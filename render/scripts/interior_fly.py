"""
1.2 s fly-through clip from a 360 spot toward a hotspot (e.g. the window to the balcony), for tour transitions.

  blender -b assets/bk/<room>/<room>.blend --python scripts/interior_fly.py -- <room> <yaw_deg> <dist_m> <name>

Uses out/web/pano/<room>.spot.json (written by interior_pano.py).  The first frame matches the 360 viewer looking at
<yaw_deg> with a 100 deg horizontal field of view; the camera eases forward <dist_m> metres with motion blur and the
last frames bloom to white so the hand-off into the next 360 is seamless.  Frames -> out/web/trans/<name>/f_###.jpg
"""
import bpy, os, sys, math, json
from mathutils import Vector, Euler
argv = sys.argv[sys.argv.index("--") + 1:]
ROOM, YAW, DIST, NAME = argv[0], float(argv[1]), float(argv[2]), argv[3]
PITCH = float(argv[4]) if len(argv) > 4 else 0.0
HERE = os.path.dirname(os.path.abspath(__file__)); RENDER = os.path.dirname(HERE)
spot = json.load(open(os.path.join(RENDER, "out", "web", "pano", ROOM + ".spot.json")))
OUT = os.path.join(RENDER, "out", "web", "trans", NAME); os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
eye = Vector(spot["eye"]); yaw = math.radians(YAW)
d = Vector((math.sin(yaw), math.cos(yaw), 0.0))
# stop short of whatever is ahead (glass, curtain, wall)
dg = bpy.context.evaluated_depsgraph_get()
hit, loc, *_ = scene.ray_cast(dg, eye, d, distance=DIST + 1.0)
dist = min(DIST, (loc - eye).length - 0.45) if hit else DIST
print(f"fly {NAME}: {ROOM} yaw {YAW} dist {dist:.2f} (asked {DIST})")
cd = bpy.data.cameras.new("Fly"); cd.lens = 15.1; cd.sensor_width = 36.0; cd.sensor_fit = "HORIZONTAL"; cd.clip_start = 0.05
cam = bpy.data.objects.new("Fly", cd); scene.collection.objects.link(cam); scene.camera = cam
N = 36
scene.frame_start, scene.frame_end = 1, N
scene.render.fps = 30
for f in range(1, N + 1):
    t = (f - 1) / (N - 1); e = t * t * (3 - 2 * t) if t < 1 else 1.0
    e = 0.5 * e + 0.5 * t * t        # ease-in heavier: accelerating "launch" feel
    cam.location = eye + d * dist * e + Vector((0, 0, math.sin(math.radians(PITCH)) * dist * e))
    cam.rotation_euler = Euler((math.radians(90 + PITCH), 0.0, -yaw), "XYZ")
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for dv in prefs.devices: dv.use = dv.type != "CPU"
    scene.cycles.device = "GPU"
except Exception as ex: print("GPU:", ex)
scene.cycles.samples = int(os.environ.get("ST_FLY_SAMPLES") or 64); scene.cycles.use_denoising = True
scene.render.use_motion_blur = True; scene.render.motion_blur_shutter = 0.9
scene.render.resolution_x, scene.render.resolution_y = 1600, 900; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.quality = 90
base_exp = scene.view_settings.exposure
for f in range(1, N + 1):
    scene.frame_set(f)
    t = (f - 1) / (N - 1); scene.view_settings.exposure = base_exp + (max(0.0, (t - 0.72) / 0.28) ** 2) * 3.2   # bloom out
    scene.render.filepath = os.path.join(OUT, f"f_{f:03d}.jpg")
    if not os.path.exists(scene.render.filepath): bpy.ops.render.render(write_still=True)
open(os.path.join(OUT, "done.txt"), "w").write("ok")
print("FLY DONE", NAME)
