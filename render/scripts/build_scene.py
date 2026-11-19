"""
Panora: assemble the client's 3ds Max export into one Blender render scene.

  render\\2-build-scene.bat   (runs this inside Blender, headless)

Reads   render/from-max/parts/*.fbx  (+ objects.json, materials.json, maps/)
Writes  render/scene/sky-tree.blend      the assembled scene (instanced, materials fixed up)
        render/scene/build-report.json   counts, polygon totals, bounds, material list
        render/scene/preview_*.jpg       quick GPU previews from 5 directions (to check the import)

Memory: each part is imported, then identical meshes are merged into shared instances before the
next part comes in, so 93M imported polygons collapse to far fewer stored ones.
"""
import bpy, os, sys, json, time, math, hashlib, glob
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(RENDER, "from-max")
OUT = os.path.join(RENDER, "scene")
ASSETS = os.path.join(RENDER, "assets")
QUICK = "--quick" in argv            # testing: fewer parts, tiny previews, CPU allowed
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "build-log.txt"), "w", encoding="utf-8")
T0 = time.time()


def log(m):
    line = f"[{time.time() - T0:7.1f}s] {m}"
    print(line, flush=True)
    LOG.write(line + "\n"); LOG.flush()


# ----------------------------------------------------------------------------- GPU
def setup_gpu(scene):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except Exception:
            continue
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            log(f"GPU: {kind} " + ", ".join(d.name for d in gpus))
            return
    scene.cycles.device = "CPU"
    log("No GPU found, using CPU")


# ----------------------------------------------------------------------------- instancing
registry = {}   # signature -> mesh datablock


def mesh_signature(me):
    n = len(me.vertices)
    if n == 0:
        return None
    co = [0.0] * (n * 3)
    me.vertices.foreach_get("co", co)
    step = max(1, n // 256) * 3
    sample = [round(c, 4) for c in co[::step]]
    h = hashlib.md5()
    h.update(f"{n}|{len(me.polygons)}|{len(me.materials)}|".encode())
    h.update(",".join(m.name.split(".")[0] if m else "-" for m in me.materials).encode())
    h.update(repr(sample).encode())
    h.update(repr([round(sum(co[i::3]), 3) for i in range(3)]).encode())
    return h.hexdigest()


def instance_new(objs):
    merged = 0
    for o in objs:
        if o.type != "MESH" or o.data is None:
            continue
        sig = mesh_signature(o.data)
        if sig is None:
            continue
        shared = registry.get(sig)
        if shared is None:
            registry[sig] = o.data
        elif shared is not o.data:
            old = o.data
            o.data = shared
            if old.users == 0:
                bpy.data.meshes.remove(old)
            merged += 1
    return merged


# ----------------------------------------------------------------------------- import
parts = sorted(glob.glob(os.path.join(SRC, "parts", "*.fbx")) + glob.glob(os.path.join(SRC, "parts", "*.obj")))
if QUICK:
    parts = parts[-2:]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
setup_gpu(scene)
col_building = bpy.data.collections.new("building"); scene.collection.children.link(col_building)
col_proxies = bpy.data.collections.new("proxies"); scene.collection.children.link(col_proxies)

imported_polys = 0
for i, p in enumerate(parts, 1):
    before = set(bpy.data.objects)
    t = time.time()
    try:
        if p.lower().endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=p, use_custom_props=True, use_image_search=False, global_scale=1.0)
        else:
            bpy.ops.wm.obj_import(filepath=p)
    except Exception as e:
        log(f"  import failed {os.path.basename(p)}: {e}")
        continue
    new = [o for o in bpy.data.objects if o not in before]
    target = col_proxies if "proxies" in os.path.basename(p) else col_building
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        target.objects.link(o)
        if o.type == "MESH":
            imported_polys += len(o.data.polygons)
    merged = instance_new(new)
    log(f"[{i}/{len(parts)}] {os.path.basename(p)}: {len(new)} objects, merged {merged} duplicates ({time.time() - t:.0f}s)")

stored_polys = sum(len(m.polygons) for m in bpy.data.meshes)
log(f"Imported {imported_polys / 1e6:.1f}M polygons; stored after instancing {stored_polys / 1e6:.1f}M in {len(bpy.data.meshes)} meshes")

# ----------------------------------------------------------------------------- materials (first pass)
mats_json = []
try:
    mats_json = json.loads(open(os.path.join(SRC, "materials.json"), encoding="latin-1").read())
except Exception as e:
    log(f"materials.json unreadable: {e}")
by_name = {}
for m in mats_json:
    by_name.setdefault(m["name"], m)


def principled(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs[0])
    return b


def setp(b, k, v):
    if k in b.inputs:
        try:
            b.inputs[k].default_value = v
        except Exception:
            pass


def fix_material(mat):
    src = by_name.get(mat.name.split(".")[0] if mat.name.split(".")[-1].isdigit() else mat.name) or by_name.get(mat.name)
    if src is None:
        return "unknown"
    b = principled(mat)
    cls = src["class"]
    if cls == "CoronaLightMtl":
        c = src.get("color", [1, 0.75, 0.45])
        setp(b, "Emission Color", (*c, 1)); setp(b, "Emission Strength", 8.0)
        mat["panora_light"] = True
        return "light"
    if cls == "_CoronaPhysicalMtl":
        if "baseColor" in src and not b.inputs["Base Color"].is_linked:
            setp(b, "Base Color", (*src["baseColor"], 1))
        setp(b, "Roughness", src.get("baseRoughness", 0.5))
        if src.get("baseMetalness", 0) or "gold" in mat.name.lower() or "stahl" in mat.name.lower():
            setp(b, "Metallic", 1.0)
        if src.get("refractionAmount", 0) > 0.5:
            setp(b, "Transmission Weight", 1.0); setp(b, "Roughness", 0.02)
            return "glass"
        return "physical"
    if cls == "CoronaLegacyMtl":
        refl = src.get("levelReflect", 0); refr = src.get("levelRefract", 0)
        gloss = src.get("reflectGlossiness", 1)
        if refr > 0.5:
            setp(b, "Transmission Weight", 1.0); setp(b, "Roughness", 0.02); setp(b, "IOR", src.get("ior", 1.52))
            setp(b, "Base Color", (0.75, 0.82, 0.85, 1))
            return "glass"
        setp(b, "Roughness", max(0.05, 1.0 - gloss) if refl > 0 else 0.75)
        setp(b, "IOR", src.get("fresnelIor", 1.52))
        return "legacy"
    return "other"


kinds = {}
for mat in bpy.data.materials:
    k = fix_material(mat)
    kinds[k] = kinds.get(k, 0) + 1
log(f"Materials: {len(bpy.data.materials)} ({kinds})")

# ----------------------------------------------------------------------------- bounds + previews
mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
for o in col_building.all_objects:
    if o.type != "MESH":
        continue
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
ctr = (mn + mx) / 2
size = (mx - mn)
log(f"Building bounds (m): min {tuple(round(v, 1) for v in mn)} max {tuple(round(v, 1) for v in mx)}")

world = bpy.data.worlds.new("Sky"); scene.world = world; world.use_nodes = True
nt = world.node_tree; nt.nodes.clear()
env = nt.nodes.new("ShaderNodeTexEnvironment")
sky = sorted(glob.glob(os.path.join(ASSETS, "hdri", "kloppenheim_05_puresky_*.hdr")) + glob.glob(os.path.join(ASSETS, "hdri", "*.hdr")))
if sky:
    env.image = bpy.data.images.load(sky[0], check_existing=True)
bg = nt.nodes.new("ShaderNodeBackground"); out = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(env.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])

cam_data = bpy.data.cameras.new("Preview"); cam_data.lens = 35; cam_data.clip_end = 20000
cam = bpy.data.objects.new("Preview", cam_data); scene.collection.objects.link(cam); scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = (480, 270) if QUICK else (1920, 1080)
scene.cycles.samples = 8 if QUICK else 96
scene.cycles.use_denoising = True
scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.quality = 90
try:
    scene.view_settings.view_transform = "AgX"
except Exception:
    pass

# save before rendering, so a render problem never loses the assembled scene
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "sky-tree.blend"), compress=False)
log("Saved scene/sky-tree.blend")

R = max(size.x, size.y, size.z)
views = {"south": (0, 12), "east": (90, 12), "north": (180, 12), "west": (270, 12), "aerial": (35, 38)}
for name, (az, el) in views.items():
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)), -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam.location = ctr + d * R * 1.55
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, f"preview_{name}.jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"Preview {name}: {time.time() - t:.0f}s")

report = {
    "parts": len(parts), "objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes),
    "importedPolygons": imported_polys, "storedPolygons": stored_polys,
    "boundsMin": list(mn), "boundsMax": list(mx), "materials": kinds,
    "materialNames": sorted(m.name for m in bpy.data.materials), "seconds": round(time.time() - T0),
}
json.dump(report, open(os.path.join(OUT, "build-report.json"), "w"), indent=2)
log("Done")
