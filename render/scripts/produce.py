"""
Sky Tree Tower - production renders for the web explorer.

  blender -b scene/sky-tree-v3.blend --python scripts/produce.py [-- --passes masks,orbit_day,explode_day,orbit_dusk,stills] [-- --quick]

1. Slices the building into 15 levels (G, 1, 2 podium; 3..13 tower; PH crown) by cutting every mesh at
   the slab tops, and parents each level to an empty that drives the "explode" animation.
2. Renders (resumable - existing frames are skipped):
     out/web/orbit/day/f_XXX.jpg     41 views on a 200 deg arc around the front (5 deg steps)
     out/web/orbit/dusk/f_XXX.jpg
     out/web/orbit/mask/f_XXX.png    floor-ID masks (red channel = (level+1)*16), same cameras
     out/web/explode/day/e_XXX.jpg   explode animation, 36 frames, fixed 3/4 camera
     out/web/explode/mask/e_XXX.png
     out/web/stills/*.jpg            2560x1440 hero stills from the look-dev cameras
     out/web/levels.json             level names, heights, colours, camera data
Saves scene/sky-tree-v4.blend (with levels + explode rig) first.
"""
import bpy, bmesh, math, os, sys, time, json
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in ARGV
NO_SLICE = "--no-slice" in ARGV
PASSES = ARGV[ARGV.index("--passes") + 1].split(",") if "--passes" in ARGV else ["masks", "orbit_day", "explode_day", "orbit_dusk", "stills"]
SCENE_DIR = os.path.dirname(bpy.data.filepath)
RENDER_DIR = os.path.dirname(SCENE_DIR)
OUT = os.path.join(RENDER_DIR, "out", "web")
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
LOG = open(os.path.join(SCENE_DIR, "produce-log.txt"), "a")
def log(m):
    s = f"[{time.time() - T0:7.1f}s] {m}"
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

scene = bpy.context.scene
CX, CY = -158.0, -5.5           # building centre (plan)
TOP = 82.1
# ---------------------------------------------------------------- levels (slab tops, world z, after the rebuild)
TOPS = [11.6, 18.9] + [25.0 + 3.5 * k for k in range(12)]      # 25.0 .. 63.5
CUTS = [t + 0.03 for t in TOPS]                                   # just above each slab top
NAMES = ["G", "1", "2"] + [str(3 + k) for k in range(11)] + ["PH"]   # 15 levels
assert len(NAMES) == len(CUTS) + 1
EXPLODE_GAP = 4.2

def level_of(z):
    for i, c in enumerate(CUTS):
        if z < c: return i
    return len(CUTS)

# ---------------------------------------------------------------- 1. slice into levels
def building_objects():
    out = []
    for cname in ("building", "proxies"):
        c = bpy.data.collections.get(cname)
        if c:
            out += [o for o in c.all_objects if o.type == "MESH"]
    return out

def bounds(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return min(v.z for v in bb), max(v.z for v in bb)

def cut_range(me, mw, lo, hi):
    inv = mw.inverted(); n = (mw.to_3x3().transposed() @ Vector((0, 0, 1))).normalized()
    bm = bmesh.new(); bm.from_mesh(me)
    if lo is not None:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=inv @ Vector((0, 0, lo)), plane_no=n, clear_inner=True)
    if hi is not None:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=inv @ Vector((0, 0, hi)), plane_no=n, clear_outer=True)
    if not bm.faces:
        bm.free(); return None
    nm = bpy.data.meshes.new(me.name + "_lv"); bm.to_mesh(nm); bm.free()
    for m in me.materials: nm.materials.append(m)
    return nm

rig = bpy.data.objects.get("LEVEL_00")
if rig is None and not NO_SLICE:
    lv_col = bpy.data.collections.new("levels"); scene.collection.children.link(lv_col)
    empties = []
    for i, nm in enumerate(NAMES):
        e = bpy.data.objects.new(f"LEVEL_{i:02d}", None); e.empty_display_size = 2; lv_col.objects.link(e)
        e["level"] = nm; empties.append(e)
    cache = {}; n_cut = n_whole = 0
    for o in building_objects():
        if o.name not in bpy.data.objects: continue
        z0, z1 = bounds(o)
        if z1 < 1.3:            # site paving / kerbs / lawns: not part of the building levels
            continue
        a, b = level_of(z0 + 0.02), level_of(z1 - 0.02)
        mw = o.matrix_world.copy()
        if a == b:
            o.parent = empties[a]; o.matrix_parent_inverse = Matrix.Identity(4); o.matrix_world = mw
            o["level"] = a; n_whole += 1; continue
        rot = tuple(round(v, 4) for r in mw.to_3x3() for v in r)
        tower = a >= 4 and b <= len(CUTS) - 1          # wholly inside the evenly spaced tower floors
        zkey = round(((mw.translation.z - CUTS[3]) % 3.5), 3) if tower else round(mw.translation.z, 3)
        key = (o.data.name, rot, zkey, (b - a) if tower else (a, b))
        rel = cache.get(key)
        if rel is None:
            rel = {}
            for k in range(a, b + 1):
                lo = CUTS[k - 1] if k > 0 else None
                hi = CUTS[k] if k < len(CUTS) else None
                m = cut_range(o.data, mw, lo, hi)
                if m: rel[k - a] = m
            cache[key] = rel
        pieces = {a + d: m for d, m in rel.items()}
        cols = list(o.users_collection)
        for k, m in pieces.items():
            p = bpy.data.objects.new(f"{o.name}_L{k:02d}", m)
            for c in cols: c.objects.link(p)
            p.parent = empties[k]; p.matrix_parent_inverse = Matrix.Identity(4); p.matrix_world = mw; p["level"] = k
        bpy.data.objects.remove(o); n_cut += 1
        if n_cut % 25 == 0: log(f"  cut {n_cut} objects")
    for me in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(me)
    log(f"Levels: {len(NAMES)}; whole objects {n_whole}, cut objects {n_cut} ({len(cache)} unique cuts)")
    # explode animation: frame 1 closed, frame 36 fully open (eased)
    for i, e in enumerate(empties):
        e.location = (0, 0, 0); e.keyframe_insert("location", index=2, frame=1)
        e.location = (0, 0, i * EXPLODE_GAP); e.keyframe_insert("location", index=2, frame=36)
        try:
            for fc in e.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.easing = "AUTO"
        except Exception:
            pass
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCENE_DIR, "sky-tree-v4.blend"), compress=False)
    log("Saved scene/sky-tree-v4.blend")
empties = [bpy.data.objects.get(f"LEVEL_{i:02d}") for i in range(len(NAMES))]

# ---------------------------------------------------------------- modes (from lookdev)
ns = {}
try:
    exec(bpy.data.texts["set_mode.py"].as_string(), ns)
except Exception:
    pass
def set_mode(mode):
    """day / dusk via the world + night lights set up by lookdev.py."""
    world = scene.world; nt = world.node_tree
    env = nt.nodes.get("SkyImg"); mp = nt.nodes.get("SkyRot"); bg = nt.nodes.get("SkyBg")
    assets = os.path.join(RENDER_DIR, "assets", "hdri")
    spec = {"day": ("evening_road_01_puresky", 1.0, -62.0, 0.0, 0.05),
            "golden": ("evening_road_01_puresky", 1.0, -62.0, 0.0, 0.05),
            "dusk": ("belfast_sunset_puresky", 1.0, 60.0, 0.55, 0.3),
            "night": ("qwantani_night_puresky", 0.12, 30.0, 1.0, 0.3)}[mode]
    p = os.path.join(assets, spec[0] + "_8k.hdr")
    if not os.path.exists(p): p = os.path.join(assets, spec[0] + "_4k.hdr")
    sw = nt.nodes.get("SkyCamSwitch")
    if sw: sw.inputs[0].default_value = 0.0
    if sw and spec[0] == "evening_road_01_puresky":   # sharp backdrop only exists for the golden-hour sky
        lp = next((n for n in nt.nodes if n.type == "LIGHT_PATH"), None)
        if lp and not sw.inputs[0].is_linked: nt.links.new(lp.outputs["Is Camera Ray"], sw.inputs[0])
    elif sw:
        for l in list(sw.inputs[0].links): nt.links.remove(l)
    for m in bpy.data.materials:
        if m.name.startswith("M_Sat_") and m.node_tree:
            hz = m.node_tree.nodes.get("HazeEm")
            if hz: hz.inputs["Color"].default_value = (*HAZE.get(mode, HAZE["day"]), 1)
    if env and os.path.exists(p):
        img = bpy.data.images.load(p, check_existing=True); env.image = img
        rot = scene.get(f"rot_{mode}")
        if rot is None:   # same sun-alignment as lookdev.py: find the sun in the HDRI, rotate it to the wanted azimuth
            sm = img.copy(); sm.scale(256, 128); px = list(sm.pixels); bpy.data.images.remove(sm)
            best, bi = -1, 0
            for i in range(0, len(px), 4):
                v = px[i] + px[i + 1] + px[i + 2]
                if v > best: best, bi = v, i // 4
            u_az = ((bi % 256 + 0.5) / 256 - 0.5) * 2 * math.pi
            rot = -math.pi / 2 - u_az - math.radians(spec[2]); scene[f"rot_{mode}"] = rot
        mp.inputs["Rotation"].default_value[2] = rot
    golden = spec[0] == "evening_road_01_puresky"
    if bg: bg.inputs["Strength"].default_value = 0.6 if golden else spec[1]
    sun = bpy.data.objects.get("GoldenSun")
    if sun is None:
        ld = bpy.data.lights.new("GoldenSun", "SUN"); sun = bpy.data.objects.new("GoldenSun", ld); scene.collection.objects.link(sun)
    az, el = math.radians(spec[2]), math.radians(13.0)
    sdir = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-sdir).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = 6.0; sun.data.color = (1.0, 0.74, 0.48); sun.data.angle = math.radians(0.8)
    sun.hide_render = not golden
    scene["night"] = spec[3]
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name.startswith("Up_"):
            base = o.get("base_energy", o.data.energy if spec[3] > 0.05 else 1000.0)
            o["base_energy"] = base
            o.data.energy = base * (spec[3] ** 1.5); o.hide_render = spec[3] < 0.05
    scene.view_settings.exposure = spec[4]

# ---------------------------------------------------------------- cameras
def look(cam, loc, tgt):
    cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
def make_cam(name, lens):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 6000; cd.clip_start = 0.5
    o = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if o.name not in scene.collection.objects: scene.collection.objects.link(o)
    return o
ORBIT = {"radius": 240.0, "elev_deg": 8.0, "target_z": 45.0, "lens": 32.0, "az0": -100.0, "step": 2.5, "count": 81}   # 2.5 deg steps: smooth swipes
def orbit_pose(i):
    az = math.radians(ORBIT["az0"] + i * ORBIT["step"]); el = math.radians(ORBIT["elev_deg"])
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    tgt = Vector((CX, CY, ORBIT["target_z"]))
    return tgt + d * ORBIT["radius"], tgt
FLY = {"frames": 168, "samples": 128}
GROUND = {"radius": 118.0, "height": 7.0, "target_z": 40.0, "lens": 22.0, "az0": -100.0, "step": 5.0, "count": 41}
def ground_pose_az(azd):
    az = math.radians(azd)
    P = Vector((CX + math.sin(az) * GROUND["radius"], CY - math.cos(az) * GROUND["radius"], GROUND["height"]))
    return P, Vector((CX, CY, GROUND["target_z"]))
def ground_pose(i): return ground_pose_az(GROUND["az0"] + i * GROUND["step"])
EXPL = {"az": 32.0, "elev": 10.0, "dist": 290.0, "target_z": 64.0, "lens": 33.0, "frames": 36}
def explode_pose():
    az = math.radians(EXPL["az"]); el = math.radians(EXPL["elev"])
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    tgt = Vector((CX, CY, EXPL["target_z"]))
    return tgt + d * EXPL["dist"], tgt

# ---------------------------------------------------------------- render settings
W, H = (480, 270) if QUICK else (1600, 900)
def cycles_setup(samples):
    scene.render.engine = "CYCLES"; scene.cycles.samples = 8 if QUICK else samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = W, H; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.quality = 88
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"; prefs.get_devices()
        for d in prefs.devices: d.use = d.type != "CPU"
        scene.cycles.device = "GPU"
    except Exception as e:
        log(f"GPU: {e}")

def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

hidden_for_mask = []
def _interior_vis(on, extra=()):
    for cn in ("interior_v1",) + tuple(extra):
        c = bpy.data.collections.get(cn)
        if c:
            for o in c.all_objects: o.hide_render = not on
def mask_setup(on):
    """Workbench, flat object colours, no AA: red channel encodes the level."""
    global hidden_for_mask
    _interior_vis(not on)
    if on:
        scene.render.engine = "BLENDER_WORKBENCH"
        sh = scene.display.shading
        sh.light = "FLAT"; sh.color_type = "OBJECT"; sh.show_shadows = False; sh.show_cavity = False
        sh.show_object_outline = False; sh.show_specular_highlight = False
        try: scene.display.render_aa = "OFF"
        except Exception: pass
        scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0; scene.view_settings.gamma = 1.0
        scene.render.resolution_x, scene.render.resolution_y = W // 2, H // 2
        scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.compression = 90
        scene.world.color = (0, 0, 0)
        for o in bpy.data.objects:
            lv = o.get("level")
            if isinstance(lv, int):
                v = srgb_to_lin((lv + 1) * 16 / 255.0); o.color = (v, 0, 0, 1)
            else:
                o.color = (0, 0, 0, 1)
            # vegetation, cars, people do not block clicks
            if o.type == "EMPTY" and o.instance_type == "COLLECTION" and not o.hide_render:
                o.hide_render = True; hidden_for_mask.append(o)
    else:
        for o in hidden_for_mask: o.hide_render = False
        hidden_for_mask = []
        try: scene.view_settings.look = "AgX - Medium High Contrast"
        except Exception: pass

def render_to(path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene.render.filepath = path; bpy.ops.render.render(write_still=True); return True

cam = make_cam("CAM_web", ORBIT["lens"]); scene.camera = cam

def do_orbit(kind, mode=None):
    for i in range(ORBIT["count"]):
        loc, tgt = orbit_pose(i); look(cam, loc, tgt)
        p = os.path.join(OUT, "orbit", kind, f"f_{i:03d}." + ("png" if kind == "mask" else "jpg"))
        t = time.time()
        if render_to(p): log(f"orbit {kind} {i:03d}: {time.time() - t:.0f}s")

def do_explode(kind):
    _interior_vis(False, ("facade_v2",))   # the floors fly apart; the lobby dressing, backing shells and new podium stone stay out of it
    loc, tgt = explode_pose(); look(cam, loc, tgt); cam.data.lens = EXPL["lens"]
    for f in range(1, EXPL["frames"] + 1):
        scene.frame_set(f)
        p = os.path.join(OUT, "explode", kind, f"e_{f - 1:03d}." + ("png" if kind == "mask" else "jpg"))
        t = time.time()
        if render_to(p): log(f"explode {kind} {f - 1:03d}: {time.time() - t:.0f}s")
    scene.frame_set(1); cam.data.lens = ORBIT["lens"]; _interior_vis(kind != "mask", ("facade_v2",)) if kind != "mask" else None

# ---------------------------------------------------------------- car paint: Lahore palette (white / silver / black / grey)
import re as _re
PAINT = [(0.80, 0.80, 0.78), (0.02, 0.02, 0.022), (0.55, 0.56, 0.57), (0.82, 0.82, 0.80), (0.30, 0.31, 0.32),
         (0.62, 0.60, 0.55), (0.04, 0.06, 0.12), (0.75, 0.75, 0.74), (0.18, 0.02, 0.03)]
def recolor_cars():
    n = 0
    cars = [c for c in bpy.data.collections if c.name.startswith("BK_") and c.get("kind") == "car"]
    for k, c in enumerate(sorted(cars, key=lambda c: c.name)):
        col = (*PAINT[k % len(PAINT)], 1.0)
        mats = {s.material for o in c.all_objects for s in getattr(o, "material_slots", []) if s.material}
        for m in mats:
            if not m.node_tree or not _re.search(r"car ?paint|carpaint|maincolor|body|pure carpaint|patterned carpaint", m.name, _re.I):
                continue
            for nd in m.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED":
                    bc = nd.inputs["Base Color"]
                    for l in list(bc.links): m.node_tree.links.remove(l)
                    bc.default_value = col; n += 1
                elif nd.type == "GROUP":
                    for inp in nd.inputs:
                        if inp.type == "RGBA" and _re.match(r"colou?r", inp.name, _re.I):
                            for l in list(inp.links): m.node_tree.links.remove(l)
                            inp.default_value = col; n += 1
                elif nd.type == "RGB":
                    r, g, b, _a = nd.outputs[0].default_value
                    if max(r, g, b) - min(r, g, b) > 0.15:
                        nd.outputs[0].default_value = col; n += 1
    log(f"Car paint: {n} inputs recoloured on {len(cars)} models")
recolor_cars()

def shrink_textures():
    """Packed asset textures come back at full size when a .blend is reopened: cap them again (12 GB GPU)."""
    bk_imgs = set()
    def walk(nt, acc):
        for nd in nt.nodes:
            if nd.type == "TEX_IMAGE" and nd.image: acc.add(nd.image.name)
            elif nd.type == "GROUP" and nd.node_tree: walk(nd.node_tree, acc)
    for c in bpy.data.collections:
        if c.name.startswith("BK_") or c.name.startswith("A_"):
            for o in c.all_objects:
                for sl in getattr(o, "material_slots", []):
                    if sl.material and sl.material.node_tree: walk(sl.material.node_tree, bk_imgs)
    n = 0; px = 0
    for im in bpy.data.images:
        if im.type != "IMAGE" or im.source != "FILE": continue
        if im.filepath.lower().endswith((".hdr", ".exr")): continue
        cap = 1024 if im.name in bk_imgs else 2048
        try:
            w, h = im.size
            if max(w, h) > cap:
                f = cap / max(w, h); im.scale(max(1, int(w * f)), max(1, int(h * f))); n += 1
            px += im.size[0] * im.size[1]
        except Exception:
            pass
    log(f"Textures capped: {n} images resized, {px / 1e6:.0f} Mpx in total")
shrink_textures()

def far_ground():
    """Push the terrain edge out to the real horizon and fade distant lawn into atmospheric haze."""
    t = bpy.data.objects.get("Terrain")
    if t is not None and t.type == "MESH":
        xs = [v.co.x for v in t.data.vertices]; cx0 = (min(xs) + max(xs)) / 2
        for v in t.data.vertices:
            v.co.x = cx0 + (v.co.x - cx0) * 12.0; v.co.y = v.co.y * 12.0
        t.data.update()
    m = bpy.data.materials.get("ST_Grass")
    if m and m.use_nodes:
        nt = m.node_tree; P = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if P and P.inputs["Base Color"].is_linked:
            src = P.inputs["Base Color"].links[0].from_socket
            cam = nt.nodes.new("ShaderNodeCameraData")
            d0 = nt.nodes.new("ShaderNodeMath"); d0.operation = "SUBTRACT"; d0.inputs[1].default_value = 450.0
            nt.links.new(cam.outputs["View Distance"], d0.inputs[0])
            d1 = nt.nodes.new("ShaderNodeMath"); d1.operation = "MAXIMUM"; d1.inputs[1].default_value = 0.0
            nt.links.new(d0.outputs[0], d1.inputs[0])
            m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = -1.0 / 2600.0
            nt.links.new(d1.outputs[0], m1.inputs[0])
            m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "EXPONENT"; nt.links.new(m1.outputs[0], m2.inputs[0])
            m3 = nt.nodes.new("ShaderNodeMath"); m3.operation = "SUBTRACT"; m3.inputs[0].default_value = 0.9
            nt.links.new(m2.outputs[0], m3.inputs[1])
            m4 = nt.nodes.new("ShaderNodeMath"); m4.operation = "MAXIMUM"; m4.inputs[1].default_value = 0.0
            nt.links.new(m3.outputs[0], m4.inputs[0])
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
            nt.links.new(m4.outputs[0], mx.inputs[0]); nt.links.new(src, mx.inputs[6])
            mx.inputs[7].default_value = (0.15, 0.18, 0.21, 1.0)
            nt.links.new(mx.outputs[2], P.inputs["Base Color"])
            log("Far ground: terrain x12, lawn haze on")
far_ground()

# ---------------------------------------------------------------- environment v2: the real site
SITE_PIN = (CX, -39.3)              # 31.3793117 N, 74.2543937 E sits 31 m from the Pine Avenue centreline
SAT_ROT = math.radians(70.7)        # true north is rotated so Pine Avenue runs along the modelled boulevard
NEAR_HALF = 520.0                   # modelled boulevard / traffic / trees kept within this many metres of the tower
HAZE = {"golden": (0.52, 0.54, 0.57), "day": (0.52, 0.54, 0.57), "dusk": (0.16, 0.15, 0.17), "night": (0.02, 0.02, 0.03)}
def env_v2():
    random = __import__("random"); random.seed(11)
    t = bpy.data.objects.get("Terrain")
    if t: t.hide_render = True
    for o in bpy.data.objects:   # the placeholder white blocks: the satellite now carries the real neighbourhood
        if o.type == "MESH" and any(sl.material and sl.material.name.startswith("ST_Context") for sl in o.material_slots):
            o.hide_render = True
    def near(x, y):
        return (-100.0 < y < -41.0 and abs(x - CX) < NEAR_HALF) or (abs(x - CX) < 80.0 and -45.0 < y < 60.0)
    dropped = 0
    for cn in ("vegetation", "traffic", "street_lights"):
        col = bpy.data.collections.get(cn)
        if not col: continue
        for o in list(col.all_objects):
            if o is None: continue
            p = o.matrix_world.translation
            if not near(p.x, p.y): o.hide_render = True; dropped += 1
    tr = bpy.data.collections.get("traffic")   # no cars: the client wants an empty, calm boulevard
    if tr:
        for o in tr.all_objects:
            if o is not None: o.hide_render = True
    for o in bpy.data.objects:
        if o.instance_type == "COLLECTION" and o.instance_collection and _re.match(r"^(A_|BK_)?(audi|tesla|cullinan|mustang|amg|bronco|porsche|lexus|bus|mercedes)", o.instance_collection.name, _re.I):
            o.hide_render = True
    # trim the modelled boulevard; the real road carries on in the satellite image
    site = bpy.data.collections.get("site")
    if site:
        for o in site.all_objects:
            if o is None or o.type != "MESH": continue
            if not _re.match(r"^(Sidewalk|Road_|Median|Lane_|Edge_)", o.name): continue
            me = o.data
            for v in me.vertices:
                v.co.x = min(max(v.co.x, CX - NEAR_HALF), CX + NEAR_HALF)
            me.update()
    # tree line around the plot (field boundaries in this area are tree-lined) - hides the flat horizon at eye level
    trees = [o for o in (bpy.data.collections.get("vegetation").all_objects if bpy.data.collections.get("vegetation") else [])
             if o is not None and o.instance_type == "COLLECTION" and o.instance_collection
             and _re.search(r"maple|eucalyptus|broadleaf|island_tree", o.instance_collection.name, _re.I)]
    added = 0
    if trees:
        ring = [(CX + x, 58.0 + random.uniform(-3, 3)) for x in range(-76, 77, 9)]
        ring += [(CX + sx * (78.0 + random.uniform(-2, 2)), y) for sx in (-1, 1) for y in range(-38, 58, 9)]
        for (x, y) in ring:
            src = random.choice(trees); e = src.copy(); e.hide_render = False
            e.location = (x, y, 0.0); e.rotation_euler = (0, 0, random.uniform(0, 6.283))
            k = random.uniform(1.1, 1.6); e.scale = (src.scale[0] * k,) * 3
            bpy.data.collections["vegetation"].objects.link(e); added += 1
    # satellite imagery, three nested levels of detail
    sat_dir = os.path.join(RENDER_DIR, "assets", "sat")
    def sat_mat(name, path, fade):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial"); bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = bpy.data.images.load(path, check_existing=True); tx.extension = "EXTEND"
        tx.interpolation = "Cubic"
        hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 1.0; hs.inputs["Value"].default_value = 0.85
        nt.links.new(tx.outputs["Color"], hs.inputs["Color"]); nt.links.new(hs.outputs["Color"], bs.inputs["Base Color"])
        dpath = os.path.join(RENDER_DIR, "assets", "tex", "leafy_grass_diff_2k.jpg")
        if name.endswith("Sat_z18") and os.path.exists(dpath):
            # close to the camera the satellite pixels are replaced by real ground texture, tinted by the satellite colour,
            # so street-level views get crisp grass while aerial views still show the true neighbourhood
            tc2 = nt.nodes.new("ShaderNodeTexCoord"); mp2 = nt.nodes.new("ShaderNodeMapping"); mp2.inputs["Scale"].default_value = (0.3, 0.3, 0.3)
            nt.links.new(tc2.outputs["Object"], mp2.inputs["Vector"])
            dt = nt.nodes.new("ShaderNodeTexImage"); dt.image = bpy.data.images.load(dpath, check_existing=True); nt.links.new(mp2.outputs[0], dt.inputs["Vector"])
            mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 1.0
            nt.links.new(hs.outputs["Color"], mul.inputs[6]); nt.links.new(dt.outputs["Color"], mul.inputs[7])
            gain = nt.nodes.new("ShaderNodeMix"); gain.data_type = "RGBA"; gain.blend_type = "MULTIPLY"; gain.inputs[0].default_value = 1.0
            nt.links.new(mul.outputs[2], gain.inputs[6]); gain.inputs[7].default_value = (2.9, 2.9, 2.9, 1)
            cd = nt.nodes.new("ShaderNodeCameraData"); fd = nt.nodes.new("ShaderNodeMapRange")
            fd.inputs["From Min"].default_value = 40.0; fd.inputs["From Max"].default_value = 240.0; fd.inputs["To Min"].default_value = 1.0; fd.inputs["To Max"].default_value = 0.0
            nt.links.new(cd.outputs["View Distance"], fd.inputs["Value"])
            mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
            nt.links.new(fd.outputs[0], mix.inputs[0]); nt.links.new(hs.outputs["Color"], mix.inputs[6]); nt.links.new(gain.outputs[2], mix.inputs[7])
            nt.links.new(mix.outputs[2], bs.inputs["Base Color"])
            bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(dt.outputs["Color"], bw.inputs[0])
            bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.4; nt.links.new(bw.outputs[0], bp.inputs["Height"]); nt.links.new(bp.outputs[0], bs.inputs["Normal"])
        bs.inputs["Roughness"].default_value = 0.93
        try: bs.inputs["Specular IOR Level"].default_value = 0.2
        except Exception: pass
        # aerial perspective: distant ground melts into the horizon haze
        cam = nt.nodes.new("ShaderNodeCameraData")
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = -1.0 / 4500.0
        nt.links.new(cam.outputs["View Distance"], m1.inputs[0])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "EXPONENT"; nt.links.new(m1.outputs[0], m2.inputs[0])
        m3 = nt.nodes.new("ShaderNodeMath"); m3.operation = "SUBTRACT"; m3.inputs[0].default_value = 0.97; nt.links.new(m2.outputs[0], m3.inputs[1])
        m4 = nt.nodes.new("ShaderNodeMath"); m4.operation = "MAXIMUM"; m4.inputs[1].default_value = 0.0; nt.links.new(m3.outputs[0], m4.inputs[0])
        em = nt.nodes.new("ShaderNodeEmission"); em.name = "HazeEm"; em.inputs["Color"].default_value = (*HAZE["golden"], 1)
        mx = nt.nodes.new("ShaderNodeMixShader"); nt.links.new(m4.outputs[0], mx.inputs[0])
        nt.links.new(bs.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        last = mx.outputs[0]
        if fade:   # soft edge so the coarser level below takes over without a seam
            tc = nt.nodes.new("ShaderNodeTexCoord"); sp = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["UV"], sp.inputs[0])
            def edge(sock):
                a = nt.nodes.new("ShaderNodeMath"); a.operation = "SUBTRACT"; a.inputs[0].default_value = 0.5; nt.links.new(sock, a.inputs[1])
                b = nt.nodes.new("ShaderNodeMath"); b.operation = "ABSOLUTE"; nt.links.new(a.outputs[0], b.inputs[0]); return b.outputs[0]
            mxm = nt.nodes.new("ShaderNodeMath"); mxm.operation = "MAXIMUM"; nt.links.new(edge(sp.outputs["X"]), mxm.inputs[0]); nt.links.new(edge(sp.outputs["Y"]), mxm.inputs[1])
            mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.40; mr.inputs["From Max"].default_value = 0.5
            nt.links.new(mxm.outputs[0], mr.inputs["Value"])
            tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mf = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(mr.outputs[0], mf.inputs[0]); nt.links.new(last, mf.inputs[1]); nt.links.new(tr.outputs[0], mf.inputs[2]); last = mf.outputs[0]
        nt.links.new(last, out.inputs["Surface"])
        return m
    made = []
    for nm, fn, half, z, fade in (("Sat_z18", "site_z18.jpg", 650.0, -0.03, True), ("Sat_z16", "site_z16.jpg", 3200.0, -0.07, True),
                                  ("Sat_z14", "site_z14.jpg", 14000.0, -0.11, False)):
        path = os.path.join(sat_dir, fn)
        if not os.path.exists(path): log(f"missing {path}"); continue
        me = bpy.data.meshes.new(nm); vs = [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)]
        me.from_pydata(vs, [], [(0, 1, 2, 3)]); uv = me.uv_layers.new()
        for lp in me.loops:
            v = vs[lp.vertex_index]; uv.data[lp.index].uv = ((v[0] / half + 1) / 2, (v[1] / half + 1) / 2)
        me.materials.append(sat_mat("M_" + nm, path, fade))
        o = bpy.data.objects.new(nm, me); scene.collection.objects.link(o)
        o.location = (SITE_PIN[0], SITE_PIN[1], z); o.rotation_euler = (0, 0, SAT_ROT); made.append(nm)
    # sky: sharp 8k backdrop for camera rays, the HDRI keeps lighting the scene
    w = scene.world; nt = w.node_tree; env = nt.nodes.get("SkyImg"); mp = nt.nodes.get("SkyRot"); bg = nt.nodes.get("SkyBg")
    bgp = os.path.join(RENDER_DIR, "assets", "hdri", "sky_bg_8k.jpg")
    if env and mp and bg and os.path.exists(bgp) and not nt.nodes.get("SkyCam"):
        tx = nt.nodes.new("ShaderNodeTexEnvironment"); tx.name = "SkyCam"; tx.image = bpy.data.images.load(bgp, check_existing=True)
        nt.links.new(mp.outputs[0], tx.inputs["Vector"])
        sc = nt.nodes.new("ShaderNodeMath"); sc.name = "SkyCamGain"; sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 5.06
        # luminance-independent scale: multiply colour via a MixRGB multiply
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.name = "SkyCamMul"
        mul.inputs[0].default_value = 1.0; nt.links.new(tx.outputs["Color"], mul.inputs[6]); mul.inputs[7].default_value = (5.06, 5.06, 5.06, 1)
        lp = nt.nodes.new("ShaderNodeLightPath"); sw = nt.nodes.new("ShaderNodeMix"); sw.data_type = "RGBA"; sw.name = "SkyCamSwitch"
        nt.links.new(lp.outputs["Is Camera Ray"], sw.inputs[0]); nt.links.new(env.outputs["Color"], sw.inputs[6]); nt.links.new(mul.outputs[2], sw.inputs[7])
        nt.links.new(sw.outputs[2], bg.inputs["Color"])
    log(f"Env v2: satellite {made}, {dropped} far props hidden, {added} boundary trees")
env_v2()

# ---------------------------------------------------------------- site v3: forecourt, parking, boundary wall, palms, lights, road text
PLOT = (-185.0, -117.5, -50.6, 23.6)        # x0, x1, y0, y1 of the client's site plate
def _mat(name, base=(0.5, 0.5, 0.5), rough=0.6, emit=None, estr=0.0, tex=None, scale=1.0, tint=None, metal=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*base, 1); bs.inputs["Roughness"].default_value = rough; bs.inputs["Metallic"].default_value = metal
    if emit:
        bs.inputs["Emission Color"].default_value = (*emit, 1); bs.inputs["Emission Strength"].default_value = estr
    if tex:
        d = os.path.join(RENDER_DIR, "assets", "tex")
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        def img(suffix, color):
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(d, f"{tex}_{suffix}_2k.jpg"), check_existing=True)
            if not color: t.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mp.outputs[0], t.inputs["Vector"]); return t
        dif = img("diff", True); rgh = img("rough", False); nor = img("nor_gl", False)
        last = dif.outputs["Color"]
        if tint:
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
            nt.links.new(last, mx.inputs[6]); mx.inputs[7].default_value = (*tint, 1); last = mx.outputs[2]
        nt.links.new(last, bs.inputs["Base Color"]); nt.links.new(rgh.outputs["Color"], bs.inputs["Roughness"])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
        nt.links.new(nor.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs[0], bs.inputs["Normal"])
    return m
def _box(name, x0, x1, y0, y1, z0, z1, mat, col):
    me = bpy.data.meshes.new(name)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me.from_pydata(v, [], f); me.materials.append(mat); o = bpy.data.objects.new(name, me); col.objects.link(o); return o
def _ground_z(x, y):
    """Height of the paving / ground at (x, y), looking through trees, plants and anything hidden from render."""
    dg = bpy.context.evaluated_depsgraph_get(); z0 = 60.0
    for _ in range(40):
        hit, loc, nrm, idx, ob, mw = scene.ray_cast(dg, Vector((x, y, z0)), Vector((0, 0, -1)), distance=z0 + 60)
        if not hit: return 0.0
        o = getattr(ob, "original", ob)
        cols = [c.name for c in o.users_collection]
        skip = o.hide_render or any(n.startswith(("BK_", "LS_", "PH_", "vegetation", "traffic", "people")) for n in cols) or o.type != "MESH" or nrm.z < 0.6 or loc.z > 6.0
        if not skip: return loc.z
        z0 = loc.z - 0.02
    return 0.0
SIGNS = {"TextPlus039": 1.22, "Shape1": 1.45, "Shape179": 1.45}   # SKY TREE TOWER lettering, HF emblems (east + west podium faces)
def site_v3():
    random = __import__("random"); random.seed(5)
    col = bpy.data.collections.get("site_v3") or bpy.data.collections.new("site_v3")
    if col.name not in scene.collection.children: scene.collection.children.link(col)
    x0, x1, y0, y1 = PLOT
    # stray pieces of the client file sitting on the boulevard
    for o in bpy.data.objects:
        if o.type == "MESH" and any(c.name == "building" for c in o.users_collection):
            p = o.matrix_world.translation
            if p.x > -110.0: o.hide_render = True
    # big trees inside the plot block the building: keep palms and shrubs only
    veg = bpy.data.collections.get("vegetation")
    if veg:
        for o in veg.all_objects:
            if o is None or o.instance_type != "COLLECTION" or not o.instance_collection: continue
            p = o.matrix_world.translation
            if x0 - 3 < p.x < x1 + 3 and y0 - 3 < p.y < y1 + 3 and _re.search(r"maple|eucalyptus|broadleaf|jacaranda|island", o.instance_collection.name, _re.I):
                o.hide_render = True
    # materials: pavers for the forecourt, asphalt for the drive, stone curbs
    pav = _mat("ST_Pavers", tex="large_grey_tiles", scale=0.33, tint=(1.0, 0.93, 0.82))
    asp = _mat("ST_Asphalt", tex="asphalt_02", scale=0.12, tint=(0.62, 0.62, 0.64))
    curb = _mat("ST_Curb", base=(0.62, 0.60, 0.56), rough=0.7)
    paint = _mat("ST_Paint", base=(0.85, 0.85, 0.82), rough=0.55)
    for o in bpy.data.objects:
        if o.type != "MESH": continue
        if o.name == "Line082": o.data.materials.clear(); o.data.materials.append(pav)
        elif o.name == "Line086": o.data.materials.clear(); o.data.materials.append(asp)
        elif o.name == "Line089": o.data.materials.clear(); o.data.materials.append(curb)
    # parking: drive lane edge lines + nine parallel bays along the east boundary
    zr = _ground_z(-122.0, -10.0) + 0.012
    _box("Pk_edge_W", -126.4, -126.25, y0 + 2, y1 - 2, zr, zr + 0.004, paint, col)
    for k in range(10):
        yy = -40.0 + k * 6.2
        _box(f"Pk_bay_{k}", -120.6, -118.0, yy, yy + 0.12, zr, zr + 0.004, paint, col)
    _box("Pk_bay_line", -120.72, -120.6, -40.0, -40.0 + 9 * 6.2 + 0.12, zr, zr + 0.004, paint, col)
    for k in range(4):   # direction arrows
        yy = -38.0 + k * 15.0
        _box(f"Pk_arrow_{k}", -123.3, -123.0, yy, yy + 3.2, zr, zr + 0.004, paint, col)
        _box(f"Pk_arrowh_{k}", -123.9, -122.4, yy + 3.2, yy + 3.5, zr, zr + 0.004, paint, col)
    # boundary wall with pilasters, lantern caps and gate pillars
    stone = bpy.data.materials.get("ST_Limestone") or _mat("ST_WallStone", base=(0.78, 0.72, 0.6), rough=0.7)
    lamp = _mat("ST_Lantern", base=(1.0, 0.9, 0.75), rough=0.3, emit=(1.0, 0.76, 0.48), estr=6.0)
    def wall(xa, ya, xb, yb, h):
        zg = _ground_z((xa + xb) / 2, (ya + yb) / 2)
        t = 0.35
        if abs(xb - xa) > abs(yb - ya): _box("Wall", min(xa, xb), max(xa, xb), ya - t / 2, ya + t / 2, zg, zg + h, stone, col)
        else: _box("Wall", xa - t / 2, xa + t / 2, min(ya, yb), max(ya, yb), zg, zg + h, stone, col)
        L = math.hypot(xb - xa, yb - ya); n = max(1, int(L / 6.0))
        for k in range(n + 1):
            px, py = xa + (xb - xa) * k / n, ya + (yb - ya) * k / n
            _box("Pilaster", px - 0.35, px + 0.35, py - 0.35, py + 0.35, zg, zg + h + 0.35, stone, col)
            _box("Lantern", px - 0.2, px + 0.2, py - 0.2, py + 0.2, zg + h + 0.35, zg + h + 0.8, lamp, col)
    wall(x0, y0, x0, y1, 2.2); wall(x0, y1, x1, y1, 2.2); wall(x1, y1, x1, y0 + 9.5, 2.2)
    for gx in (-176.0, -140.0, -127.5, x1):
        zg = _ground_z(gx, y0)
        _box("GatePillar", gx - 0.6, gx + 0.6, y0 - 0.6, y0 + 0.6, zg, zg + 3.2, stone, col)
        _box("GateLamp", gx - 0.3, gx + 0.3, y0 - 0.3, y0 + 0.3, zg + 3.2, zg + 3.9, lamp, col)
        ld = bpy.data.lights.new("GateGlow", "POINT"); ld.energy = 60; ld.color = (1.0, 0.78, 0.52); ld.shadow_soft_size = 0.3
        lo = bpy.data.objects.new("GateGlow", ld); lo.location = (gx, y0 - 0.9, zg + 3.5); col.objects.link(lo)
    # palms with warm uplights: inside the side wall and framing the forecourt
    palms = [c for c in bpy.data.collections if c.name.startswith("BK_palm")]
    spots = [(x0 + 2.2, y) for y in range(-44, 22, 7)] + [(-178.5, y0 + 2.5), (-137.5, y0 + 2.5), (-130.0, y0 + 2.5), (-122.5, -45.0)]
    for k, (px, py) in enumerate(spots):
        if not palms: break
        e = bpy.data.objects.new(f"Palm3_{k}", None); e.instance_type = "COLLECTION"; e.instance_collection = random.choice(palms)
        e.location = (px, py, _ground_z(px, py)); e.rotation_euler = (0, 0, random.uniform(0, 6.28)); s_ = random.uniform(0.9, 1.15); e.scale = (s_, s_, s_)
        col.objects.link(e)
        ld = bpy.data.lights.new("PalmUp", "SPOT"); ld.energy = 120; ld.spot_size = math.radians(40); ld.color = (1.0, 0.8, 0.55)
        lo = bpy.data.objects.new("PalmUp", ld); lo.location = (px + 0.6, py - 0.6, e.location.z + 0.15); lo.rotation_euler = (math.radians(-12), math.radians(-8), 0)
        col.objects.link(lo)
    # PINE AVENUE painted on the carriageway in front of the tower
    for k, (tx, ty, rot) in enumerate(((CX + 2.0, -63.4, 0.0), (CX - 2.0, -77.6, math.pi))):
        cu = bpy.data.curves.new(f"PineText{k}", "FONT"); cu.body = "PINE  AVENUE"; cu.size = 2.6; cu.align_x = "CENTER"; cu.align_y = "CENTER"
        cu.space_character = 1.15
        to = bpy.data.objects.new(f"PineText{k}", cu); to.location = (tx, ty, _ground_z(tx, ty) + 0.015); to.rotation_euler = (0, 0, rot)
        cu.materials.append(paint); col.objects.link(to)
    # make the SKY TREE lettering and the HF emblem read from a distance
    sg = _mat("ST_SignGold", base=(0.92, 0.62, 0.24), rough=0.28, metal=1.0, emit=(1.0, 0.62, 0.22), estr=0.9)
    plate = _mat("ST_SignPlate", base=(0.035, 0.04, 0.05), rough=0.35)
    signs = []
    for nm, k in SIGNS.items():
        o = bpy.data.objects.get(nm)
        if o is None or o.type != "MESH": continue
        signs.append(nm)
        me = o.data.copy(); o.data = me
        for i in range(len(me.materials)): me.materials[i] = sg
        bb = [Vector(c) for c in o.bound_box]; c = sum(bb, Vector()) / 8.0      # scale about the sign's own centre, standing slightly proud of the wall
        nrm = Vector((0, -1, 0)) if nm == "TextPlus039" else Vector((1, 0, 0)) if nm == "Shape1" else Vector((-1, 0, 0))
        mw = o.matrix_world.copy(); wc = mw @ c
        from mathutils import Matrix
        o.matrix_world = Matrix.Translation(wc + nrm * (0.34 if nm == "TextPlus039" else 0.06)) @ Matrix.Scale(k, 4) @ Matrix.Translation(-wc) @ mw
        if nm == "TextPlus039":   # dark slate band behind the lettering: gold on black reads from the boulevard
            wb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            x0_, x1_ = min(v.x for v in wb), max(v.x for v in wb); z0_, z1_ = min(v.z for v in wb), max(v.z for v in wb); yf = max(v.y for v in wb)
            _box("SignPlate", x0_ - 0.6, x1_ + 0.6, yf - 0.03, yf + 0.45, z0_ - 0.28, z1_ + 0.28, plate, col)
            continue
        ld = bpy.data.lights.new("SignWash", "AREA"); ld.energy = 120; ld.color = (1.0, 0.86, 0.66)
        ld.shape = "RECTANGLE"; ld.size = 14 if nm == "TextPlus039" else 4; ld.size_y = 2.5 if nm == "TextPlus039" else 4
        try: ld.cycles.cast_shadow = False
        except Exception: pass
        lo = bpy.data.objects.new("SignWash", ld); lo.location = wc + nrm * 4.0 + Vector((0, 0, -1.5))
        lo.rotation_euler = (-nrm).to_track_quat("-Z", "Y").to_euler(); col.objects.link(lo)
    log(f"site v3: signage boosted on {signs[:12]}")
site_v3()

# ================================================================ landscape v4: terrace garden, rooftop gardens, ground beds (matched to the client's renders)
import zipfile as _zipfile, bmesh as _bm
from mathutils import noise as _noise
_LS = {}
def _ls_lib():
    if "lib" in _LS: return _LS["lib"]
    lib = bpy.data.collections.new("LS_lib"); scene.collection.children.link(lib)
    def _excl(lc):
        for c in lc.children:
            if c.collection == lib: c.exclude = True; return True
            if _excl(c): return True
    _excl(bpy.context.view_layer.layer_collection)
    _LS["lib"] = lib; return lib
def _proto(name):
    c = bpy.data.collections.new(name); _ls_lib().children.link(c); return c
def _ph(name):
    d = os.path.join(RENDER_DIR, "assets", "ph"); dd = os.path.join(d, name); z = os.path.join(d, f"pha_{name}.zip")
    if not os.path.isdir(dd) and os.path.exists(z): _zipfile.ZipFile(z).extractall(d)
    bl = os.path.join(dd, f"{name}_1k.blend")
    if not os.path.exists(bl): log(f"landscape: missing {name}"); return None
    c = bpy.data.collections.get("PH_" + name)
    if c: return c
    with bpy.data.libraries.load(bl, link=False) as (src, dst): dst.objects = list(src.objects)
    c = _proto("PH_" + name)
    objs = [o for o in dst.objects if o is not None]
    roots = [o for o in objs if o.parent is None and o.type in ("MESH", "EMPTY")]
    # Poly Haven files often hold several variants side by side: keep the one standing at (or nearest to) the origin
    def _rdist(o): return Vector((o.matrix_world.translation.x, o.matrix_world.translation.y)).length
    near = [o for o in roots if _rdist(o) < 0.35] or sorted(roots, key=_rdist)[:1]
    keep = set()
    for r in near:
        keep.add(r); keep.update(r.children_recursive)
    for o in keep:
        if o.type in ("MESH", "EMPTY", "CURVE"): c.objects.link(o)
    for r in near:
        if _rdist(r) >= 0.35: r.location.x = 0; r.location.y = 0
    log(f"landscape: {name}: {len(roots)} roots, kept {[o.name for o in near]}")
    for im in bpy.data.images:
        if im.filepath and not im.packed_file and not os.path.exists(bpy.path.abspath(im.filepath)):
            cand = os.path.join(dd, "textures", os.path.basename(im.filepath.replace("\\", "/")))
            if os.path.exists(cand): im.filepath = cand; im.reload()
            elif name in im.filepath: log(f"landscape: texture not found {im.filepath}")
    return c
def _inst(coll, x, y, z, rot=0.0, s=1.0, col=None):
    if coll is None: return None
    e = bpy.data.objects.new(coll.name + "_i", None); e.instance_type = "COLLECTION"; e.instance_collection = coll
    e.location = (x, y, z); e.rotation_euler = (0, 0, rot); e.scale = (s, s, s) if not isinstance(s, tuple) else s
    (col or _LS["col"]).objects.link(e); return e
def _obj(name, verts, faces, mat, col=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    if mat: me.materials.append(mat)
    o = bpy.data.objects.new(name, me); o.location = loc; (col or _LS["col"]).objects.link(o); return o
def _cyl(name, r1, r2, h, segs, mat, loc, col=None, cap=True):
    bm = _bm.new(); _bm.ops.create_cone(bm, cap_ends=cap, segments=segs, radius1=r1, radius2=r2, depth=h)
    for v in bm.verts: v.co.z += h / 2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    if mat: me.materials.append(mat)
    o = bpy.data.objects.new(name, me); o.location = loc; (col or _LS["col"]).objects.link(o); return o
def _leaf_mat(name, c1, c2, bump=0.7):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 6
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 38.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"]); nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (*c1, 1); cr.color_ramp.elements[1].color = (*c2, 1)
    mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MULTIPLY"; nt.links.new(nz.outputs["Fac"], mx.inputs[0]); nt.links.new(vo.outputs["Distance"], mx.inputs[1])
    nt.links.new(mx.outputs[0], cr.inputs["Fac"]); nt.links.new(cr.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.62
    try: bs.inputs["Subsurface Weight"].default_value = 0.06; bs.inputs["Subsurface Radius"].default_value = (0.2, 0.4, 0.1)
    except Exception: pass
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = 0.05
    nt.links.new(vo.outputs["Distance"], bp.inputs["Height"]); nt.links.new(bp.outputs[0], bs.inputs["Normal"])
    return m
def _blob(name, verts_fn, mat, col, amp=0.06, freq=3.0, segs=20, rings=14):
    """A leafy solid (cypress, ball, vine) from a radius profile r(t), t in 0..1 along height, with a noisy surface."""
    verts, faces = [], []
    H, prof = verts_fn
    for i in range(rings + 1):
        t = i / rings; r = prof(t)
        for j in range(segs):
            a = 2 * math.pi * j / segs; p = Vector((math.cos(a) * r, math.sin(a) * r, t * H))
            n = _noise.noise(p * freq) * amp + _noise.noise(p * freq * 3.1) * amp * 0.4
            p += Vector((math.cos(a), math.sin(a), 0)) * n; verts.append(p)
    for i in range(rings):
        for j in range(segs):
            a, b = i * segs + j, i * segs + (j + 1) % segs
            faces.append((a, b, b + segs, a + segs))
    verts.append(Vector((0, 0, H * 1.0 + amp))); top = len(verts) - 1
    for j in range(segs): faces.append((rings * segs + j, rings * segs + (j + 1) % segs, top))
    o = _obj(name, verts, faces, mat, col)
    for p in o.data.polygons: p.use_smooth = True
    o.modifiers.new("sub", "SUBSURF").levels = 1
    return o
def _ring_poly(cx, cy, rx, ry, rot=0.0, wob=0.12, n=48, seed=0.0):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n; w = 1 + wob * math.sin(2 * a + seed) + wob * 0.5 * math.sin(3 * a + seed * 2)
        x, y = math.cos(a) * rx * w, math.sin(a) * ry * w
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts
def _inside(pts, x, y):
    c = False; n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c
def _bed(name, pts, z, kerb_mat, soil_mat, h=0.38, w=0.16):
    """Raised bed with a dark stone kerb following an arbitrary outline."""
    n = len(pts); cx = sum(p[0] for p in pts) / n; cy = sum(p[1] for p in pts) / n
    verts, faces = [], []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy; L = math.hypot(dx, dy) or 1
        ix, iy = x - dx / L * w, y - dy / L * w
        verts += [(x, y, z), (x, y, z + h), (ix, iy, z + h), (ix, iy, z)]
    for k in range(n):
        a = 4 * k; b = 4 * ((k + 1) % n)
        faces += [(a, b, b + 1, a + 1), (a + 1, b + 1, b + 2, a + 2), (a + 2, b + 2, b + 3, a + 3)]
    _obj(name + "_kerb", verts, faces, kerb_mat)
    soil = [(x - (x - cx) * 0.02, y - (y - cy) * 0.02, z + h - 0.06) for (x, y) in pts]
    _obj(name + "_soil", soil, [tuple(range(n))], soil_mat)
    return z + h - 0.06
def _scatter(pts, z, protos, density, rnd, smin=0.8, smax=1.25, keep=None):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]; area += x1 * y2 - x2 * y1
    count = int(abs(area) / 2 * density); placed = 0; tries = 0
    tot = sum(w for _, w, _ in protos)
    while placed < count and tries < count * 6:
        tries += 1; x = rnd.uniform(min(xs), max(xs)); y = rnd.uniform(min(ys), max(ys))
        if not _inside(pts, x, y) or (keep and not keep(x, y)): continue
        r = rnd.uniform(0, tot); acc = 0
        for c, w, s in protos:
            acc += w
            if r <= acc: _inst(c, x, y, z, rnd.uniform(0, 6.28), s * rnd.uniform(smin, smax)); break
        placed += 1
    return placed
def _rect(x0, x1, y0, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
def _coll_ok(c):
    """False when any image used by the collection's materials is missing on disk (renders magenta)."""
    if c is None: return False
    for o in c.all_objects:
        for sl in getattr(o, "material_slots", []):
            m = sl.material
            if not (m and m.use_nodes): continue
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image and not n.image.packed_file and n.image.source == "FILE":
                    if not os.path.exists(bpy.path.abspath(n.image.filepath, library=n.image.library)):
                        log(f"landscape: skipping {c.name} (missing {os.path.basename(n.image.filepath)})"); return False
    return True
def _tweak(m, hue=0.5, sat=1.0, val=1.0, rough_add=0.0):
    nt = m.node_tree; bs = nt.nodes.get("Principled BSDF")
    if bs is None: return m
    lk = bs.inputs["Base Color"].links
    if lk and (hue != 0.5 or sat != 1.0 or val != 1.0):
        h = nt.nodes.new("ShaderNodeHueSaturation"); h.inputs["Hue"].default_value = hue; h.inputs["Saturation"].default_value = sat; h.inputs["Value"].default_value = val
        nt.links.new(lk[0].from_socket, h.inputs["Color"]); nt.links.new(h.outputs["Color"], bs.inputs["Base Color"])
    rl = bs.inputs["Roughness"].links
    if rough_add:
        if rl:
            ad = nt.nodes.new("ShaderNodeMath"); ad.operation = "ADD"; ad.use_clamp = True; ad.inputs[1].default_value = rough_add
            nt.links.new(rl[0].from_socket, ad.inputs[0]); nt.links.new(ad.outputs[0], bs.inputs["Roughness"])
        else: bs.inputs["Roughness"].default_value = min(1.0, bs.inputs["Roughness"].default_value + rough_add)
    return m
def _recolor(src, name, **kw):
    """Copy of a plant collection with its materials re-coloured (red / magenta variants of the same plant)."""
    if src is None: return None
    c = _proto(name); cache = {}
    for o in src.all_objects:
        if o.type != "MESH": continue
        n = o.copy(); n.data = o.data.copy(); c.objects.link(n)
        if n.parent and n.parent.name not in [x.name for x in src.all_objects]: n.parent = None
        for i, m in enumerate(n.data.materials):
            if m is None: continue
            if m.name not in cache: cache[m.name] = _tweak(m.copy(), **kw)
            n.data.materials[i] = cache[m.name]
    return c

def landscape_v4():
    rnd = __import__("random").Random(11)
    col = bpy.data.collections.new("landscape_v4"); scene.collection.children.link(col); _LS["col"] = col
    # ---------------- materials
    deck = _tweak(_mat("LS_Deck", tex="herringbone_parquet", scale=1.1, tint=(1.0, 0.9, 0.72)), sat=0.75, val=1.9, rough_add=0.3)
    lawn = _tweak(_mat("LS_Lawn", tex="leafy_grass", scale=0.55, tint=(0.62, 1.0, 0.4)), sat=1.12, val=1.02)
    hexp = _tweak(_mat("LS_Cobble", tex="interlocking_concrete_pavers", scale=0.55, tint=(0.82, 0.8, 0.77)), sat=0.12, val=1.1)
    kerb = _mat("LS_Kerb", base=(0.07, 0.07, 0.075), rough=0.45)
    soil = _mat("LS_Soil", base=(0.09, 0.06, 0.04), rough=0.95)
    stone = bpy.data.materials.get("ST_Limestone") or _mat("LS_Stone", base=(0.78, 0.72, 0.6), rough=0.6)
    white = _mat("LS_Planter", base=(0.86, 0.85, 0.82), rough=0.4)
    wood = _mat("LS_Wood", base=(0.22, 0.12, 0.06), rough=0.55)
    bronze = _mat("LS_Bronze", base=(0.05, 0.045, 0.04), rough=0.35, metal=0.7)
    fabric = _mat("LS_Fabric", base=(0.9, 0.86, 0.76), rough=0.85)
    glow = _mat("LS_Glow", base=(1.0, 0.92, 0.8), rough=0.3, emit=(1.0, 0.82, 0.58), estr=4.0)
    glass = bpy.data.materials.get("LS_GlassRoof")
    if glass is None:
        glass = bpy.data.materials.new("LS_GlassRoof"); glass.use_nodes = True; b = glass.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.05, 0.06, 0.07, 1); b.inputs["Roughness"].default_value = 0.04
        b.inputs["Transmission Weight"].default_value = 0.55; b.inputs["IOR"].default_value = 1.45
    rail = bpy.data.materials.get("LS_Rail")
    if rail is None:
        rail = bpy.data.materials.new("LS_Rail"); rail.use_nodes = True; b = rail.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.8, 0.88, 0.9, 1); b.inputs["Roughness"].default_value = 0.02; b.inputs["Transmission Weight"].default_value = 0.92
    water = bpy.data.materials.get("LS_Water")
    if water is None:
        water = bpy.data.materials.new("LS_Water"); water.use_nodes = True; nt = water.node_tree; b = nt.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (0.25, 0.42, 0.45, 1); b.inputs["Roughness"].default_value = 0.03; b.inputs["Transmission Weight"].default_value = 0.8
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9; bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs[0], b.inputs["Normal"])
    hedge = _leaf_mat("LS_Hedge", (0.035, 0.09, 0.02), (0.11, 0.22, 0.05))
    cyp = _leaf_mat("LS_Cypress", (0.02, 0.06, 0.02), (0.07, 0.15, 0.04), 0.9)
    box = _leaf_mat("LS_Boxwood", (0.05, 0.13, 0.03), (0.16, 0.3, 0.07))
    vine = _leaf_mat("LS_Vine", (0.03, 0.1, 0.02), (0.1, 0.24, 0.05), 1.0)
    # ---------------- prototypes
    P = {}
    c = _proto("LS_cypress"); _blob("cypress", (3.6, lambda t: 0.48 * max(0.0, math.sin(math.pi * min(1, 0.06 + t * 0.94))) ** 0.55), cyp, c, amp=0.07, freq=2.4); P["cypress"] = c
    c = _proto("LS_ball"); o = _blob("ball", (1.1, lambda t: 0.6 * math.sin(math.pi * t) ** 0.8), box, c, amp=0.05, freq=3.5); P["ball"] = c
    c = _proto("LS_umbrella")
    _cyl("u_pole", 0.03, 0.03, 2.55, 10, bronze, (0, 0, 0), c); _cyl("u_base", 0.28, 0.24, 0.08, 16, bronze, (0, 0, 0), c)
    hu, s2 = 2.2, 1.55
    _obj("u_canopy", [(-s2, -s2, hu), (s2, -s2, hu), (s2, s2, hu), (-s2, s2, hu), (0, 0, hu + 0.55)], [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], fabric, c)
    _obj("u_valance", [(-s2, -s2, hu - 0.14), (s2, -s2, hu - 0.14), (s2, s2, hu - 0.14), (-s2, s2, hu - 0.14), (-s2, -s2, hu), (s2, -s2, hu), (s2, s2, hu), (-s2, s2, hu)],
         [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], fabric, c)
    for o in c.objects:
        if o.name.startswith("u_canopy") or o.name.startswith("u_valance"): o.modifiers.new("t", "SOLIDIFY").thickness = 0.015
    P["umbrella"] = c
    c = _proto("LS_bollard"); _box("b_post", -0.09, 0.09, -0.09, 0.09, 0, 0.78, bronze, c); _box("b_lamp", -0.08, 0.08, -0.08, 0.08, 0.78, 0.9, glow, c)
    _box("b_cap", -0.1, 0.1, -0.1, 0.1, 0.9, 0.93, bronze, c); P["bollard"] = c
    c = _proto("LS_planter"); _box("p_box", -0.4, 0.4, -0.4, 0.4, 0, 0.62, white, c); _box("p_soil", -0.36, 0.36, -0.36, 0.36, 0.55, 0.6, soil, c); P["planter"] = c
    c = _proto("LS_round_planter"); _cyl("rp", 0.6, 0.5, 0.7, 24, white, (0, 0, 0), c); _cyl("rps", 0.55, 0.55, 0.66, 24, soil, (0, 0, 0), c); P["rplanter"] = c
    c = _proto("LS_pergola")
    for sx in (-1.5, 1.5):
        for sy in (-1.0, 1.0):
            _box("pg_post", sx - 0.07, sx + 0.07, sy - 0.07, sy + 0.07, 0, 2.6, wood, c)
            _blob("pg_vine", (2.4, lambda t: 0.16 + 0.05 * math.sin(t * 9)), vine, c, amp=0.05, freq=4).location = (sx, sy, 0)
    for sy in (-1.0, 1.0): _box("pg_beam", -1.8, 1.8, sy - 0.06, sy + 0.06, 2.45, 2.62, wood, c)
    for k in range(9): xk = -1.6 + k * 0.4; _box("pg_raft", xk - 0.03, xk + 0.03, -1.25, 1.25, 2.62, 2.72, wood, c)
    _blob("pg_canopy", (0.35, lambda t: 1.0 * math.sin(math.pi * t) ** 0.4), vine, c, amp=0.12, freq=2).location = (0.6, -0.3, 2.6)
    _box("pg_bench", -1.0, 1.0, -0.22, 0.22, 0.42, 0.48, wood, c); _box("pg_bl", -0.95, -0.85, -0.2, 0.2, 0, 0.42, wood, c); _box("pg_br", 0.85, 0.95, -0.2, 0.2, 0, 0.42, wood, c)
    P["pergola"] = c
    tbl = _ph("round_wooden_table_01"); chr_ = _ph("gallinera_chair"); dine = _ph("outdoor_table_chair_set_01")
    flowers = [(_ph("flower_gazania"), 3, 1.6), (_ph("shrub_sorrel_01"), 2, 1.0), (_ph("periwinkle_plant"), 2, 1.4),
               (bpy.data.collections.get("BK_geranium"), 4, 1.3), (bpy.data.collections.get("BK_hydrangea_red"), 2, 0.55),
               (bpy.data.collections.get("BK_roses_yellow"), 2, 0.5)]
    flowers = [f for f in flowers if _coll_ok(f[0])]
    gz_ = _ph("flower_gazania"); hy_ = bpy.data.collections.get("BK_hydrangea_red")
    if _coll_ok(gz_):   # the client's beds are red / yellow / white / magenta: colour variants of the same flower
        flowers += [(_recolor(gz_, "LS_flower_red", hue=0.43, sat=1.3, val=0.95), 4, 1.6), (_recolor(gz_, "LS_flower_magenta", hue=0.2, sat=1.2, val=1.05), 2, 1.6)]
    shrubs = [(_ph("shrub_02"), 2, 0.9), (_ph("shrub_01"), 1, 0.7), (bpy.data.collections.get("BK_abelia_small"), 2, 0.8)]
    shrubs = [f for f in shrubs if _coll_ok(f[0])]
    log(f"landscape: flowers {[f[0].name for f in flowers]}, shrubs {[f[0].name for f in shrubs]}")
    spiral = bpy.data.collections.get("BK_cypress_spiral"); palm = bpy.data.collections.get("BK_palm_dense") or bpy.data.collections.get("BK_palm_tall")
    palm2 = bpy.data.collections.get("BK_palm_tall") or palm
    # purple flowering tree (crape myrtle / bougainvillea): a re-coloured copy of the broadleaf tree
    purple = None; src = bpy.data.collections.get("BK_broadleaf")
    if src:
        purple = _proto("LS_purple_tree")
        for o in src.all_objects:
            if o.type != "MESH": continue
            n = o.copy(); n.data = o.data.copy(); purple.objects.link(n); n.parent = None; n.matrix_world = o.matrix_world.copy()
            for i, m in enumerate(n.data.materials):
                if m and _re.search(r"leaf|leaves|foliage", m.name, _re.I):
                    pm = m.copy(); pm.name = m.name + "_purple"; nt = pm.node_tree; bs = nt.nodes.get("Principled BSDF")
                    if bs:
                        lk = bs.inputs["Base Color"].links
                        hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.inputs["Hue"].default_value = 0.06; hsv.inputs["Saturation"].default_value = 1.5; hsv.inputs["Value"].default_value = 1.35
                        if lk: nt.links.new(lk[0].from_socket, hsv.inputs["Color"])
                        else: hsv.inputs["Color"].default_value = bs.inputs["Base Color"].default_value
                        nt.links.new(hsv.outputs["Color"], bs.inputs["Base Color"])
                    n.data.materials[i] = pm
    def cafe(x, y, z, rot=0.0, n=4):
        _inst(tbl, x, y, z, rot)
        for k in range(n):
            a = rot + 2 * math.pi * k / n
            _inst(chr_, x + math.cos(a) * 0.82, y + math.sin(a) * 0.82, z, a + math.pi / 2)
    def dining(x, y, z, rot=0.0, umb=True):
        _inst(dine, x, y, z, rot)
        if umb: _inst(P["umbrella"], x, y, z, rot)
    def bollards(x0, y0, x1, y1, step, z):
        L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / step))
        for k in range(n + 1): _inst(P["bollard"], x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, z)
    def lawn_slab(x0, x1, y0, y1, z): _box("LS_lawn", x0, x1, y0, y1, z, z + 0.05, lawn, col)
    def deck_slab(x0, x1, y0, y1, z): _box("LS_deck", x0, x1, y0, y1, z, z + 0.04, deck, col)

    # ================= podium terrace (deck at 24.77 m): courtyard between the towers + strip behind the pediment
    Z = 24.79
    deck_slab(-181.0, -134.0, -24.4, -21.6, Z)                 # walkway across the terrace
    deck_slab(-159.2, -156.8, -21.6, -12.6, Z)                 # spine into the courtyard
    deck_slab(-165.0, -151.0, -12.6, -11.0, Z)                 # cross walk
    deck_slab(-165.0, -163.2, -11.0, -0.8, Z); deck_slab(-152.8, -151.0, -11.0, -0.8, Z)   # U around the skylight
    lawn_slab(-165.0, -159.2, -21.6, -12.6, Z); lawn_slab(-156.8, -151.0, -21.6, -12.6, Z)
    lawn_slab(-163.2, -152.8, -11.0, -6.8, Z); lawn_slab(-163.2, -161.6, -6.8, -0.8, Z); lawn_slab(-154.4, -152.8, -6.8, -0.8, Z)
    lawn_slab(-170.6, -145.4, -31.2, -24.4, Z); lawn_slab(-181.0, -178.3, -31.2, -24.4, Z); lawn_slab(-137.7, -134.0, -31.2, -24.4, Z)
    # skylight with a flower border
    zf = _bed("LS_skyborder", _rect(-161.6, -154.4, -6.8, -0.8), Z, kerb, soil, h=0.3, w=0.12)
    _scatter(_rect(-161.5, -154.5, -6.7, -0.9), zf, flowers, 9, rnd, keep=lambda x, y: not (-161.0 < x < -155.0 and -6.2 < y < -1.4))
    _box("LS_sky_base", -161.0, -155.0, -6.2, -1.4, Z, Z + 0.55, stone, col)
    zb = Z + 0.55; hx0, hx1, hy0, hy1, hr = -160.9, -155.1, -6.1, -1.5, 1.7
    _obj("LS_sky_glass", [(hx0, hy0, zb), (hx1, hy0, zb), (hx1, hy1, zb), (hx0, hy1, zb), (-158.0, hy0 + 1.2, zb + hr), (-158.0, hy1 - 1.2, zb + hr)],
         [(0, 1, 4), (1, 2, 5, 4), (2, 3, 5), (3, 0, 4, 5)], glass, col)
    for (a, b) in (((hx0, hy0), (-158.0, hy0 + 1.2)), ((hx1, hy0), (-158.0, hy0 + 1.2)), ((hx1, hy1), (-158.0, hy1 - 1.2)), ((hx0, hy1), (-158.0, hy1 - 1.2))):
        L = math.hypot(b[0] - a[0], b[1] - a[1]); v = Vector((b[0] - a[0], b[1] - a[1], hr)); m = (Vector((a[0], a[1], zb)) + Vector((b[0], b[1], zb + hr))) / 2
        o = _box("LS_sky_hip", -0.04, 0.04, -0.04, 0.04, -v.length / 2, v.length / 2, bronze, col); o.location = m; o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    _box("LS_sky_ridge", -158.05, -157.95, hy0 + 1.2, hy1 - 1.2, zb + hr - 0.05, zb + hr + 0.05, bronze, col)
    for k in range(1, 5):
        yk = hy0 + 1.2 + (hy1 - hy0 - 2.4) * k / 5
        for side in (-1, 1):
            v = Vector((side * 2.9, 0, hr)); m = Vector((-158.0 + side * 1.45, yk, zb + hr / 2))
            o = _box("LS_sky_raft", -0.025, 0.025, -0.025, 0.025, -v.length / 2, v.length / 2, bronze, col); o.location = m; o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    # furniture
    dining(-162.1, -17.4, Z + 0.05, 0.0); dining(-153.9, -17.4, Z + 0.05, 0.0)
    for xx in (-161.2, -158.0, -154.8): cafe(xx, -8.8, Z + 0.05, 0.3)
    for xx in (-167.6, -162.6, -153.4, -148.4): cafe(xx, -28.0, Z + 0.05, 0.0)
    _inst(P["pergola"], -158.0, -28.6, Z + 0.05)
    dining(-179.6, -28.0, Z + 0.05, math.pi / 2)
    _box("LS_kiosk", -137.4, -134.6, -30.9, -30.1, Z, Z + 1.1, white, col); _box("LS_kiosk_top", -137.5, -134.5, -31.0, -30.0, Z + 1.1, Z + 1.16, wood, col)
    _box("LS_kiosk_back", -137.4, -134.6, -31.2, -31.0, Z, Z + 2.3, wood, col); cafe(-136.0, -27.0, Z + 0.05, 0.4, 3)
    for (px, py) in ((-169.6, -25.3), (-146.4, -25.3), (-163.9, -20.2), (-152.1, -20.2)):
        _inst(P["rplanter"], px, py, Z); _inst(palm, px, py, Z + 0.65, rnd.uniform(0, 6.28), 0.34)
    for yy in range(-19, -1, 3):
        for xx in (-164.55, -151.45):
            _inst(P["planter"], xx, yy + 0.5, Z); _scatter(_rect(xx - 0.34, xx + 0.34, yy + 0.16, yy + 0.84), Z + 0.6, shrubs, 6, rnd, 0.7, 1.0)
    for xx in range(-180, -133, 3):
        if -166 < xx < -150: continue
        _inst(P["planter"], xx + 0.5, -21.15, Z); _scatter(_rect(xx + 0.16, xx + 0.84, -21.5, -20.8), Z + 0.6, shrubs, 6, rnd, 0.7, 1.0)
    _inst(P["pergola"], -163.3, -2.4, Z + 0.05, math.pi / 2, 0.75); _inst(P["pergola"], -152.7, -2.4, Z + 0.05, math.pi / 2, 0.75)
    bollards(-159.5, -21.0, -159.5, -13.0, 2.7, Z); bollards(-156.5, -21.0, -156.5, -13.0, 2.7, Z)
    bollards(-180.5, -24.65, -135.0, -24.65, 3.5, Z); bollards(-165.3, -11.0, -165.3, -1.2, 3.3, Z); bollards(-150.7, -11.0, -150.7, -1.2, 3.3, Z)

    # ================= tower rooftop gardens (roof at 79.03 m)
    Z2 = 79.05
    for (rx0, rx1) in ((-181.0, -166.0), (-150.0, -135.0)):
        ry0, ry1 = -18.0, 2.0; cxr = (rx0 + rx1) / 2
        deck_slab(rx0 + 0.3, rx1 - 0.3, ry0 + 0.3, ry1, Z2)
        lawn_slab(rx0 + 1.6, rx1 - 1.6, ry0 + 1.6, ry1 - 1.4, Z2 + 0.01)
        deck_slab(cxr - 1.1, cxr + 1.1, ry0 + 1.6, ry1 - 1.4, Z2 + 0.02)
        dining(cxr - 3.6, ry0 + 5.0, Z2 + 0.06, 0.0); dining(cxr + 3.6, ry0 + 5.0, Z2 + 0.06, 0.0)
        for yy in (ry0 + 10.5, ry0 + 15.0):
            cafe(cxr - 3.8, yy, Z2 + 0.06, 0.2); cafe(cxr + 3.8, yy, Z2 + 0.06, 0.6)
        for (px, py) in ((rx0 + 1.0, ry0 + 1.0), (rx1 - 1.0, ry0 + 1.0), (rx0 + 1.0, ry1 - 1.0), (rx1 - 1.0, ry1 - 1.0)):
            _inst(P["rplanter"], px, py, Z2); _inst(palm, px, py, Z2 + 0.65, rnd.uniform(0, 6.28), 0.42)
        for k in range(6):
            yy = ry0 + 3.0 + k * 2.8
            _inst(P["planter"], rx0 + 0.75, yy, Z2); _inst(P["planter"], rx1 - 0.75, yy, Z2)
            _scatter(_rect(rx0 + 0.41, rx0 + 1.09, yy - 0.34, yy + 0.34), Z2 + 0.6, flowers + shrubs, 8, rnd)
            _scatter(_rect(rx1 - 1.09, rx1 - 0.41, yy - 0.34, yy + 0.34), Z2 + 0.6, flowers + shrubs, 8, rnd)
        bollards(cxr - 1.3, ry0 + 1.8, cxr - 1.3, ry1 - 1.6, 3.2, Z2); bollards(cxr + 1.3, ry0 + 1.8, cxr + 1.3, ry1 - 1.6, 3.2, Z2)
        for (a, b) in (((rx0 + 0.1, ry0 + 0.1), (rx1 - 0.1, ry0 + 0.1)), ((rx0 + 0.1, ry0 + 0.1), (rx0 + 0.1, ry1)), ((rx1 - 0.1, ry0 + 0.1), (rx1 - 0.1, ry1))):
            if abs(a[0] - b[0]) > abs(a[1] - b[1]):
                _box("LS_rail", a[0], b[0], a[1] - 0.012, a[1] + 0.012, Z2, Z2 + 1.1, rail, col); _box("LS_railtop", a[0], b[0], a[1] - 0.03, a[1] + 0.03, Z2 + 1.1, Z2 + 1.14, bronze, col)
            else:
                _box("LS_rail", a[0] - 0.012, a[0] + 0.012, a[1], b[1], Z2, Z2 + 1.1, rail, col); _box("LS_railtop", a[0] - 0.03, a[0] + 0.03, a[1], b[1], Z2 + 1.1, Z2 + 1.14, bronze, col)
    # back roof: rooftop restaurant around the dome
    deck_slab(-170.7, -145.3, 2.3, 19.7, Z2)
    for yy in (13.0, 17.0):
        for k, xx in enumerate((-168.4, -164.3, -160.2, -156.1, -152.0, -147.9)):
            if k % 2 == 0: dining(xx, yy, Z2 + 0.05, 0.0)
            else: cafe(xx, yy, Z2 + 0.05, 0.3)
    for (xx, yy) in ((-168.6, 5.0), (-152.5, 5.0), (-148.4, 8.5), (-168.6, 9.0)): cafe(xx, yy, Z2 + 0.05, 0.5)
    for (px, py) in ((-170.0, 19.0), (-146.0, 19.0), (-170.0, 2.9), (-146.0, 2.9)):
        _inst(P["rplanter"], px, py, Z2); _inst(palm, px, py, Z2 + 0.65, rnd.uniform(0, 6.28), 0.4)
    for xx in range(-167, -147, 3):
        _inst(P["planter"], xx + 0.5, 19.35, Z2); _scatter(_rect(xx + 0.16, xx + 0.84, 19.0, 19.7), Z2 + 0.6, flowers + shrubs, 8, rnd)

    # ================= ground: facade beds, kidney beds, fountain, hedges, purple trees
    gz = lambda x, y: _ground_z(x, y)
    # client front render: open cobbled forecourt with parked cars, clear shopfronts, potted balls at the piers,
    # a cypress at the west end, magenta bougainvillea standards, a flowering-shrub border along the road
    zfc = gz(CX, -40.0)
    pot = _mat("LS_Pot", base=(0.13, 0.12, 0.11), rough=0.4)
    for px in (-180.2, -174.25, -167.5, -160.75, -155.25, -148.25, -141.75, -135.6):
        _cyl("LS_pierpot", 0.32, 0.26, 0.42, 24, pot, (px, -33.75, gz(px, -33.75)))
        _inst(P["ball"], px, -33.75, gz(px, -33.75) + 0.4, rnd.uniform(0, 6), 0.55)
    for cxp in (-181.3, -173.0): _inst(P["cypress"], cxp, -34.2, gz(cxp, -34.2), 0, 0.95)
    leafm = _leaf_mat("LS_BougLeaf", (0.03, 0.1, 0.02), (0.1, 0.25, 0.05), 0.9)
    bloom = _leaf_mat("LS_BougBloom", (0.42, 0.01, 0.1), (0.85, 0.05, 0.3), 1.1)
    bg = _proto("LS_bougainvillea")
    _cyl("bg_trunk", 0.07, 0.05, 2.2, 10, _mat("LS_Bark", base=(0.18, 0.12, 0.08), rough=0.85), (0, 0, 0), bg)
    _blob("bg_leaf", (1.5, lambda t: 0.75 * math.sin(math.pi * t) ** 0.7), leafm, bg, amp=0.12, freq=2.6).location = (0, 0, 1.6)
    _blob("bg_bloom", (0.7, lambda t: 0.95 * math.sin(math.pi * (0.5 + 0.5 * t)) ** 0.5), bloom, bg, amp=0.16, freq=3.4).location = (0, 0, 2.7)
    for (bx_, by_) in ((-148.25, -34.6), (-135.6, -34.6)):
        _cyl("LS_bgpot", 0.5, 0.4, 0.55, 24, pot, (bx_, by_, gz(bx_, by_))); _inst(bg, bx_, by_, gz(bx_, by_) + 0.5, rnd.uniform(0, 6), 1.0)
    # palms + shrubs at the west corner by the fountain, flowering border along the road between the drive entrances
    _inst(palm, -182.4, -39.0, gz(-182.4, -39.0), 1.0, 0.45); _inst(palm2, -183.0, -42.5, gz(-183.0, -42.5), 2.0, 0.4)
    for (x0_, x1_) in ((-170.7, -165.0), (-150.0, -145.4)):
        _box("LS_hedge", x0_, x1_, -50.5, -49.7, gz((x0_ + x1_) / 2, -50.1), gz((x0_ + x1_) / 2, -50.1) + 0.8, hedge, col)
    zb = _bed("LS_roadbed", _rect(-165.0, -150.0, -50.6, -48.6), gz(-157.5, -49.6), kerb, soil, h=0.3, w=0.12)
    hyd = bpy.data.collections.get("BK_hydrangea_red")
    for k in range(9):
        xx = -164.2 + k * 1.75
        if _coll_ok(hyd) and k % 2 == 0: _inst(hyd, xx, -49.6 + rnd.uniform(-0.3, 0.3), zb, rnd.uniform(0, 6), 0.75)
        else: _inst(P["ball"], xx, -49.6, zb, rnd.uniform(0, 6), 0.9)
    _scatter(_rect(-164.8, -150.2, -50.45, -48.75), zb, flowers, 6, rnd)
    # parked cars, nose to the shops, as in the client's render
    cars = sorted([c for c in bpy.data.collections if c.name.startswith("BK_") and c.get("kind") == "car" and not _re.search("bus", c.name, _re.I)], key=lambda c: c.name)
    def park(c, x, y, yaw):
        pts = [o.matrix_world @ Vector(v) for o in c.all_objects if o.type == "MESH" for v in o.bound_box]
        if not pts: return
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        ctr = (lo + hi) / 2 - c.instance_offset; base = 0.0 if (hi.y - lo.y) >= (hi.x - lo.x) else math.pi / 2
        a = base + yaw; off = Matrix.Rotation(a, 3, "Z") @ Vector((ctr.x, ctr.y, 0))
        _inst(c, x - off.x, y - off.y, gz(x, y) - (lo.z - c.instance_offset.z), a, 1.0)
    for k, (x, y, yaw) in enumerate(((-177.2, -42.4, 0.08), (-170.6, -44.6, -0.12), (-158.6, -40.9, 1.45), (-148.4, -41.6, 0.05), (-144.2, -42.2, -0.06), (-139.8, -41.4, 0.1))):
        if cars: park(cars[(k * 3 + 1) % len(cars)], x, y, yaw + (math.pi if k % 2 else 0.0))
    log(f"landscape: {len(cars)} car models for the forecourt")
    # tiered fountain at the left of the forecourt
    fx, fy = -178.6, -45.0; fz = gz(fx, fy); log(f"landscape: fountain z={fz:.2f}")
    _cyl("LS_f_pool", 2.3, 2.3, 0.5, 48, stone, (fx, fy, fz)); _cyl("LS_f_water", 2.1, 2.1, 0.46, 48, water, (fx, fy, fz + 0.02))
    _cyl("LS_f_stem", 0.32, 0.22, 1.25, 24, stone, (fx, fy, fz)); _cyl("LS_f_bowl1", 0.35, 1.05, 0.25, 32, stone, (fx, fy, fz + 1.2))
    _cyl("LS_f_w1", 0.95, 0.95, 0.04, 32, water, (fx, fy, fz + 1.42)); _cyl("LS_f_stem2", 0.14, 0.1, 0.65, 16, stone, (fx, fy, fz + 1.45))
    _cyl("LS_f_bowl2", 0.15, 0.5, 0.16, 24, stone, (fx, fy, fz + 2.05)); _cyl("LS_f_fin", 0.09, 0.02, 0.45, 12, stone, (fx, fy, fz + 2.2))
    fl = _ring_poly(fx, fy, 3.3, 3.3, 0, 0.02, 40)
    _scatter(fl, fz + 0.02, flowers, 6, rnd, keep=lambda x, y: math.hypot(x - fx, y - fy) > 2.45)
    # clipped hedge along Pine Avenue (replaces the low front wall) and at the drive
    for (hx0, hx1) in ((-184.6, -176.7), (-139.4, -128.2)):
        _box("LS_hedge", hx0, hx1, -50.5, -49.7, gz((hx0 + hx1) / 2, -50.1), gz((hx0 + hx1) / 2, -50.1) + 1.0, hedge, col)
    # purple flowering trees by the hotel drive (as in the client's renders)
    for (tx, ty, s) in ((-131.6, -45.4, 0.55), (-124.0, -36.0, 0.6), (-124.0, -4.0, 0.55)):
        _inst(purple, tx, ty, gz(tx, ty), rnd.uniform(0, 6.28), s)
    # hex cobble on the forecourt plate
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name == "Line082": o.data.materials.clear(); o.data.materials.append(hexp)
    for o in bpy.data.objects:   # the client's frontage is open: hedge + beds, no gate pillars
        if _re.match(r"(GatePillar|GateLamp|GateGlow)", o.name): o.hide_render = True
    log(f"landscape v4: {len(col.objects)} objects")
    _LS.update(flowers=flowers, shrubs=shrubs, palm=palm, palm2=palm2, tbl=tbl, chr=chr_, P=P)

landscape_v4()

# ---------------------------------------------------------------- interior v1: ground-floor lobby + shops, backing shells
def _bray(P, D, far=60.0):
    """First hit on the client's building geometry only (ignores landscape, plants, our own interior)."""
    dg = bpy.context.evaluated_depsgraph_get(); B = set(o.name for o in building_objects()); d0 = 0.0
    for _ in range(40):
        h, loc, nrm, idx, ob, mw = scene.ray_cast(dg, P + D * d0, D, distance=far - d0)
        if not h: return None
        if getattr(ob, "original", ob).name in B and not ob.hide_render: return loc
        d0 = (loc - P).length + 0.01
    return None
def _node_mat(name):
    m = bpy.data.materials.get(name)
    if m: return m, None, None
    m = bpy.data.materials.new(name); m.use_nodes = True; return m, m.node_tree, m.node_tree.nodes.get("Principled BSDF")
def _marble(name, c1, c2, vein=(0.35, 0.33, 0.3), scale=0.35, rough=0.09, tiles=0.0):
    m, nt, bs = _node_mat(name)
    if nt is None: return m
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale * 0.6, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 0.9; wv.inputs["Distortion"].default_value = 9.0
    wv.inputs["Detail"].default_value = 10.0; wv.inputs["Detail Roughness"].default_value = 0.62; nt.links.new(mp.outputs[0], wv.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements; e[0].position = 0.0; e[0].color = (*[v * 0.45 + c * 0.55 for v, c in zip(vein, c1)], 1); e[1].position = 0.022; e[1].color = (*c1, 1)
    e3 = e.new(0.6); e3.color = (*c2, 1); nt.links.new(wv.outputs["Fac"], cr.inputs["Fac"])
    last = cr.outputs["Color"]
    if tiles:
        br = nt.nodes.new("ShaderNodeTexBrick"); br.offset = 0.0; br.inputs["Scale"].default_value = 1.0 / tiles
        br.inputs["Mortar Size"].default_value = 0.004; br.inputs["Color1"].default_value = (1, 1, 1, 1); br.inputs["Color2"].default_value = (0.94, 0.93, 0.91, 1)
        br.inputs["Mortar"].default_value = (0.55, 0.52, 0.48, 1); br.inputs["Brick Width"].default_value = 1.0; br.inputs["Row Height"].default_value = 1.0
        nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
        nt.links.new(last, mx.inputs[6]); nt.links.new(br.outputs["Color"], mx.inputs[7]); last = mx.outputs[2]
    nt.links.new(last, bs.inputs["Base Color"]); bs.inputs["Roughness"].default_value = rough
    try: bs.inputs["Coat Weight"].default_value = 0.35; bs.inputs["Coat Roughness"].default_value = 0.03
    except Exception: pass
    return m
def _glass(name, tint=(0.92, 0.96, 0.95), rough=0.0, ior=1.5):
    m, nt, bs = _node_mat(name)
    if nt is None: return m
    bs.inputs["Base Color"].default_value = (*tint, 1); bs.inputs["Roughness"].default_value = rough
    bs.inputs["Transmission Weight"].default_value = 1.0; bs.inputs["IOR"].default_value = ior; return m
def _emit(name, col, strength):
    m, nt, bs = _node_mat(name)
    if nt is None: return m
    bs.inputs["Base Color"].default_value = (*col, 1); bs.inputs["Emission Color"].default_value = (*col, 1); bs.inputs["Emission Strength"].default_value = strength
    return m
def _torus_mesh(R, r, segs=48, rs=8, z=0.0):
    v, f = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for j in range(rs):
            b = 2 * math.pi * j / rs; rr = R + r * math.cos(b)
            v.append((math.cos(a) * rr, math.sin(a) * rr, z + r * math.sin(b)))
    for i in range(segs):
        for j in range(rs):
            f.append((i * rs + j, i * rs + (j + 1) % rs, ((i + 1) % segs) * rs + (j + 1) % rs, ((i + 1) % segs) * rs + j))
    return v, f
def _merge(parts):
    V, F = [], []
    for v, f in parts:
        o = len(V); V += v; F += [tuple(i + o for i in ff) for ff in f]
    return V, F
def _ico(c, r, sz=1.0, sub=1):
    bm = _bm.new(); _bm.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    v = [(c[0] + p.co.x, c[1] + p.co.y, c[2] + p.co.z * sz) for p in bm.verts]; f = [tuple(x.index for x in fc.verts) for fc in bm.faces]; bm.free(); return v, f
def _chandelier(name, x, y, ztop, R, tiers, col, gold, crystal, bulb, drop=2.6, power=900.0):
    """Tiered crystal chandelier: gold hoops, strands of crystal drops, candle bulbs and a warm light inside."""
    zc = ztop - drop
    rod = _cyl(name + "_rod", 0.03, 0.03, ztop - zc, 8, gold, (x, y, zc), col)
    hoops, drops, bulbs = [], [], []
    for t in range(tiers):
        rt = R * (1.0 - 0.3 * t); zt = zc + 0.55 * t
        hoops.append(_torus_mesh(rt, 0.025, 64, 6, zt)); hoops.append(_torus_mesh(rt * 0.55, 0.018, 40, 6, zt + 0.12))
        n = max(10, int(2 * math.pi * rt / 0.11))
        for k in range(n):
            a = 2 * math.pi * k / n; cx, cy = math.cos(a) * rt, math.sin(a) * rt
            for d in range(3 if t == 0 else 2):
                drops.append(_ico((cx, cy, zt - 0.09 - d * 0.13), 0.032, 1.8))
        nb = max(6, int(rt * 7))
        for k in range(nb):
            a = 2 * math.pi * (k + 0.5) / nb; bulbs.append(_ico((math.cos(a) * rt * 0.92, math.sin(a) * rt * 0.92, zt + 0.12), 0.035, 1.6))
    bowl = _ico((0, 0, zc - 0.25), R * 0.22, 0.9)
    v, f = _merge(hoops); _obj(name + "_gold", v, f, gold, col, (x, y, 0))
    v, f = _merge(drops + [bowl]); o = _obj(name + "_crystal", v, f, crystal, col, (x, y, 0))
    for pl in o.data.polygons: pl.use_smooth = True
    v, f = _merge(bulbs); _obj(name + "_bulbs", v, f, bulb, col, (x, y, 0))
    ld = bpy.data.lights.new(name + "_L", "POINT"); ld.energy = power; ld.color = (1.0, 0.78, 0.55); ld.shadow_soft_size = 0.2
    lo = bpy.data.objects.new(name + "_L", ld); lo.location = (x, y, zc + 0.3); col.objects.link(lo)
    for a in ("visible_camera", "visible_glossy", "visible_transmission"):   # the light glows through the crystals, never as a ball of its own
        try: setattr(lo, a, False)
        except Exception: pass
def _area(name, x, y, z, sx, sy, energy, col, colr=(1.0, 0.86, 0.7)):
    ld = bpy.data.lights.new(name, "AREA"); ld.shape = "RECTANGLE"; ld.size = sx; ld.size_y = sy; ld.energy = energy; ld.color = colr
    o = bpy.data.objects.new(name, ld); o.location = (x, y, z); col.objects.link(o)
    for a in ("visible_camera", "visible_glossy", "visible_transmission"):
        try: setattr(o, a, False)
        except Exception: pass
    return o

def interior_v1():
    col = bpy.data.collections.new("interior_v1"); scene.collection.children.link(col)
    rnd = __import__("random").Random(7)
    fl = _bray(Vector((CX, -25.0, 5.0)), Vector((0, 0, -1)), 10); zf = fl.z if fl else 0.15
    ce = _bray(Vector((CX, -25.0, zf + 1.0)), Vector((0, 0, 1)), 14); zc = ce.z if ce and zf + 5.0 < ce.z < zf + 12 else zf + 8.5
    log(f"interior: floor {zf:.2f}  ceiling {zc:.2f}")
    X0, X1, YG, YB = -180.4, -135.6, -29.2, -13.0     # interior box: glass line at YG, feature wall at YB
    nkill = 0
    for o in building_objects():
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        if max(v.x for v in bb) < X0 or min(v.x for v in bb) > X1 or max(v.y for v in bb) < YG or min(v.y for v in bb) > YB + 0.6 or min(v.z for v in bb) > zc: continue
        mw = o.matrix_world; bm = _bm.new(); bm.from_mesh(o.data)
        def _in(v):
            w = mw @ v.co
            return X0 + 0.3 <= w.x <= X1 - 0.3 and YG + 0.6 <= w.y <= YB + 0.6 and zf - 0.05 <= w.z <= zc + 0.05
        kill = [f for f in bm.faces if all(_in(v) for v in f.verts)]
        if kill:
            _bm.ops.delete(bm, geom=kill, context="FACES"); bm.to_mesh(o.data); nkill += len(kill)
        bm.free()
    log(f"interior: removed {nkill} bare partition faces from the shop floor")
    xa, xb = -167.5, -148.25                          # partitions on the piers: boutique | lobby | cafe
    # ---------- materials
    floor = _marble("IN_FloorMarble", (0.84, 0.8, 0.74), (0.76, 0.71, 0.64), scale=0.28, rough=0.07, tiles=1.2)
    wallm = _marble("IN_WallMarble", (0.78, 0.69, 0.56), (0.68, 0.58, 0.45), vein=(0.42, 0.33, 0.24), scale=1.0, rough=0.15)
    dark = _marble("IN_DarkMarble", (0.06, 0.055, 0.05), (0.12, 0.11, 0.1), vein=(0.75, 0.7, 0.62), scale=0.5, rough=0.08)
    gold = _mat("IN_Gold", base=(1.0, 0.74, 0.4), rough=0.22, metal=1.0)
    plaster = _mat("IN_Ceiling", base=(0.8, 0.74, 0.64), rough=0.8)
    velvet = _mat("IN_Velvet", base=(0.16, 0.09, 0.05), rough=0.9); cream = _mat("IN_Cream", base=(0.88, 0.84, 0.76), rough=0.85)
    rug = _mat("IN_Rug", base=(0.3, 0.2, 0.13), rough=0.95); walnut = _mat("IN_Walnut", base=(0.12, 0.065, 0.035), rough=0.35)
    glassf = _glass("IN_Storefront"); crystal = _glass("IN_Crystal", (1, 1, 1), 0.0, 1.62)
    bulb = _emit("IN_Bulb", (1.0, 0.78, 0.5), 30.0); cove = _emit("IN_Cove", (1.0, 0.8, 0.58), 5.0)
    onyx, nt, bs = _node_mat("IN_Onyx")
    if nt:
        tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexWave"); nz.inputs["Scale"].default_value = 1.8; nz.inputs["Distortion"].default_value = 5
        nz.inputs["Detail"].default_value = 8; nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.75, 0.38, 0.1, 1); cr.color_ramp.elements[1].color = (1.0, 0.86, 0.6, 1)
        nt.links.new(nz.outputs["Fac"], cr.inputs["Fac"]); nt.links.new(cr.outputs["Color"], bs.inputs["Base Color"]); nt.links.new(cr.outputs["Color"], bs.inputs["Emission Color"])
        bs.inputs["Emission Strength"].default_value = 0.7; bs.inputs["Roughness"].default_value = 0.1
    shell, nt, sb = _node_mat("IN_Shell")
    if nt:
        tc = nt.nodes.new("ShaderNodeTexCoord"); br_ = nt.nodes.new("ShaderNodeTexBrick"); br_.offset = 0.0; br_.squash = 1.0
        br_.inputs["Scale"].default_value = 1.0; br_.inputs["Brick Width"].default_value = 1.6; br_.inputs["Row Height"].default_value = 3.3
        br_.inputs["Mortar Size"].default_value = 0.05; br_.inputs["Color1"].default_value = (0.035, 0.045, 0.055, 1); br_.inputs["Color2"].default_value = (0.05, 0.06, 0.07, 1)
        br_.inputs["Mortar"].default_value = (0.32, 0.27, 0.2, 1)
        sep = nt.nodes.new("ShaderNodeSeparateXYZ"); cmb = nt.nodes.new("ShaderNodeCombineXYZ"); ad = nt.nodes.new("ShaderNodeMath"); ad.operation = "ADD"
        nt.links.new(tc.outputs["Object"], sep.inputs[0]); nt.links.new(sep.outputs[0], ad.inputs[0]); nt.links.new(sep.outputs[1], ad.inputs[1])
        nt.links.new(ad.outputs[0], cmb.inputs[0]); nt.links.new(sep.outputs[2], cmb.inputs[1]); nt.links.new(cmb.outputs[0], br_.inputs["Vector"])
        nt.links.new(br_.outputs["Color"], sb.inputs["Base Color"])
        rr = nt.nodes.new("ShaderNodeMapRange"); nt.links.new(br_.outputs["Fac"], rr.inputs[0]); rr.inputs[3].default_value = 0.04; rr.inputs[4].default_value = 0.45
        nt.links.new(rr.outputs[0], sb.inputs["Roughness"])
        try: sb.inputs["Specular IOR Level"].default_value = 0.8
        except Exception: pass
    # ---------- shell: floor, ceiling, feature wall, sides, partitions
    _box("IN_floor", X0, X1, YG - 0.4, YB, zf + 0.0, zf + 0.03, floor, col)
    _box("IN_ceiling", X0, X1, YG - 0.4, YB, zc - 0.06, zc - 0.03, plaster, col)
    _box("IN_back", X0, X1, YB, YB + 0.3, zf, zc, wallm, col)
    for px in (xa, xb):
        _box("IN_part", px - 0.18, px + 0.18, YG + 0.05, YB, zf, zc, wallm, col)
        for k in range(5): yy = YG + 1.2 + k * 3.2; _box("IN_partGold", px - 0.2, px + 0.2, yy, yy + 0.05, zf, zc - 0.4, gold, col)
    _box("IN_beyond", X0, X1, YB + 0.3, 19.0, zf, zc, shell, col)                 # rest of the deep ground floor: closed
    # coffered ceiling: gold beams + warm cove line, recessed downlights
    for k in range(int((X1 - X0) / 3.2) + 1):
        xx = X0 + k * 3.2; _box("IN_beam", xx - 0.12, xx + 0.12, YG, YB, zc - 0.42, zc - 0.06, plaster, col); _box("IN_beamG", xx - 0.13, xx + 0.13, YG, YB, zc - 0.45, zc - 0.42, gold, col)
    for yy in (YG + 0.5, -21.2, YB - 0.5):
        _box("IN_beamY", X0, X1, yy - 0.12, yy + 0.12, zc - 0.42, zc - 0.06, plaster, col); _box("IN_coveL", X0, X1, yy - 0.16, yy - 0.12, zc - 0.40, zc - 0.36, cove, col)
    dl = []
    for k in range(14):
        for j in range(4):
            xx = X0 + 1.6 + k * 3.2; yy = YG + 2.4 + j * 4.0
            if abs(xx - xa) > 0.6 and abs(xx - xb) > 0.6: dl.append(_ico((xx, yy, zc - 0.07), 0.09, 0.15))
    v, f = _merge(dl); _obj("IN_downlights", v, f, _emit("IN_Down", (1.0, 0.88, 0.72), 14.0), col)
    # base boards + gold reveal on the back wall
    _box("IN_skirt", X0, X1, YB - 0.04, YB, zf, zf + 0.18, dark, col); _box("IN_reveal", X0, X1, YB - 0.05, YB, zf + 2.95, zf + 3.0, gold, col)
    # ---------- storefront glazing behind the arcade piers (client front render: slim black frames, one dark band at capital height)
    br = _mat("IN_Bronze", base=(0.025, 0.022, 0.02), rough=0.32, metal=0.85)
    g = _box("IN_glass", X0, X1, YG - 0.02, YG + 0.0, zf, zc, glassf, col)
    try: g.visible_shadow = False
    except Exception: pass
    BAYS = [(-178.5, -175.0), (-173.5, -169.5), (-165.5, -161.5), (-160.0, -156.0), (-154.5, -150.5), (-146.5, -142.5), (-141.0, -137.0)]
    for (b0, b1) in BAYS:
        for xx in (b0 + 0.05, b1 - 0.05, b0 + (b1 - b0) / 3, b0 + 2 * (b1 - b0) / 3):
            _box("IN_mull", xx - 0.035, xx + 0.035, YG - 0.07, YG + 0.04, zf, zc, br, col)
        _box("IN_sill", b0, b1, YG - 0.08, YG + 0.04, zf, zf + 0.12, br, col)
    _box("IN_band", X0, X1, YG - 0.09, YG + 0.04, zf + 5.35, zf + 5.62, br, col)
    _box("IN_band2", X0, X1, YG - 0.07, YG + 0.04, zf + 2.75, zf + 2.8, br, col)
    # entrance: black-framed double doors in the centre bay, steel push bars, a dark mat
    for xx in (-159.6, -158.0, -156.4): _box("IN_door", xx - 0.06, xx + 0.06, YG - 0.12, YG + 0.08, zf, zf + 2.8, br, col)
    for xx in (-158.25, -157.75): _box("IN_push", xx - 0.02, xx + 0.02, YG - 0.16, YG - 0.12, zf + 0.8, zf + 2.0, _mat("IN_Steel", base=(0.6, 0.6, 0.6), rough=0.2, metal=1.0), col)
    _box("IN_mat", -159.4, -156.6, YG + 0.15, YG + 1.6, zf + 0.03, zf + 0.04, _mat("IN_DoorMat", base=(0.03, 0.03, 0.03), rough=0.95), col)
    fls = _LS.get("flowers") or []
    # ---------- lobby: dark Nero marble, gold reveals, lift doors, stacked ring chandeliers
    LX, LY = -158.0, -25.1; LB = -21.0
    nero = _marble("IN_Nero", (0.035, 0.033, 0.032), (0.06, 0.056, 0.052), vein=(0.5, 0.46, 0.4), scale=1.3, rough=0.08)
    lfloor = _marble("IN_LobbyFloor", (0.62, 0.6, 0.57), (0.52, 0.5, 0.47), vein=(0.3, 0.28, 0.26), scale=0.3, rough=0.05, tiles=1.0)
    _box("IN_lobbyFloor", xa, xb, YG - 0.4, LB, zf + 0.031, zf + 0.04, lfloor, col)
    _box("IN_lobbyBack", xa, xb, LB, LB + 0.3, zf, zc, nero, col)
    for px, sg in ((xa + 0.18, 1), (xb - 0.18, -1)):
        _box("IN_lobbySide", min(px, px + sg * 0.06), max(px, px + sg * 0.06), YG + 0.05, LB, zf, zc, nero, col)
        for k in range(4): yy = YG + 1.6 + k * 2.0; _box("IN_sideGold", min(px, px + sg * 0.08), max(px, px + sg * 0.08), yy, yy + 0.03, zf, zc - 0.6, gold, col)
    for zz in (zf + 3.3, zc - 0.7): _box("IN_lobbyReveal", xa, xb, LB - 0.05, LB, zz, zz + 0.04, gold, col)
    _box("IN_lobbySkirt", xa, xb, LB - 0.04, LB, zf, zf + 0.15, gold, col)
    steel = _mat("IN_LiftSteel", base=(0.45, 0.36, 0.25), rough=0.28, metal=1.0)
    for k, lx_ in enumerate((-161.2, -158.0, -154.8)):       # three lifts
        _box("IN_liftFrame", lx_ - 0.85, lx_ + 0.85, LB - 0.12, LB, zf, zf + 2.95, gold, col)
        _box("IN_liftDoorL", lx_ - 0.68, lx_ - 0.01, LB - 0.16, LB - 0.12, zf + 0.04, zf + 2.75, steel, col)
        _box("IN_liftDoorR", lx_ + 0.01, lx_ + 0.68, LB - 0.16, LB - 0.12, zf + 0.04, zf + 2.75, steel, col)
        _box("IN_liftInd", lx_ - 0.25, lx_ + 0.25, LB - 0.14, LB - 0.12, zf + 3.05, zf + 3.13, _emit("IN_LiftInd", (1.0, 0.72, 0.4), 6.0), col)
    _box("IN_liftCove", xa + 0.3, xb - 0.3, LB - 0.3, LB - 0.26, zc - 0.62, zc - 0.58, cove, col)
    # stacked LED ring chandeliers (the client's centre bay shows two)
    ringE = _emit("IN_Ring", (1.0, 0.84, 0.62), 22.0)
    def rings(x, y, ztop, radii, z0):
        for k, r_ in enumerate(radii):
            zz = z0 + k * 0.32
            _obj("IN_ring", *_torus_mesh(r_, 0.035, 96, 8, 0.0), ringE, col, (x, y, zz)); _obj("IN_ringG", *_torus_mesh(r_ + 0.05, 0.018, 96, 6, 0.0), gold, col, (x, y, zz + 0.02))
            for a in (0.0, 2.094, 4.189): _cyl("IN_cable", 0.004, 0.004, ztop - zz, 4, steel, (x + math.cos(a) * r_, y + math.sin(a) * r_, zz), col)
        ld = bpy.data.lights.new("IN_ringL", "POINT"); ld.energy = 900 * len(radii) * max(radii); ld.color = (1.0, 0.8, 0.58); ld.shadow_soft_size = 0.2
        lo = bpy.data.objects.new("IN_ringL", ld); lo.location = (x, y, z0 - 0.2); col.objects.link(lo)
        for a in ("visible_camera", "visible_glossy", "visible_transmission"):
            try: setattr(lo, a, False)
            except Exception: pass
    rings(LX, -24.0, zc - 0.05, (1.5, 1.1, 0.7), zc - 3.6)
    rings(LX, -27.4, zc - 0.05, (0.85, 0.55), zc - 2.6)
    # reception at the west side of the lobby, lounge at the east side
    _box("IN_desk", -166.6, -162.4, -23.2, -22.2, zf, zf + 1.08, nero, col); _box("IN_deskTop", -166.75, -162.25, -23.35, -22.05, zf + 1.08, zf + 1.13, wallm, col)
    for k in range(20): xx = -166.5 + k * 0.205; _box("IN_flute", xx, xx + 0.05, -23.26, -23.2, zf + 0.12, zf + 1.0, gold, col)
    _box("IN_deskGlow", -166.5, -162.5, -23.22, -23.2, zf + 0.04, zf + 0.08, cove, col)
    def sofa(x, y, rot, w=2.4):
        c, s_ = math.cos(rot), math.sin(rot)
        def bx(n, a, b, c0, d, z0, z1, m):
            pts = [(a, c0), (b, c0), (b, d), (a, d)]; P_ = [(x + c * px - s_ * py, y + s_ * px + c * py) for px, py in pts]
            v = [(px, py, z0) for px, py in P_] + [(px, py, z1) for px, py in P_]
            _obj(n, v, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], m, col).modifiers.new("b", "BEVEL").width = 0.04
        bx("IN_sofaB", -w / 2, w / 2, -0.45, 0.45, zf + 0.1, zf + 0.45, cream); bx("IN_sofaBk", -w / 2, w / 2, 0.3, 0.48, zf + 0.45, zf + 0.95, cream)
        bx("IN_sofaA1", -w / 2 - 0.18, -w / 2, -0.45, 0.48, zf + 0.1, zf + 0.7, cream); bx("IN_sofaA2", w / 2, w / 2 + 0.18, -0.45, 0.48, zf + 0.1, zf + 0.7, cream)
        for k in range(3): bx("IN_cush", -w / 2 + 0.05 + k * (w / 3), -w / 2 + (k + 1) * (w / 3) - 0.05, -0.4, 0.3, zf + 0.45, zf + 0.58, velvet)
        bx("IN_legs", -w / 2, w / 2, -0.4, 0.43, zf, zf + 0.1, gold)
    lx = -152.6
    _box("IN_rug", lx - 1.6, lx + 1.6, LY - 2.0, LY + 2.0, zf + 0.04, zf + 0.052, rug, col)
    sofa(lx, LY - 1.35, 0.0); sofa(lx, LY + 1.35, math.pi)
    _cyl("IN_ctable", 0.55, 0.55, 0.05, 32, nero, (lx, LY, zf + 0.42), col); _cyl("IN_ctleg", 0.12, 0.2, 0.42, 16, gold, (lx, LY, zf), col)
    if fls: _inst(fls[0][0], lx, LY, zf + 0.47, 0, fls[0][2] * 0.3, col)
    pal = _LS.get("palm")
    for (ux, uy) in ((-166.6, -28.2), (-149.5, -28.2), (-149.5, -21.8)):
        _cyl("IN_urn", 0.42, 0.3, 0.75, 32, nero, (ux, uy, zf), col)
        if pal: _inst(pal, ux, uy, zf + 0.7, rnd.uniform(0, 6.28), 0.22, col)
    # ---------- west: flower shop (white blooms on tiered stands, lit shelving, warm pendants)
    for (cx_, cy_) in ((-176.8, -25.4), (-171.2, -25.4)): _chandelier("IN_bout", cx_, cy_, zc - 0.05, 0.7, 2, col, gold, crystal, bulb, drop=1.8, power=380)
    whiteF = _recolor(fls[0][0], "IN_flower_white", hue=0.5, sat=0.08, val=1.6) if fls else None
    pinkF = _recolor(fls[0][0], "IN_flower_pink", hue=0.15, sat=0.7, val=1.3) if fls else None
    for (tx, ty) in ((-177.6, -26.0), (-171.0, -26.0), (-174.3, -22.0), (-177.6, -18.0), (-171.0, -18.0)):
        for t_, (r_, z_) in enumerate(((0.75, 0.0), (0.5, 0.45), (0.28, 0.9))):      # three-tier round stand
            _cyl("IN_tier", r_, r_, 0.05, 32, wallm, (tx, ty, zf + 0.42 + z_), col); _cyl("IN_tierP", 0.04, 0.04, 0.45, 8, gold, (tx, ty, zf + z_), col)
            n_ = (8, 5, 3)[t_]
            for k in range(n_):
                a = 2 * math.pi * k / n_ + t_; vx, vy = tx + math.cos(a) * r_ * 0.7, ty + math.sin(a) * r_ * 0.7
                _cyl("IN_pvase", 0.09, 0.07, 0.22, 12, crystal, (vx, vy, zf + 0.47 + z_), col)
                fl_ = (whiteF, pinkF, fls[(k + t_) % len(fls)][0] if fls else None)[(k + t_) % 3]
                if fl_: _inst(fl_, vx, vy, zf + 0.62 + z_, rnd.uniform(0, 6), (fls[0][2] if fls else 1.0) * 0.28, col)
    for k in range(5):     # back-lit shelving with potted plants and vases
        zz = zf + 0.6 + k * 0.62
        _box("IN_shelf", X0 + 0.4, xa - 0.6, YB - 0.42, YB - 0.02, zz, zz + 0.04, walnut, col); _box("IN_shelfL", X0 + 0.4, xa - 0.6, YB - 0.4, YB - 0.36, zz - 0.02, zz, cove, col)
        for j in range(16):
            ox = X0 + 0.7 + j * 0.74 + rnd.uniform(-0.1, 0.1); h_ = rnd.uniform(0.18, 0.4)
            _cyl("IN_item", rnd.uniform(0.07, 0.12), rnd.uniform(0.05, 0.1), h_, 12, _mat("IN_Ceramic%d" % (j % 4), base=((0.92, 0.9, 0.86), (0.74, 0.6, 0.5), (0.58, 0.66, 0.6), (0.85, 0.75, 0.62))[j % 4], rough=0.25), (ox, YB - 0.22, zz + 0.04), col)
            if j % 3 == 0 and whiteF: _inst(whiteF, ox, YB - 0.22, zz + 0.04 + h_, rnd.uniform(0, 6), (fls[0][2] if fls else 1.0) * 0.2, col)
    for k in range(6):     # flower buckets just inside the glass
        bx_ = X0 + 1.0 + k * 2.1; _cyl("IN_bucket", 0.26, 0.2, 0.42, 20, _mat("IN_Zinc", base=(0.55, 0.55, 0.53), rough=0.35, metal=0.9), (bx_, YG + 0.75, zf), col)
        fl_ = (whiteF, pinkF)[k % 2] or (fls[0][0] if fls else None)
        if fl_: _inst(fl_, bx_, YG + 0.75, zf + 0.4, rnd.uniform(0, 6), (fls[0][2] if fls else 1.0) * 0.5, col)
    # ---------- east: fashion boutique (panelled beige walls, lit arched niches, mannequins, rails)
    beige = _mat("IN_Panel", base=(0.72, 0.62, 0.5), rough=0.5)
    for (cx_, cy_) in ((-144.6, -25.4), (-139.2, -25.4)): _chandelier("IN_bq", cx_, cy_, zc - 0.05, 0.7, 2, col, gold, crystal, bulb, drop=1.8, power=420)
    _box("IN_bqBack", xb + 0.2, X1, YB - 0.06, YB, zf, zc, beige, col)
    for k in range(4):     # arched niches with a glow line and handbags on a shelf
        nx = xb + 1.5 + k * 3.05
        _box("IN_niche", nx - 0.8, nx + 0.8, YB - 0.1, YB - 0.06, zf + 0.5, zf + 3.6, _mat("IN_NicheBack", base=(0.85, 0.78, 0.68), rough=0.6), col)
        _obj("IN_nicheArch", *_torus_mesh(0.8, 0.03, 48, 6, 0.0), gold, col, (nx, YB - 0.1, zf + 3.6)).rotation_euler = (math.pi / 2, 0, 0)
        for xx in (nx - 0.82, nx + 0.78): _box("IN_nicheF", xx, xx + 0.04, YB - 0.12, YB - 0.06, zf + 0.5, zf + 3.6, gold, col)
        _box("IN_nicheGlow", nx - 0.78, nx + 0.78, YB - 0.14, YB - 0.1, zf + 3.5, zf + 3.55, cove, col)
        _box("IN_nicheShelf", nx - 0.75, nx + 0.75, YB - 0.45, YB - 0.06, zf + 1.6, zf + 1.64, walnut, col)
        for j in range(3): _box("IN_bag", nx - 0.55 + j * 0.45, nx - 0.3 + j * 0.45, YB - 0.32, YB - 0.18, zf + 1.64, zf + 1.86, _mat("IN_Leather%d" % j, base=((0.06, 0.04, 0.03), (0.5, 0.32, 0.18), (0.75, 0.68, 0.6))[j], rough=0.4), col)
    gown = [_mat("IN_Gown%d" % k, base=c_, rough=0.75) for k, c_ in enumerate(((0.92, 0.9, 0.86), (0.85, 0.78, 0.68), (0.5, 0.06, 0.08), (0.06, 0.06, 0.07)))]
    skin = _mat("IN_Mannequin", base=(0.9, 0.88, 0.85), rough=0.25)
    def mannequin(x, y, m):
        _cyl("IN_mqBase", 0.22, 0.22, 0.03, 24, gold, (x, y, zf), col); _cyl("IN_mqRod", 0.015, 0.015, 0.75, 8, gold, (x, y, zf), col)
        _cyl("IN_mqDress", 0.42, 0.13, 0.95, 32, m, (x, y, zf + 0.12), col); _cyl("IN_mqTorso", 0.13, 0.17, 0.5, 24, m, (x, y, zf + 1.05), col)
        _cyl("IN_mqNeck", 0.045, 0.045, 0.14, 12, skin, (x, y, zf + 1.55), col)
        o = _obj("IN_mqHead", *_ico((0, 0, 0), 0.1, 1.25, 3), skin, col, (x, y, zf + 1.78))
        sh_ = _obj("IN_mqShoulder", *_ico((0, 0, 0), 0.2, 0.45, 3), m, col, (x, y, zf + 1.5))
        for pl in sh_.data.polygons: pl.use_smooth = True
        for pl in o.data.polygons: pl.use_smooth = True
    for k, (mx_, my_) in enumerate(((-146.0, -27.8), (-144.6, -27.6), (-139.6, -27.8), (-138.2, -27.6), (-142.2, -19.0))): mannequin(mx_, my_, gown[k % 4])
    for (ry_, x0_, x1_) in ((-23.6, -146.8, -144.0), (-23.6, -140.6, -137.8)):     # clothing rails
        for xx in (x0_, x1_): _cyl("IN_railPost", 0.02, 0.02, 1.7, 8, gold, (xx, ry_, zf), col)
        _box("IN_rail", x0_, x1_, ry_ - 0.015, ry_ + 0.015, zf + 1.66, zf + 1.69, gold, col)
        n_ = int((x1_ - x0_) / 0.13)
        for j in range(1, n_):
            xx = x0_ + j * 0.13; _box("IN_garment", xx - 0.02, xx + 0.02, ry_ - 0.25, ry_ + 0.25, zf + 0.62 + rnd.uniform(0, 0.25), zf + 1.6, gown[rnd.randrange(4)], col)
    _cyl("IN_ottoman", 0.65, 0.65, 0.42, 40, velvet, (-142.2, -24.0, zf), col)
    _obj("IN_mirror", [(-136.0, -18.5, zf + 0.3), (-136.0, -16.5, zf + 0.3), (-136.0, -16.5, zf + 2.6), (-136.0, -18.5, zf + 2.6)], [(0, 1, 2, 3)], _mat("IN_Mirror", base=(0.95, 0.95, 0.95), rough=0.0, metal=1.0), col)
    # ---------- warm room light (keeps the shops glowing behind the glass in daylight too)
    for (x0_, x1_) in ((X0, xa), (xa, xb), (xb, X1)):
        w_ = x1_ - x0_; d_ = YB - YG; _area("IN_room", (x0_ + x1_) / 2, (YG + YB) / 2, zc - 0.5, w_ - 0.4, d_ - 0.4, w_ * d_ * 9.0, col)
    # ---------- backing shells: nothing in the towers / podium may be see-through
    for (a_, b_, c_, d_, e_, f_) in ((-179.6, -167.4, -20.6, 0.6, 24.85, 78.9),      # west tower
                                     (-148.6, -136.4, -20.6, 0.6, 24.85, 78.9),      # east tower
                                     (-179.6, -136.4, 1.9, 18.6, 24.85, 78.9),       # back block
                                     (-180.5, -135.5, -27.0, 18.8, zc + 0.3, 24.6)):  # podium floors above the shops
        _box("IN_backing", a_, b_, c_, d_, e_, f_, shell, col)
    log(f"interior v1: {len(col.objects)} objects")

interior_v1()

# ---------------------------------------------------------------- warmer stone + professional night lighting
def _night_attr(nt):
    nd = nt.nodes.new("ShaderNodeAttribute"); nd.attribute_type = "VIEW_LAYER"; nd.attribute_name = "night"; return nd.outputs["Fac"]
def stone_and_night_v2():
    # 1. stone: a touch warmer, toward the client's sandstone
    m = bpy.data.materials.get("ST_Limestone")
    if m and m.node_tree:
        nt = m.node_tree
        for bs in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED" and abs(n.inputs["Roughness"].default_value - 0.62) < 0.01]:
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
            mx.inputs[7].default_value = (0.97, 0.89, 0.72, 1)
            lk = bs.inputs["Base Color"].links
            if lk: nt.links.new(lk[0].from_socket, mx.inputs[6])
            else: mx.inputs[6].default_value = bs.inputs["Base Color"].default_value
            nt.links.new(mx.outputs[2], bs.inputs["Base Color"])
        log("stone: warmed toward sandstone")
    # 2. every window lit, one warm tone with only a whisper of variation (no random dark rooms)
    g = bpy.data.materials.get("ST_Glass")
    if g and g.node_tree:
        nt = g.node_tree; bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        for k in ("Emission Strength", "Emission Color"):
            for l in list(bs.inputs[k].links): nt.links.remove(l)
        info = nt.nodes.new("ShaderNodeObjectInfo")
        var = nt.nodes.new("ShaderNodeMapRange"); nt.links.new(info.outputs["Random"], var.inputs[0]); var.inputs[3].default_value = 0.88; var.inputs[4].default_value = 1.0
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; nt.links.new(_night_attr(nt), m1.inputs[0]); nt.links.new(var.outputs[0], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; nt.links.new(m1.outputs[0], m2.inputs[0]); m2.inputs[1].default_value = 1.3
        nt.links.new(m2.outputs[0], bs.inputs["Emission Strength"]); bs.inputs["Emission Color"].default_value = (1.0, 0.66, 0.36, 1)
        log("night: all windows lit, uniform warm")
    sh = bpy.data.materials.get("IN_Shell")     # the curtain-wall infill glows the same way, frames stay dark
    if sh and sh.node_tree:
        nt = sh.node_tree; bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); br_ = next(n for n in nt.nodes if n.type == "TEX_BRICK")
        inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; nt.links.new(br_.outputs["Fac"], inv.inputs[1])
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; nt.links.new(_night_attr(nt), m1.inputs[0]); nt.links.new(inv.outputs[0], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; nt.links.new(m1.outputs[0], m2.inputs[0]); m2.inputs[1].default_value = 0.9
        nt.links.new(m2.outputs[0], bs.inputs["Emission Strength"]); bs.inputs["Emission Color"].default_value = (1.0, 0.66, 0.36, 1)
    # 3. architectural floodlighting: warm spots from the forecourt and the three other sides wash the whole stone face
    col = bpy.data.collections.new("night_floods"); scene.collection.children.link(col)
    def flood(name, src, tgt, size_deg, energy):
        ld = bpy.data.lights.new(name, "SPOT"); ld.energy = energy; ld.spot_size = math.radians(size_deg); ld.spot_blend = 0.85
        ld.color = (1.0, 0.70, 0.40); ld.shadow_soft_size = 0.6
        o = bpy.data.objects.new(name, ld); o.location = src; col.objects.link(o)
        o.rotation_euler = (Vector(tgt) - Vector(src)).to_track_quat("-Z", "Y").to_euler(); o["base_energy_v2"] = energy
        for a in ("visible_camera", "visible_glossy"):
            try: setattr(o, a, False)
            except Exception: pass
    for dx in (-20.0, 0.0, 20.0):                                   # front: low (podium) + high (towers)
        flood("NF_front_lo", (CX + dx, -96.0, 1.0), (CX + dx * 0.6, -31.0, 14.0), 34, 60000)
        flood("NF_front_hi", (CX + dx, -112.0, 1.0), (CX + dx * 0.5, -21.0, 58.0), 26, 160000)
    for sx in (-1, 1):                                              # east / west faces
        for dy in (-18.0, 8.0):
            flood("NF_side", (CX + sx * 85.0, CY + dy, 1.0), (CX + sx * 23.0, CY + dy * 0.5, 42.0), 34, 140000)
    for dx in (-15.0, 15.0): flood("NF_back", (CX + dx, 95.0, 1.0), (CX + dx * 0.6, 20.0, 42.0), 36, 140000)
    for o in bpy.data.objects:                                      # existing grazing uplights: warmer and stronger
        if o.type == "LIGHT" and o.name.startswith("Up_"): o.data.color = (1.0, 0.70, 0.40)
    log(f"night v2: {len(col.objects)} floodlights")
stone_and_night_v2()

# ---------------------------------------------------------------- podium floors 1-2 wings: stone, not curtain glass (client front render)
def podium_facade_v2():
    col = bpy.data.collections.new("facade_v2"); scene.collection.children.link(col)
    cut = bpy.data.collections.new("facade_v2_cut"); scene.collection.children.link(cut)
    stone = bpy.data.materials.get("ST_Limestone") or _mat("FV_Stone", base=(0.7, 0.62, 0.48), rough=0.6)
    glassw = bpy.data.materials.get("ST_Glass") or _glass("FV_Glass", (0.05, 0.06, 0.07))
    YF, YB_ = -30.08, -29.99                      # stone face just in front of the client's curtain glass, behind their surrounds
    def _outward(o):
        bm = _bm.new(); bm.from_mesh(o.data); _bm.ops.reverse_faces(bm, faces=bm.faces); bm.to_mesh(o.data); bm.free(); return o
    def cutter(x0, x1, z0, z1, arch=False):
        o = _outward(_box("FV_cut", x0, x1, YF - 0.3, YB_ + 0.3, z0, z1, stone, cut))
        if arch:
            r_ = (x1 - x0) / 2; c_ = _cyl("FV_cutA", r_, r_, 0.9, 32, stone, ((x0 + x1) / 2, YF - 0.3, z1), cut); c_.rotation_euler = (-math.pi / 2, 0, 0)
    def wall(x0, x1, z0, z1):
        w = _outward(_box("FV_wall", x0, x1, YF, YB_, z0, z1, stone, col))
        md = w.modifiers.new("cut", "BOOLEAN"); md.operation = "DIFFERENCE"; md.operand_type = "COLLECTION"; md.collection = cut
        try: md.solver = "EXACT"
        except Exception: pass
        return w
    def pane(x0, x1, z0, z1, arch=False):        # glazing in the new openings (lit at night with every other window)
        _box("FV_pane", x0, x1, YB_ - 0.02, YB_ - 0.01, z0, z1, glassw, col)
        if arch:
            r_ = (x1 - x0) / 2; c_ = _cyl("FV_paneA", r_, r_, 0.01, 32, glassw, ((x0 + x1) / 2, YB_ - 0.01, z1), col); c_.rotation_euler = (-math.pi / 2, 0, 0)
    def arch_frame(cx, z0, zs, w=1.96, t=0.14):
        r_ = w / 2
        for sx in (-1, 1): _box("FV_jamb", cx + sx * r_ - t / 2, cx + sx * r_ + t / 2, YF - 0.22, YF, z0, zs, stone, col)
        v = []; f = []; n = 24
        for i in range(n + 1):
            a = math.pi * i / n
            for (rr, yy) in ((r_ - t / 2, YF - 0.22), (r_ + t / 2, YF - 0.22), (r_ + t / 2, YF), (r_ - t / 2, YF)):
                v.append((cx + math.cos(a) * rr, yy, zs + math.sin(a) * rr))
        for i in range(n):
            for k in range(4): f.append((i * 4 + k, i * 4 + (k + 1) % 4, (i + 1) * 4 + (k + 1) % 4, (i + 1) * 4 + k))
        _obj("FV_arch", v, f, stone, col); _box("FV_key", cx - 0.14, cx + 0.14, YF - 0.3, YF, zs + r_ - 0.1, zs + r_ + 0.25, stone, col)
        _box("FV_sill", cx - r_ - 0.15, cx + r_ + 0.15, YF - 0.25, YF, z0 - 0.12, z0, stone, col)
    def rect_frame(cx, z0, z1, w=1.9, t=0.14):
        for sx in (-1, 1): _box("FV_jamb", cx + sx * w / 2 - t / 2, cx + sx * w / 2 + t / 2, YF - 0.2, YF, z0, z1, stone, col)
        _box("FV_head", cx - w / 2 - 0.2, cx + w / 2 + 0.2, YF - 0.3, YF, z1, z1 + 0.22, stone, col)
        _box("FV_sill", cx - w / 2 - 0.15, cx + w / 2 + 0.15, YF - 0.25, YF, z0 - 0.12, z0, stone, col)
    def balcony(cx, zb, w=2.1):
        _box("FV_balc", cx - w / 2, cx + w / 2, YF - 0.7, YF, zb, zb + 0.18, stone, col)
        for k in range(int(w / 0.19)):
            bx_ = cx - w / 2 + 0.12 + k * 0.19; _cyl("FV_bal", 0.045, 0.06, 0.62, 10, stone, (bx_, YF - 0.6, zb + 0.18), col)
        _box("FV_rail", cx - w / 2, cx + w / 2, YF - 0.72, YF - 0.48, zb + 0.8, zb + 0.92, stone, col)
        for x_ in (cx - w / 2, cx + w / 2 - 0.14): _box("FV_post", x_, x_ + 0.14, YF - 0.72, YF, zb + 0.18, zb + 0.8, stone, col)
    def pediment(cx, zb, w=3.3):
        _box("FV_pedB", cx - w / 2, cx + w / 2, YF - 0.42, YF, zb, zb + 0.16, stone, col)
        v = [(cx - w / 2, YF - 0.34, zb + 0.16), (cx + w / 2, YF - 0.34, zb + 0.16), (cx, YF - 0.34, zb + 0.95),
             (cx - w / 2, YF, zb + 0.16), (cx + w / 2, YF, zb + 0.16), (cx, YF, zb + 0.95)]
        _obj("FV_ped", v, [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], stone, col)
    # stone panels between the pilasters, z from the logo band to the podium cornice
    wl = wall(-180.45, -168.15, 12.05, 23.45); wr = wall(-147.95, -136.0, 12.05, 23.45)
    # floor 1: tall windows (left already has pediment surrounds; right gets matching pediments)
    for (a_, b_) in ((-179.4, -177.1), (-175.2, -172.9), (-171.8, -169.1), (-147.6, -144.4), (-143.8, -140.2), (-139.55, -136.2)):
        cutter(a_, b_, 12.45, 17.3)
    for cx in (-146.0, -142.0, -137.9): pediment(cx, 17.35)
    # floor 2: three arched / balconied windows per wing, the left wing mirrors the right
    for cx in (-146.0, -137.5, -170.0, -178.5):
        cutter(cx - 0.95, cx + 0.95, 20.0, 21.9, arch=True)
    for cx in (-142.3, -173.7): cutter(cx - 0.9, cx + 0.9, 20.0, 22.6)
    for cx in (-170.0, -178.5): arch_frame(cx, 20.0, 21.9); balcony(cx, 19.2); pane(cx - 0.95, cx + 0.95, 20.0, 21.9, arch=True)
    rect_frame(-173.7, 20.0, 22.6); balcony(-173.7, 19.2); pane(-174.6, -172.8, 20.0, 22.6)
    rect_frame(-142.3, 20.0, 22.6); pane(-143.2, -141.4, 20.0, 22.6)
    for o in cut.objects: o.hide_render = True
    log(f"podium facade v2: {len(col.objects)} pieces")
podium_facade_v2()

# ---------------------------------------------------------------- v5: no trees around the building (street trees on Pine Avenue stay)
def hide_trees_around():
    from collections import Counter
    keep_cols = {"landscape_v4", "LS_lib", "interior_v1", "facade_v2", "facade_v2_cut", "traffic", "people", "street_lights", "night_floods"}
    n = 0; kept = 0; by = Counter()
    for o in bpy.data.objects:
        if o.type != "EMPTY" or o.instance_type != "COLLECTION" or not o.instance_collection: continue
        cols = {c.name for c in o.users_collection}
        if cols & keep_cols or any(c.startswith(("LS_", "BK_", "PH_")) for c in cols): continue
        nm = o.instance_collection.name
        if _re.search(r"palm|shrub|bush|grass|flower|hedge|abelia|geranium|rose|hydrangea|cypress|lamp|light|bench|car|bus|truck|people|person|sign", nm, _re.I): continue
        p = o.matrix_world.translation
        road_side = p.y < -52.5                       # Pine Avenue verges and everything across the road
        if not road_side and math.hypot(p.x - CX, p.y - CY) < 300.0:
            if not o.hide_render: n += 1; by[next(iter(cols)) + ":" + nm[:18]] += 1
            o.hide_render = True
        elif not o.hide_render: kept += 1
    # standalone tree meshes (not instances) next to the plot
    bset = set(o.name for o in building_objects()); mt = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.hide_render or o.name in bset: continue
        cols = {c.name for c in o.users_collection}
        if cols & keep_cols or any(c.startswith(("LS_", "BK_", "PH_", "IN_", "FV_")) for c in cols): continue
        mats = " ".join(m.name for m in o.data.materials if m)
        if not _re.search(r"leaf|leav|foliage|bark|tree|trunk|branch|twig|maple|oak|eucalyp", o.name + " " + mats, _re.I): continue
        p = o.matrix_world @ Vector(o.bound_box[0]); q = o.matrix_world @ Vector(o.bound_box[6]); c_ = (p + q) / 2
        if c_.y >= -52.5 and math.hypot(c_.x - CX, c_.y - CY) < 300.0:
            o.hide_render = True; mt.append(o.name)
    log(f"trees: hid {n} around the building, kept {kept} (road and beyond)  {dict(by.most_common(12))}; meshes {len(mt)}: {mt[:12]}")
hide_trees_around()
_set_mode_v1 = set_mode
def set_mode(mode):
    _set_mode_v1(mode); nv = float(scene.get("night", 0.0))
    for o in bpy.data.objects:
        if "base_energy_v2" in o:
            o.data.energy = o["base_energy_v2"] * (nv ** 1.5); o.hide_render = nv < 0.05
        elif o.type == "LIGHT" and o.name.startswith("Up_") and nv >= 0.05:
            o.data.energy = o.data.energy * 1.8

def fill_light(on=True):
    """A soft, shadowless front fill so the recessed centre bay reads as bright as the main piers."""
    f = bpy.data.objects.get("FillSun")
    if f is None:
        ld = bpy.data.lights.new("FillSun", "SUN"); f = bpy.data.objects.new("FillSun", ld); scene.collection.objects.link(f)
        ld.energy = 1.6; ld.color = (1.0, 0.94, 0.86); ld.angle = math.radians(8)
        for attr in ("use_shadow",):
            try: setattr(ld, attr, False)
            except Exception: pass
        try: ld.cycles.cast_shadow = False
        except Exception: pass
        d = Vector((0.0, -math.cos(math.radians(22)), math.sin(math.radians(22))))
        f.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    try: f.visible_glossy = False          # a fill, never a sun disc mirrored in the shop glass or polished marble
    except Exception: pass
    f.hide_render = not on
    r = bpy.data.objects.get("RecessFill")      # local shadowless wash on the recessed centre bay between the twin piers
    if r is None:
        ld = bpy.data.lights.new("RecessFill", "AREA"); ld.shape = "RECTANGLE"; ld.size = 18; ld.size_y = 95; ld.energy = 3000
        ld.color = (1.0, 0.92, 0.82); ld.spread = math.radians(70)
        try: ld.cycles.cast_shadow = False
        except Exception: pass
        r = bpy.data.objects.new("RecessFill", ld); scene.collection.objects.link(r)
        r.location = (CX, -95.0, 48.0); r.rotation_euler = Vector((0, 1, 0.02)).to_track_quat("-Z", "Y").to_euler()
    r.hide_render = not on

_set_mode0 = set_mode
def set_mode(mode):   # every pass gets the shadowless front fill in daylight, none at dusk / night
    _set_mode0(mode); fill_light(mode in ("day", "golden"))

# ---------------------------------------------------------------- the 3 x 3 grid of rendered paths (height x distance)
PATHS = {   # radius (horizontal), camera height, look-at height, lens
    "g1": (95.0, 5.5, 40.0, 19.0), "g2": (130.0, 6.5, 39.0, 24.0), "g3": (180.0, 15.0, 40.0, 30.0),
    "m1": (150.0, 40.0, 40.0, 24.0), "m2": (237.7, 78.4, 45.0, 32.0), "m3": (380.0, 110.0, 40.0, 36.0),
    "h1": (160.0, 150.0, 30.0, 24.0), "h2": (260.0, 220.0, 30.0, 30.0), "h3": (420.0, 330.0, 25.0, 36.0)}
PATH_N, PATH_STEP = 81, 2.5      # 81 views on the same 200 deg arc (was 41 x 5 deg): twice as many frames for smoother swiping
def path_pose(key, i):
    r, h, tz, lens = PATHS[key]; az = math.radians(-100.0 + PATH_STEP * i)
    return Vector((CX + math.sin(az) * r, CY - math.cos(az) * r, h)), Vector((CX, CY, tz)), lens
_VEG = None
def clear_view(P, tz):
    """Hide trees and lamp posts standing between the camera and the tower for this frame."""
    global _VEG
    if _VEG is None:
        _VEG = []
        for cn in ("vegetation", "street_lights", "site_v3"):
            c = bpy.data.collections.get(cn)
            if not c: continue
            for o in c.all_objects:
                if o is not None and not o.hide_render and (o.instance_type == "COLLECTION" or o.type == "MESH" and cn == "street_lights"):
                    _VEG.append([o, o.matrix_world.translation.copy()])
    T = Vector((CX, CY, min(tz, 20.0))); seg = T - P; L = seg.length; u = seg / L
    for item in _VEG:
        o, q = item; qq = Vector((q.x, q.y, max(q.z + 5.0, P.z * 0.6)))
        t = (qq - P).dot(u)
        block = 0 < t < L - 26.0 and (P + u * t - qq).length < 15.0 and P.z < 70.0
        o.hide_render = block

meta = {"levels": [{"index": i, "name": n, "zBottom": (CUTS[i - 1] if i else 0.0), "zTop": (CUTS[i] if i < len(CUTS) else TOP),
                    "maskValue": (i + 1) * 16} for i, n in enumerate(NAMES)],
        "orbit": ORBIT, "explode": EXPL, "size": [W, H], "maskSize": [W // 2, H // 2]}
json.dump(meta, open(os.path.join(OUT, "levels.json"), "w"), indent=1)

for ps in PASSES:
    log(f"=== pass {ps}")
    if ps == "masks":
        if empties[0] is None:
            log("masks need the sliced scene"); continue
        mask_setup(True); do_orbit("mask"); do_explode("mask")
        for i in range(GROUND["count"]):
            P, T = ground_pose(i); look(cam, P, T); cam.data.lens = GROUND["lens"]
            render_to(os.path.join(OUT, "ground", "mask", f"g_{i:03d}.png"))
        cam.data.lens = ORBIT["lens"]; mask_setup(False)
    elif ps == "path_masks":
        if empties[0] is None:
            log("masks need the sliced scene"); continue
        mask_setup(True); scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        for key in PATHS:
            for i in range(PATH_N):
                P, T, lens = path_pose(key, i); look(cam, P, T); cam.data.lens = lens
                render_to(os.path.join(OUT, "p", key, "mask", f"f_{i:03d}.png"))
        cam.data.lens = ORBIT["lens"]; mask_setup(False)
    elif ps == "orbit_day":
        cycles_setup(256); set_mode("day"); do_orbit("day")
    elif ps == "orbit_dusk":
        cycles_setup(256); set_mode("dusk"); do_orbit("dusk")
    elif ps == "explode_day":
        if empties[0] is None:
            log("explode needs the sliced scene"); continue
        hid = []
        for cn in ("vegetation", "traffic", "context", "street_lights"):
            c = bpy.data.collections.get(cn)
            if c:
                for o in c.all_objects:
                    if o is not None and not o.hide_render: o.hide_render = True; hid.append(o)
        cycles_setup(256); set_mode("day"); do_explode("day")
        for o in hid: o.hide_render = False
    elif ps == "view10":
        # 360 view from the 10th-floor balcony of the west tower, front facade (unit 10-A)
        cycles_setup(384); set_mode("day")
        scene.frame_set(1)
        z10 = 25.0 + 3.5 * 7 + 1.6
        hit, loc, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector((-174.0, -120.0, z10)), Vector((0, 1, 0)), distance=200)
        y = (loc.y - 0.9) if hit else -24.0
        cd = bpy.data.cameras.new("View10"); cd.type = "PANO"
        try: cd.panorama_type = "EQUIRECTANGULAR"
        except Exception: cd.cycles.panorama_type = "EQUIRECTANGULAR"
        vc = bpy.data.objects.new("View10", cd); scene.collection.objects.link(vc)
        vc.location = (-174.0, y, z10); vc.rotation_euler = (math.radians(90), 0, math.radians(180))   # facing out over Pine Avenue
        scene.camera = vc
        scene.render.resolution_x, scene.render.resolution_y = (1024, 512) if QUICK else (4096, 2048)
        t = time.time()
        if render_to(os.path.join(OUT, "pano", "view.jpg")): log(f"view10 pano: {time.time() - t:.0f}s at y={y:.2f}")
        for lk, md in (("sunset", "dusk"), ("night", "night")):   # same camera, other light: the tour's time-of-day slider
            set_mode(md); render_to(os.path.join(OUT, "pano", f"view@{lk}.jpg"))
        set_mode("day")
        # Pine Avenue: a standing 360 on the boulevard median in front of the tower
        set_mode("golden"); fill_light(True); clear_view(Vector((0, -9999, 999)), 0)
        vc.location = (CX, -70.5, 1.7); vc.rotation_euler = (math.radians(90), 0, 0)
        if render_to(os.path.join(OUT, "pano", "pine.jpg")): log("pine avenue pano done")
        set_mode("night"); render_to(os.path.join(OUT, "pano", "pine@night.jpg")); set_mode("day")
        scene.camera = cam
    elif ps == "flyin":
        # cinematic fly-in: from the orbit's front view down to the floor-10 window of unit 10-A (viewer crossfades into the tour)
        cycles_setup(FLY["samples"]); set_mode("day"); scene.frame_set(1)
        z10 = 25.0 + 3.5 * 7 + 1.6
        hit, loc, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector((-174.0, -120.0, z10)), Vector((0, 1, 0)), distance=200)
        yb = loc.y if hit else -23.0
        log(f"flyin: facade hit={hit} y={yb:.2f}")
        P0, TA = orbit_pose(ORBIT["count"] // 2)   # the front view (az 0), where the explorer starts
        P3 = Vector((-174.0, yb - 2.4, z10 - 0.1)); TB = Vector((-174.0, yb + 12.0, z10 - 0.6))
        P1 = P0 + Vector((-4.0, 48.0, -14.0)); P2 = P3 + Vector((10.0, -55.0, 9.0))
        N = FLY["frames"]
        for i in range(N):
            u = i / (N - 1); e = u * u * u * (u * (u * 6 - 15) + 10)            # smootherstep
            k = 1 - e
            pos = k**3 * P0 + 3 * k**2 * e * P1 + 3 * k * e**2 * P2 + e**3 * P3
            te = min(1.0, e * 1.15); tgt = TA.lerp(TB, te * te * (3 - 2 * te))
            look(cam, pos, tgt); cam.data.lens = ORBIT["lens"] - 6.0 * e
            p = os.path.join(OUT, "flyin", f"fl_{i:03d}.jpg"); t = time.time()
            if render_to(p): log(f"flyin {i:03d}: {time.time() - t:.0f}s")
        cam.data.lens = ORBIT["lens"]
    elif ps == "inspect":
        import json as _json
        rows = []
        dg = bpy.context.evaluated_depsgraph_get()
        for o in scene.objects:
            if o.type not in ("MESH", "EMPTY", "CURVE", "LIGHT") or o.hide_render: continue
            p = o.matrix_world.translation
            if not (abs(p.x - CX) < 110 and -110 < p.y < 80): continue
            if o.type == "MESH":
                bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
                zmin, zmax = min(v.z for v in bb), max(v.z for v in bb)
                if zmax > 8.0: continue
                dims = [round(max(v[k] for v in bb) - min(v[k] for v in bb), 1) for k in range(3)]
                rows.append({"n": o.name, "t": "MESH", "x": round(p.x, 1), "y": round(p.y, 1), "z": [round(zmin, 2), round(zmax, 2)], "dim": dims,
                             "mats": [sl.material.name for sl in o.material_slots if sl.material][:4], "cols": [c.name for c in o.users_collection]})
            else:
                rows.append({"n": o.name, "t": o.type, "x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1),
                             "inst": o.instance_collection.name if o.instance_type == "COLLECTION" and o.instance_collection else "", "cols": [c.name for c in o.users_collection]})
        os.makedirs(os.path.join(RENDER_DIR, "out", "inspect"), exist_ok=True)
        open(os.path.join(RENDER_DIR, "out", "inspect", "site.json"), "w").write(_json.dumps(rows, indent=0))
        log(f"inspect: {len(rows)} objects near the plot")
        cycles_setup(48); set_mode("golden")
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1600
        top = make_cam("CAM_top", 50); top.data.type = "ORTHO"; top.data.ortho_scale = 200.0
        top.location = (CX, CY - 25.0, 300.0); top.rotation_euler = (0, 0, 0); scene.camera = top
        render_to(os.path.join(RENDER_DIR, "out", "inspect", "top.jpg"))
        scene.camera = cam; scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        look(cam, Vector((CX - 30, -88.0, 4.0)), Vector((CX, -30.0, 6.0))); cam.data.lens = 24
        render_to(os.path.join(RENDER_DIR, "out", "inspect", "forecourt.jpg"))
        cam.data.lens = ORBIT["lens"]
    elif ps == "lsdebug":
        cycles_setup(24); set_mode("golden"); clear_view(Vector((0, -9999, 999)), 0)
        cam.data.type = "ORTHO"; cam.data.ortho_scale = 70; cam.location = (CX, -38.0, 120); cam.rotation_euler = (0, 0, 0)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
        render_to(os.path.join(RENDER_DIR, "out", "lookdev4", "forecourt_top.jpg")); cam.data.type = "PERSP"
        for o in _LS["col"].objects:
            if o.name.startswith(("LS_kidney", "LS_f_pool", "LS_facade")): log(f"dbg {o.name} loc={tuple(round(v,1) for v in o.location)} verts0={tuple(round(v,1) for v in o.data.vertices[0].co) if o.type=='MESH' else ''} hide={o.hide_render}")
    elif ps == "probe_shell":
        # horizontal ray grid against the building only: where the facade is, and where you can see straight through it
        dg = bpy.context.evaluated_depsgraph_get(); B = set(o.name for o in building_objects())
        def hit(P, D, far):
            d0 = 0.0
            for _ in range(60):
                h, loc, nrm, idx, ob, mw = scene.ray_cast(dg, P + D * d0, D, distance=far - d0)
                if not h: return None
                o = getattr(ob, "original", ob)
                if o.name in B and not o.hide_render:
                    m = ob.material_slots[ob.data.polygons[idx].material_index].material.name if ob.type == "MESH" and ob.material_slots and idx < len(ob.data.polygons) else ""
                    return [round((loc - P).length, 2), m[:18]]
                d0 = (loc - P).length + 0.01
            return None
        res = {"z": [], "xs": [], "ys": []}
        xs = [-192 + 0.5 * i for i in range(170)]; ys = [-58 + 0.5 * i for i in range(180)]; res["xs"] = xs; res["ys"] = ys
        for z in [0.6, 1.5, 3.0, 4.5, 6.0, 8.0, 12.0, 18.0, 23.0, 27.0, 32.0, 40.0, 50.0, 60.0, 66.0, 70.0, 73.0, 76.0, 78.5, 81.0, 84.0]:
            row = {"z": z, "S": [hit(Vector((x, -80.0, z)), Vector((0, 1, 0)), 130) for x in xs], "N": [hit(Vector((x, 50.0, z)), Vector((0, -1, 0)), 130) for x in xs],
                   "W": [hit(Vector((-205.0, y, z)), Vector((1, 0, 0)), 110) for y in ys], "E": [hit(Vector((-100.0, y, z)), Vector((-1, 0, 0)), 110) for y in ys]}
            res["z"].append(row); log(f"probe z={z}")
        os.makedirs(os.path.join(RENDER_DIR, "out", "inspect"), exist_ok=True)
        json.dump(res, open(os.path.join(RENDER_DIR, "out", "inspect", "shell.json"), "w"))
        cycles_setup(48); set_mode("golden"); fill_light(True); clear_view(Vector((0, -9999, 999)), 0)
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        d = os.path.join(RENDER_DIR, "out", "inspect")
        V = {"sh_east": ((-80.0, -5.0, 70.0), (CX, -5.0, 66.0), 35), "sh_back": ((CX, 80.0, 70.0), (CX, -5.0, 62.0), 35), "sh_west": ((-236.0, -5.0, 70.0), (CX, -5.0, 66.0), 35),
             "sh_se": ((-95.0, -75.0, 85.0), (CX, -5.0, 60.0), 30), "sh_ne": ((-100.0, 60.0, 60.0), (CX, -5.0, 45.0), 30),
             "gf_arcade": ((CX, -46.0, 2.2), (CX, -25.0, 4.0), 22), "gf_left": ((-172.0, -40.0, 1.8), (-172.0, -20.0, 3.0), 24),
             "gf_hotel": ((-128.5, -58.0, 1.7), (-150.0, -38.0, 4.0), 26), "gf_east": ((-112.0, -20.0, 2.0), (-135.0, -18.0, 4.0), 24)}
        for k, (P_, T_, lens) in V.items():
            look(cam, Vector(P_), Vector(T_)); cam.data.lens = lens; render_to(os.path.join(d, k + ".jpg"))
        cam.data.lens = ORBIT["lens"]; log("probe_shell done")
    elif ps == "lookdev5":
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 64)); set_mode("golden"); fill_light(True); clear_view(Vector((0, -9999, 999)), 0)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 900; d = os.path.join(RENDER_DIR, "out", "lookdev5"); os.makedirs(d, exist_ok=True)
        V = {"arcade": ((CX, -47.0, 2.0), (CX, -24.0, 3.6), 24), "lobby_in": ((-158.0, -28.4, 1.65), (-158.0, -14.0, 2.6), 18),
             "boutique": ((-172.0, -40.0, 1.7), (-174.0, -20.0, 2.8), 26), "cafe": ((-142.0, -40.0, 1.7), (-142.0, -20.0, 2.8), 26),
             "front_mid": ((CX, -95.0, 9.0), (CX, -28.0, 12.0), 28), "client_front": ((CX, -80.0, 5.5), (CX, -30.0, 14.0), 20),
             "fashion_in": ((-147.6, -28.6, 1.65), (-138.0, -18.0, 1.9), 18), "flower_in": ((-168.4, -28.6, 1.65), (-178.0, -18.0, 1.9), 18), "sh_east": ((-80.0, -5.0, 70.0), (CX, -5.0, 66.0), 35),
             "sh_se": ((-95.0, -75.0, 85.0), (CX, -5.0, 60.0), 30), "sh_back": ((CX, 80.0, 70.0), (CX, -5.0, 62.0), 35)}
        for k in ("m1_30", "m1_40", "g2_14"):
            P_, T_, lens = path_pose(k[:2], int(k[3:])); V[k] = (tuple(P_), tuple(T_), lens)
        for k, (P_, T_, lens) in V.items():
            clear_view(Vector(P_), T_[2]); look(cam, Vector(P_), Vector(T_)); cam.data.lens = lens; render_to(os.path.join(d, k + ".jpg"))
        cam.data.lens = ORBIT["lens"]
        set_mode("night"); fill_light(False)
        for k in ("arcade", "client_front"):
            P_, T_, lens = V[k]; clear_view(Vector(P_), T_[2]); look(cam, Vector(P_), Vector(T_)); cam.data.lens = lens; render_to(os.path.join(d, k + "@night.jpg"))
        cam.data.lens = ORBIT["lens"]; set_mode("day")
    elif ps == "elev":
        dg = bpy.context.evaluated_depsgraph_get(); B = set(o.name for o in building_objects())
        xs = [-184.0 + 0.25 * i for i in range(210)]; zs = [8.0 + 0.25 * i for i in range(112)]; rows = []
        for z in zs:
            row = []
            for x in xs:
                P0 = Vector((x, -80.0, z)); d0 = 0.0; val = None
                for _ in range(30):
                    h, loc, nrm, idx, ob, mw = scene.ray_cast(dg, P0 + Vector((0, d0, 0)), Vector((0, 1, 0)), distance=120 - d0)
                    if not h: break
                    if getattr(ob, "original", ob).name in B: val = round(loc.y, 2); break
                    d0 = loc.y + 80.0 + 0.01
                row.append(val)
            rows.append(row)
        json.dump({"xs": xs, "zs": zs, "y": rows}, open(os.path.join(RENDER_DIR, "out", "inspect", "elev.json"), "w"))
        cycles_setup(48); set_mode("golden"); fill_light(True); clear_view(Vector((0, -9999, 999)), 0)
        cam.data.type = "ORTHO"; cam.data.ortho_scale = 54.0; look(cam, Vector((CX, -120.0, 20.0)), Vector((CX, 0.0, 20.0)))
        scene.render.resolution_x, scene.render.resolution_y = 2160, 1200
        render_to(os.path.join(RENDER_DIR, "out", "inspect", "elev_front.jpg")); cam.data.type = "PERSP"; log("elev done")
    elif ps == "night_test":
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 64)); scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        d = os.path.join(RENDER_DIR, "out", "lookdev6"); os.makedirs(d, exist_ok=True)
        V = {"client_front": ((CX, -80.0, 5.5), (CX, -30.0, 14.0), 20), "front_far": ((CX, -150.0, 25.0), (CX, -5.0, 45.0), 30),
             "arcade": ((CX, -47.0, 2.0), (CX, -24.0, 3.6), 24), "elev_persp": ((CX, -70.0, 18.0), (CX, -30.0, 18.0), 30)}
        for k in ("m1_30", "m1_10", "h1_20", "g2_14"):
            P_, T_, lens = path_pose(k[:2], int(k[3:])); V[k] = (tuple(P_), tuple(T_), lens)
        for md, suf in (("golden", ""), ("night", "@night")):
            set_mode(md); fill_light(md == "golden")
            for k, (P_, T_, lens) in V.items():
                if md == "golden" and k not in ("client_front", "elev_persp", "m1_30", "arcade"): continue
                clear_view(Vector(P_), T_[2]); look(cam, Vector(P_), Vector(T_)); cam.data.lens = lens; render_to(os.path.join(d, k + suf + ".jpg"))
        cam.data.lens = ORBIT["lens"]; set_mode("day")
    elif ps == "splat_data":
        # Gaussian-splat capture: ~370 calibrated views of the tower + site on full rings and close arcs, RGBA (sky and
        # everything beyond SPLAT_R is transparent via a camera-only holdout cylinder), COLMAP + nerfstudio poses, and
        # a coloured sparse point cloud ray-cast from the renders (synthetic "SfM").
        import random as _rnd
        R_HOLD = 165.0; test = os.environ.get("ST_SPLAT_TEST") == "1"
        sd = os.path.join(RENDER_DIR, "out", "splat_test" if test else "splat"); idir = os.path.join(sd, "images"); os.makedirs(idir, exist_ok=True)
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 96)); set_mode("golden"); fill_light(True); clear_view(Vector((0, -9999, 999)), 0)
        W_, H_ = (960, 540) if test else (1920, 1080)
        scene.render.resolution_x, scene.render.resolution_y = W_, H_
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGBA"; scene.render.image_settings.color_depth = "8"
        hm = bpy.data.materials.new("SPL_Holdout"); hm.use_nodes = True; hn = hm.node_tree
        for n in list(hn.nodes):
            if n.type != "OUTPUT_MATERIAL": hn.nodes.remove(n)
        ho = hn.nodes.new("ShaderNodeHoldout"); hn.links.new(ho.outputs[0], next(n for n in hn.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"])
        hc = _cyl("SPL_holdcyl", R_HOLD, R_HOLD, 1600.0, 128, hm, (CX, CY, -60.0), scene.collection, cap=False)
        for a in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_shadow", "visible_volume_scatter"):
            try: setattr(hc, a, False)
            except Exception: pass
        cams = []   # (name, P, T, lens)
        def ring(tag, r, h, tz, n, lens, a0=-180.0, a1=180.0, full=True):
            m = n if full else n - 1
            for k in range(n):
                az = math.radians(a0 + (a1 - a0) * k / m)
                cams.append((f"{tag}{k:03d}", Vector((CX + math.sin(az) * r, CY - math.cos(az) * r, h)), Vector((CX, CY, tz)), lens))
        ring("A", 95.0, 6.0, 25.0, 72, 24); ring("B", 130.0, 35.0, 35.0, 72, 28); ring("C", 120.0, 90.0, 40.0, 60, 28)
        ring("D", 90.0, 150.0, 30.0, 48, 28); ring("E", 40.0, 230.0, 20.0, 24, 30)
        ring("F", 45.0, 3.0, 8.0, 29, 22, -70.0, 70.0, False); ring("G", 70.0, 15.0, 18.0, 33, 24, -80.0, 80.0, False)
        ring("H", 35.0, 100.0, 79.0, 36, 24)
        if os.environ.get("ST_SPLAT_V2", "1") == "1":
            # v2: closer views for facade/podium/tower detail (sharper splat). Existing A-H images are kept.
            ring("I", 55.0, 12.0, 18.0, 72, 24)                      # podium + arcade, close all round
            ring("J", 60.0, 40.0, 42.0, 72, 24)                      # lower tower
            ring("K", 60.0, 70.0, 66.0, 60, 24)                      # upper tower
            ring("L", 65.0, 105.0, 82.0, 48, 24)                     # crown / roof
            ring("M", 32.0, 4.0, 7.0, 41, 20, -75.0, 75.0, False)    # forecourt + entrance, very close
            ring("N", 85.0, 55.0, 45.0, 48, 35)                      # mild telephoto detail all round
            # v2b: even closer facade / rooftop / terrace / ground coverage (sharp on phones too)
            ring("O", 42.0, 20.0, 22.0, 96, 24)                      # podium facade, very close all round
            ring("P", 42.0, 55.0, 55.0, 72, 24)                      # tower facade, very close all round
            ring("Q", 26.0, 100.0, 86.0, 36, 20)                     # rooftop, looking down from just above
            ring("R", 30.0, 36.0, 25.0, 60, 20)                      # podium terrace garden
            ring("S", 70.0, 2.5, 4.0, 72, 22)                        # ground level, eye height all round
            ring("T", 50.0, 26.0, 0.0, 48, 22)                       # forecourt / site ground from above
        if test: cams = cams[::62]
        log(f"splat: {len(cams)} views at {W_}x{H_}")
        frames = []
        for (nm, P_, T_, lens) in cams:
            look(cam, P_, T_); cam.data.lens = lens; cam.data.sensor_width = 36.0; cam.data.sensor_fit = "HORIZONTAL"
            bpy.context.view_layer.update()   # refresh matrix_world even when the render is skipped (image already exists)
            fp = os.path.join(idir, nm + ".png"); t0 = time.time()
            if render_to(fp): log(f"splat {nm}: {time.time() - t0:.0f}s")
            frames.append((nm, cam.matrix_world.copy(), lens))
        # poses: nerfstudio transforms.json (OpenGL camera = Blender camera), and COLMAP text (OpenCV camera)
        fx = W_ * frames[0][2] / 36.0
        OFF = Vector((CX, CY, 0.0))       # scene centred on the tower for numerical comfort
        tj = {"camera_model": "OPENCV", "w": W_, "h": H_, "cx": W_ / 2, "cy": H_ / 2, "ply_file_path": "sparse_pc.ply", "frames": []}
        os.makedirs(os.path.join(sd, "sparse", "0"), exist_ok=True)
        ctx_, itx = [], []
        flip = Matrix(((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))
        for k, (nm, mw, lens) in enumerate(frames):
            f_ = W_ * lens / 36.0; m = mw.copy(); m.translation = m.translation - OFF
            tj["frames"].append({"file_path": f"images/{nm}.png", "fl_x": f_, "fl_y": f_, "transform_matrix": [list(r) for r in m]})
            ctx_.append(f"{k + 1} PINHOLE {W_} {H_} {f_:.6f} {f_:.6f} {W_ / 2:.3f} {H_ / 2:.3f}")
            w2c = (m @ flip).inverted(); q = w2c.to_quaternion(); t = w2c.translation
            itx.append(f"{k + 1} {q.w:.9f} {q.x:.9f} {q.y:.9f} {q.z:.9f} {t.x:.6f} {t.y:.6f} {t.z:.6f} {k + 1} {nm}.png\n\n")
        json.dump(tj, open(os.path.join(sd, "transforms.json"), "w"), indent=1)
        open(os.path.join(sd, "sparse", "0", "cameras.txt"), "w").write("# Camera list\n" + "\n".join(ctx_) + "\n")
        open(os.path.join(sd, "sparse", "0", "images.txt"), "w").write("# Image list\n" + "".join(itx))
        # sparse points: cast a pixel grid from every 5th view, colour from that view's render
        dg = bpy.context.evaluated_depsgraph_get(); pts = []; t_start = time.time(); rng = _rnd.Random(3)
        for k, (nm, mw, lens) in enumerate(frames):
            if k % (1 if test else 5): continue
            if time.time() - t_start > 1500: break
            im = bpy.data.images.load(os.path.join(idir, nm + ".png")); px = im.pixels[:]; f_ = W_ * lens / 36.0
            org = mw.translation; R3 = mw.to_3x3()
            for gy in range(27):
                for gx in range(48):
                    u = (gx + rng.random()) / 48 * W_; v = (gy + rng.random()) / 27 * H_
                    d = R3 @ Vector(((u - W_ / 2) / f_, -(v - H_ / 2) / f_, -1.0)); d.normalize()
                    h, loc, *_ = scene.ray_cast(dg, org, d, distance=600.0)
                    if not h or (Vector((loc.x - CX, loc.y - CY)).length > R_HOLD - 2): continue
                    pi = (int(H_ - 1 - v) * W_ + int(u)) * 4
                    if px[pi + 3] < 0.5: continue
                    pts.append((loc - OFF, [min(255, int(c * 255)) for c in px[pi:pi + 3]]))
            bpy.data.images.remove(im)
        with open(os.path.join(sd, "sparse", "0", "points3D.txt"), "w") as fo:
            fo.write("# 3D point list\n")
            for i, (p_, c_) in enumerate(pts): fo.write(f"{i + 1} {p_.x:.4f} {p_.y:.4f} {p_.z:.4f} {c_[0]} {c_[1]} {c_[2]} 0\n")
        with open(os.path.join(sd, "sparse_pc.ply"), "w") as fo:
            fo.write(f"ply\nformat ascii 1.0\nelement vertex {len(pts)}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
            for (p_, c_) in pts: fo.write(f"{p_.x:.4f} {p_.y:.4f} {p_.z:.4f} {c_[0]} {c_[1]} {c_[2]}\n")
        log(f"splat: {len(frames)} poses, {len(pts)} sparse points ({time.time() - t_start:.0f}s)")
        scene.render.film_transparent = False; scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.color_mode = "RGB"
        bpy.data.objects.remove(hc)
        # sky backdrop for the web viewer: the same golden-hour world, nothing else, as a 4096 x 2048 equirect
        hid = [o for o in bpy.data.objects if o.type in ("MESH", "CURVE", "FONT", "EMPTY") and not o.hide_render]
        for o in hid: o.hide_render = True
        cd = bpy.data.cameras.new("SkyPano"); cd.type = "PANO"
        try: cd.panorama_type = "EQUIRECTANGULAR"
        except Exception: cd.cycles.panorama_type = "EQUIRECTANGULAR"
        sc = bpy.data.objects.new("SkyPano", cd); scene.collection.objects.link(sc); sc.location = (CX, CY, 40.0); sc.rotation_euler = (math.radians(90), 0, 0)
        scene.camera = sc; cycles_setup(32); scene.render.resolution_x, scene.render.resolution_y = (1024, 512) if test else (4096, 2048)
        render_to(os.path.join(sd, "sky.jpg")); scene.camera = cam
        for o in hid: o.hide_render = False
        json.dump({"file": "skytree.spz", "offset": [CX, CY, 0.0], "views": len(frames), "sky_yaw_deg": 0.0}, open(os.path.join(sd, "meta.json"), "w"))
    elif ps == "garden_panos":
        # standing 360s in the podium terrace garden and the west-tower rooftop garden (day + night)
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 256)); scene.frame_set(1); clear_view(Vector((0, -9999, 999)), 0)
        cd = bpy.data.cameras.new("GardenPano"); cd.type = "PANO"
        try: cd.panorama_type = "EQUIRECTANGULAR"
        except Exception: cd.cycles.panorama_type = "EQUIRECTANGULAR"
        gc = bpy.data.objects.new("GardenPano", cd); scene.collection.objects.link(gc); scene.camera = gc
        scene.render.resolution_x, scene.render.resolution_y = 4096, 2048
        for nm, loc, yaw in (("terrace", (-158.0, -15.5, 24.8 + 1.65), 0.0), ("rooftop", (-173.5, -8.5, 79.05 + 1.65), 0.0)):
            gc.location = loc; gc.rotation_euler = (math.radians(90), 0, math.radians(yaw))   # yaw 0: looking toward the back (+y) of the tower
            for md, suf in (("day", ""), ("night", "@night")):
                set_mode(md); t = time.time()
                if render_to(os.path.join(OUT, "pano", f"{nm}{suf}.jpg")): log(f"garden pano {nm}{suf}: {time.time() - t:.0f}s")
        set_mode("day"); scene.camera = cam
    elif ps == "lookdev4":
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 64)); set_mode("golden"); fill_light(True)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        d = os.path.join(RENDER_DIR, "out", "lookdev4"); clear_view(Vector((0, -9999, 999)), 0)
        V = {"terrace_aerial": ((CX, -78.0, 66.0), (CX, -14.0, 24.0), 32), "terrace_eye": ((-163.6, -23.6, 26.4), (-150.0, -6.0, 26.6), 22),
             "terrace_top": ((CX, -13.0, 75.0), (CX, -12.9, 24.0), 26), "roof_left": ((-196.0, -40.0, 98.0), (-172.0, -8.0, 80.0), 30),
             "ground_front": ((CX, -63.0, 1.7), (CX, -38.0, 7.0), 24), "ground_hotel": ((-128.5, -58.0, 1.7), (-150.0, -38.0, 4.0), 26),
             "aerial_ref": ((-95.0, -150.0, 130.0), (CX, -10.0, 30.0), 30), "front_ref": ((CX, -150.0, 25.0), (CX, -5.0, 45.0), 30)}
        for k, (P_, T_, lens) in V.items():
            look(cam, Vector(P_), Vector(T_)); cam.data.lens = lens; render_to(os.path.join(d, k + ".jpg"))
        cam.data.lens = ORBIT["lens"]
    elif ps == "inspect3":
        # height map of every surface you could stand on, from above: finds the podium terrace and the tower roofs
        dg = bpy.context.evaluated_depsgraph_get(); hm = []
        for gy in range(-58, 32):
            row = []
            for gx in range(-192, -110):
                hit, loc, nrm, idx, ob, mw = scene.ray_cast(dg, Vector((gx + 0.5, gy + 0.5, 250.0)), Vector((0, 0, -1)), distance=260)
                row.append([round(loc.z, 2), ob.name if hit else "", (ob.active_material.name if hit and ob.active_material else "")] if hit else [0, "", ""])
            hm.append(row)
        os.makedirs(os.path.join(RENDER_DIR, "out", "inspect"), exist_ok=True)
        json.dump({"x0": -192, "y0": -58, "rows": hm}, open(os.path.join(RENDER_DIR, "out", "inspect", "heights.json"), "w"))
        cam.data.type = "ORTHO"; cam.data.ortho_scale = 95; cam.location = (CX, CY, 260); cam.rotation_euler = (0, 0, 0)
        scene.render.resolution_x = scene.render.resolution_y = 1600; set_mode("day")
        render_to(os.path.join(RENDER_DIR, "out", "inspect", "roof_top.jpg"))
        cam.data.type = "PERSP"
        log("inspect3 done")
    elif ps == "inspect2":
        rows = []; mats = {}
        for o in bpy.data.objects:
            if o.type not in ("MESH", "FONT", "CURVE") or o.hide_render: continue
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))); hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
            if not (-200 < lo.x and hi.x < -110 and -60 < lo.y and hi.y < 40 and hi.z > 6): continue
            ms = [sl.material.name for sl in o.material_slots if sl.material]
            for m in ms: mats[m] = mats.get(m, 0) + 1
            d = hi - lo
            if max(d) < 30: rows.append({"n": o.name, "t": o.type, "lo": [round(v, 1) for v in lo], "hi": [round(v, 1) for v in hi], "m": ms, "v": len(o.data.vertices) if o.type == "MESH" else 0})
        os.makedirs(os.path.join(RENDER_DIR, "out", "inspect"), exist_ok=True)
        json.dump({"mats": mats, "objs": rows}, open(os.path.join(RENDER_DIR, "out", "inspect", "bldg.json"), "w"), indent=0)
        log(f"inspect2: {len(rows)} objects, {len(mats)} materials")
    elif ps == "lookdev3":
        cycles_setup(64); set_mode("golden"); fill_light(True)
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        for key in PATHS:
            P, T, lens = path_pose(key, 20); clear_view(P, T.z); look(cam, P, T); cam.data.lens = lens
            render_to(os.path.join(RENDER_DIR, "out", "lookdev3", f"{key}_20.jpg"))
        for key, i in (("g1", 12), ("m1", 32), ("g1", 32)):
            P, T, lens = path_pose(key, i); clear_view(P, T.z); look(cam, P, T); cam.data.lens = lens
            render_to(os.path.join(RENDER_DIR, "out", "lookdev3", f"{key}_{i}.jpg"))
        look(cam, Vector((CX, -62.0, 14.0)), Vector((CX, -30.0, 24.0))); cam.data.lens = 50
        render_to(os.path.join(RENDER_DIR, "out", "lookdev3", "sign.jpg"))
        clear_view(Vector((0, -9999, 999)), 0)
        look(cam, Vector((CX + 20.0, -96.0, 2.2)), Vector((CX - 5.0, -30.0, 6.0))); cam.data.lens = 24
        render_to(os.path.join(RENDER_DIR, "out", "lookdev3", "forecourt.jpg"))
        look(cam, Vector((-100.0, -70.0, 8.0)), Vector((-122.0, -5.0, 1.0))); cam.data.lens = 28
        render_to(os.path.join(RENDER_DIR, "out", "lookdev3", "parking.jpg"))
        cam.data.lens = ORBIT["lens"]
    elif ps == "paths":
        cycles_setup(int(os.environ.get("ST_SAMPLES") or 96)); set_mode("golden"); fill_light(True)
        scene.render.resolution_x, scene.render.resolution_y = 2560, 1440
        order = [k.strip() for k in (os.environ.get("ST_PATHS") or "m2,g2,h2,m1,m3,g1,g3,h1,h3").split(",")]
        for key in order:
            for i in range(PATH_N):
                P, T, lens = path_pose(key, i); clear_view(P, T.z); look(cam, P, T); cam.data.lens = lens
                p = os.path.join(OUT, "p", key, "day", f"f_{i:03d}.jpg"); t = time.time()
                if render_to(p): log(f"path {key} {i:03d}: {time.time() - t:.0f}s")
        clear_view(Vector((0, -9999, 999)), 0); cam.data.lens = ORBIT["lens"]
    elif ps == "lookdev2":
        cycles_setup(128); set_mode("golden")
        scene.render.resolution_x, scene.render.resolution_y = 1600, 900
        loc, tgt = orbit_pose(20); look(cam, loc, tgt); cam.data.lens = ORBIT["lens"]
        render_to(os.path.join(RENDER_DIR, "out", "lookdev2", "aerial_golden.jpg"))
        loc, tgt = orbit_pose(28); look(cam, loc, tgt)
        render_to(os.path.join(RENDER_DIR, "out", "lookdev2", "aerial_golden_b.jpg"))
        for k, az in enumerate((0.0, 35.0)):
            P, T = ground_pose_az(az); look(cam, P, T); cam.data.lens = GROUND["lens"]
            render_to(os.path.join(RENDER_DIR, "out", "lookdev2", f"ground_golden_{k}.jpg"))
        cam.data.lens = ORBIT["lens"]
    elif ps == "orbit_ground":
        cycles_setup(256); set_mode("golden")
        for i in range(GROUND["count"]):
            P, T = ground_pose(i); look(cam, P, T); cam.data.lens = GROUND["lens"]
            p = os.path.join(OUT, "ground", "day", f"g_{i:03d}.jpg"); t = time.time()
            if render_to(p): log(f"ground {i:03d}: {time.time() - t:.0f}s")
        cam.data.lens = ORBIT["lens"]
    elif ps == "orbit_golden":
        cycles_setup(256); set_mode("golden"); do_orbit("golden")
    elif ps == "stills":
        cycles_setup(384); scene.render.resolution_x, scene.render.resolution_y = (640, 360) if QUICK else (2560, 1440)
        for cname, mode in (("CAM_front", "day"), ("CAM_aerial", "day"), ("CAM_corner", "day"), ("CAM_entrance", "day"),
                            ("CAM_front", "dusk"), ("CAM_front", "night"), ("CAM_corner", "night")):
            c = bpy.data.objects.get(cname)
            if not c: continue
            scene.camera = c; set_mode(mode)
            t = time.time()
            if render_to(os.path.join(OUT, "stills", f"{cname[4:]}_{mode}.jpg")): log(f"still {cname} {mode}: {time.time() - t:.0f}s")
        scene.camera = cam
log("Done")
