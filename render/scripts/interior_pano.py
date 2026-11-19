"""
Render a 360 equirectangular panorama of a downloaded interior scene (unit 10-A demo tour).

  blender -b assets/bk/<room>/<room>.blend --python scripts/interior_pano.py -- <room> [--quick]

Finds the most open spot inside the room (rays to walls / floor / ceiling), stands a camera there at eye
height (1.55 m) and renders out/web/pano/<room>.jpg (4096 x 2048).
"""
import bpy, os, sys, math, time
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ROOM = argv[0] if argv else "room"
QUICK = "--quick" in argv
HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.dirname(HERE)
OUT = os.path.join(RENDER, "out", "web", "pano"); os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

def ray(o, d, dist=60.0):
    hit, loc, n, i, ob, mt = scene.ray_cast(dg, o, d, distance=dist)
    return (loc - o).length if hit else None

# search bounds: around the scene's own camera(s) and the mesh bounds
mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
for o in scene.objects:
    if o.type == "MESH" and not o.hide_render:
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
dirs = [Vector((math.cos(a), math.sin(a), 0)) for a in [k * math.tau / 32 for k in range(32)]]
step = max(0.25, max(mx.x - mn.x, mx.y - mn.y) / 40)
grid = []
x = mn.x + step
while x < mx.x:
    y = mn.y + step
    while y < mx.y:
        grid.append((x, y)); y += step
    x += step
# pass 1: the real floor height = the most common surface found under the ceiling
zs = []
for (x, y) in grid:
    hit, c, *_ = scene.ray_cast(dg, Vector((x, y, mx.z - 0.05)), Vector((0, 0, -1)), distance=(mx.z - mn.z) + 1)
    if not hit: continue
    hit2, f, *_ = scene.ray_cast(dg, Vector((x, y, c.z - 0.05)), Vector((0, 0, -1)), distance=8)
    if hit2: zs.append(round(f.z / 0.05) * 0.05)
from collections import Counter
floor_z = Counter(zs).most_common(1)[0][0] if zs else mn.z
# pick the reference camera: an existing 360 camera if the scene has one, else the perspective camera
# nearest the room centre at eye height
cams = [o for o in scene.objects if o.type == "CAMERA"]
pano_cams = [o for o in cams if o.data.type == "PANO"]
ctr = (mn + mx) / 2
persp = [o for o in cams if o.data.type == "PERSP" and 0.8 < (o.matrix_world.translation.z - mn.z) < 3.0] or [o for o in cams if o.data.type == "PERSP"]
ref = pano_cams[0] if pano_cams else (min(persp, key=lambda o: (o.matrix_world.translation - ctr).length) if persp else scene.camera)
hint = None
if ref is not None:
    cl = ref.matrix_world.translation.copy()
    near = [z for z in zs if cl.z - 2.6 < z < cl.z - 0.4]
    if near: floor_z = Counter(near).most_common(1)[0][0]
    if pano_cams:
        grid = [(cl.x, cl.y)] + [(x, y) for (x, y) in grid if (Vector((x, y, 0)) - Vector((cl.x, cl.y, 0))).length < 2.5]
    else:
        fwd = ref.matrix_world.to_3x3() @ Vector((0, 0, -1)); fwd.z = 0
        if fwd.length > 1e-3: fwd.normalize()
        hint = cl + fwd * 3.0
        grid = [(x, y) for (x, y) in grid if (Vector((x, y, 0)) - Vector((hint.x, hint.y, 0))).length < 7.0]
print(f"reference camera {ref.name if ref else None}, floor at z={floor_z:.2f}")
# pass 2: the most open eye-height spot standing on that floor
best = None
for (x, y) in grid:
    eye = Vector((x, y, floor_z + 1.55))
    down = ray(eye, Vector((0, 0, -1)), 3); up = ray(eye, Vector((0, 0, 1)), 8)
    if down is None or up is None or abs(down - 1.55) > 0.08 or up < 0.6:
        continue
    ds = [ray(eye, d, 25) for d in dirs]
    if any(v is None for v in ds): continue
    score = min(ds) * 2.0 + sum(ds) / len(ds) * 0.25
    if min(ds) > 0.7 and (best is None or score > best[0]):
        best = (score, eye.copy(), min(ds), sum(ds) / len(ds))

cam_obj = ref or scene.camera
if best is None and cam_obj:
    eye = cam_obj.matrix_world.translation.copy(); eye.z = max(eye.z, 1.4)
    print("no open spot found, using the scene camera")
else:
    eye = best[1]; print(f"spot {tuple(round(v, 2) for v in eye)} clearance {best[2]:.2f} m, mean {best[3]:.2f} m")
cd = bpy.data.cameras.new("Pano"); cd.type = "PANO"
try:
    cd.panorama_type = "EQUIRECTANGULAR"
except Exception:
    cd.cycles.panorama_type = "EQUIRECTANGULAR"
cd.clip_start = 0.05
cam = bpy.data.objects.new("Pano", cd); scene.collection.objects.link(cam)
cam.location = eye; cam.rotation_euler = (math.radians(90), 0, 0)     # looking +Y at the horizon
scene.camera = cam
scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for d in prefs.devices: d.use = d.type != "CPU"
    scene.cycles.device = "GPU"
except Exception as e:
    print("GPU:", e)
scene.cycles.samples = 16 if QUICK else 384
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = (1024, 512) if QUICK else (4096, 2048)
scene.render.resolution_percentage = 100
scene.render.use_border = False
scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.quality = 90
scene.render.filepath = os.path.join(OUT, f"{ROOM}.jpg")
t = time.time()
if not os.path.exists(scene.render.filepath) or "--force" in argv:
    bpy.ops.render.render(write_still=True)
print(f"PANO {ROOM}: {time.time() - t:.0f}s -> {scene.render.filepath}")

# --lights: the same camera, same projection, only the light changes (morning / sunset / night previews)
if "--lights" in argv:
    suns = [o for o in scene.objects if o.type == "LIGHT" and o.data.type == "SUN" and not o.hide_render]
    lamps = [o for o in scene.objects if o.type == "LIGHT" and o.data.type != "SUN" and not o.hide_render]
    w = scene.world; bgs = [n for n in w.node_tree.nodes if n.type == "BACKGROUND"] if w and w.use_nodes else []
    base = {"sun": [(o, o.rotation_euler.copy(), o.data.energy, tuple(o.data.color)) for o in suns],
            "lamp": [(o, o.data.energy) for o in lamps], "bg": [(n, n.inputs["Strength"].default_value, tuple(n.inputs["Color"].default_value)) for n in bgs],
            "exp": scene.view_settings.exposure}
    emit = []
    for m in bpy.data.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "EMISSION": emit.append((n.inputs["Strength"], n.inputs["Strength"].default_value))
                elif n.type == "BSDF_PRINCIPLED" and n.inputs["Emission Strength"].default_value > 0: emit.append((n.inputs["Emission Strength"], n.inputs["Emission Strength"].default_value))
    LOOKS = {   # sun elevation change (deg), sun colour, sun x, sky x, sky tint, lamps x, exposure +
        "morning": (-18, (1.0, 0.86, 0.72), 0.75, 0.75, (0.92, 0.96, 1.08), 0.6, 0.15),
        "sunset":  (-30, (1.0, 0.56, 0.30), 0.55, 0.40, (1.10, 0.86, 0.70), 1.0, 0.35),
        "night":   (None, None, 0.0, 0.025, (0.55, 0.65, 1.0), 2.2, 1.2)}
    for name, (del_el, scol, sk, wk, tint, lk, ex) in LOOKS.items():
        out = os.path.join(OUT, f"{ROOM}@{name}.jpg")
        if os.path.exists(out) and "--force" not in argv: continue
        for o, rot, en, col in base["sun"]:
            o.rotation_euler = rot.copy(); o.data.energy = en * sk; o.hide_render = sk == 0
            if del_el is not None: o.rotation_euler.x = rot.x + math.radians(-del_el) * (1 if rot.x >= 0 else -1)
            if scol: o.data.color = scol
        for n, st, col in base["bg"]:
            n.inputs["Strength"].default_value = st * wk
            if not n.inputs["Color"].is_linked: n.inputs["Color"].default_value = tuple(c * t for c, t in zip(col[:3], tint)) + (1,)
        for o, en in base["lamp"]: o.data.energy = en * lk
        for sock, v in emit: sock.default_value = v * lk
        scene.view_settings.exposure = base["exp"] + ex
        scene.render.filepath = out; t = time.time(); bpy.ops.render.render(write_still=True)
        print(f"PANO {ROOM}@{name}: {time.time() - t:.0f}s")
    for o, rot, en, col in base["sun"]: o.rotation_euler = rot; o.data.energy = en; o.data.color = col; o.hide_render = False
