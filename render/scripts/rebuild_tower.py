"""
Rebuild the missing tower floors and re-seat the podium pavilions, to match the client's renders.

  blender -b scene/sky-tree.blend --python scripts/rebuild_tower.py [-- --quick] [-- --no-render]

The model in 1.max has 6 tower floors (slabs every 3.5 m from 24.75 m); the client's renders show 11.
The upper band (floors at 38.75 and 42.25 m) is identical on every face, so the slice between two
quiet mid-wall heights (40.5 .. 44.0 m) is repeated ADD_FLOORS times:
  - geometry below 40.5 m stays,
  - geometry above 44.0 m (crown, roofs) moves up by ADD_FLOORS * 3.5 m,
  - geometry in the slice is repeated (whole objects as linked instances, cut objects as shared cut meshes).
Objects that cross a cut plane are split there, so pilasters, walls and glazing continue seamlessly.

The two domed pavilions that float beside the podium are moved onto the podium roof at its front corners,
which is where the client's Front Cam and aerial renders show them.

Writes scene/sky-tree-v2.blend (sky-tree.blend is left as it is), scene/rebuild-log.txt and previews
scene/v2_*.jpg.
"""
import bpy, bmesh, math, os, sys, time, json
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in ARGV
NO_RENDER = "--no-render" in ARGV
SRC = bpy.data.filepath
OUT = os.path.dirname(SRC) if SRC else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scene")

PITCH = 3.5          # floor-to-floor (m)
CUT_LO = 40.5        # bottom of the repeated slice (mid-wall, floor 38.75)
CUT_HI = CUT_LO + PITCH
ADD_FLOORS = 5
LIFT = ADD_FLOORS * PITCH

PODIUM_ROOF = 24.75  # top of the podium slab
PODIUM_X = (-182.0, -134.0)
PAVILION_INSET = 6.5 # pavilion centre, metres in from the podium side
PAVILION_Y_SHIFT = 1.0

T0 = time.time()
LOG = open(os.path.join(OUT, "rebuild-log.txt"), "w")
def log(m):
    s = f"[{time.time() - T0:7.1f}s] {m}"
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

def world_bounds(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(v[i] for v in bb) for i in range(3)]), Vector([max(v[i] for v in bb) for i in range(3)])

def link_like(new, src):
    for c in src.users_collection:
        c.objects.link(new)

# ------------------------------------------------------------------ 0. flatten parenting (keep world transforms)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
for o in bpy.data.objects:
    if o.parent is not None:
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
log(f"{len(meshes)} mesh objects")

# ------------------------------------------------------------------ 1. pavilions onto the podium roof
pav = []
for o in meshes:
    mn, mx = world_bounds(o)
    c = (mn + mx) / 2
    if (c.x < PODIUM_X[0] - 0.5 or c.x > PODIUM_X[1] + 0.5) and 17.0 < mn.z and mx.z < 30.5 and mx.y < -24.0:
        pav.append(o)
sides = {"L": [o for o in pav if world_bounds(o)[0].x < PODIUM_X[0]],
         "R": [o for o in pav if world_bounds(o)[0].x >= PODIUM_X[0]]}
for side, grp in sides.items():
    if not grp:
        continue
    mn = Vector((min(world_bounds(o)[0][i] for o in grp) for i in range(3)))
    mx = Vector((max(world_bounds(o)[1][i] for o in grp) for i in range(3)))
    cx = (mn.x + mx.x) / 2
    tx = PODIUM_X[0] + PAVILION_INSET if side == "L" else PODIUM_X[1] - PAVILION_INSET
    d = Vector((tx - cx, PAVILION_Y_SHIFT, PODIUM_ROOF - mn.z))
    for o in grp:
        o.matrix_world = Matrix.Translation(d) @ o.matrix_world
    log(f"Pavilion {side}: {len(grp)} objects moved by ({d.x:.2f}, {d.y:.2f}, {d.z:.2f}) m")

# ------------------------------------------------------------------ 2. classify against the slice
def cut_mesh(me, mw, lo, hi):
    """Return (below, middle, above) new meshes (or None) of mesh `me` cut by world planes z=lo, z=hi."""
    inv = mw.inverted()
    m3t = mw.to_3x3().transposed()
    n_local = (m3t @ Vector((0, 0, 1))).normalized()
    out = []
    for keep in ("below", "middle", "above"):
        bm = bmesh.new(); bm.from_mesh(me)
        def cut(z, clear_outer):
            co = inv @ Vector((0, 0, z))
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co, plane_no=n_local,
                                   clear_outer=clear_outer, clear_inner=not clear_outer)
        if keep == "below":
            cut(lo, True)
        elif keep == "above":
            cut(hi, False)
        else:
            cut(lo, False); cut(hi, True)
        if len(bm.faces) == 0:
            out.append(None); bm.free(); continue
        nm = bpy.data.meshes.new(f"{me.name}_{keep}")
        bm.to_mesh(nm); bm.free()
        for mat in me.materials:
            nm.materials.append(mat)
        try:
            nm.set_sharp_from_angle(angle=math.radians(35))
        except Exception:
            pass
        out.append(nm)
    return out

keep_n = up_n = slice_n = cut_n = 0
cut_polys = 0
lift_m = Matrix.Translation((0, 0, LIFT))
cut_cache = {}   # (mesh name, matrix key) -> pieces, so identical instances are only cut once
for o in list(meshes):
    if o.name not in bpy.data.objects:
        continue
    mn, mx = world_bounds(o)
    if mx.z <= CUT_LO + 1e-4:
        keep_n += 1
        continue
    if mn.z >= CUT_HI - 1e-4:
        o.matrix_world = lift_m @ o.matrix_world
        up_n += 1
        continue
    if mn.z >= CUT_LO - 1e-4 and mx.z <= CUT_HI + 1e-4:
        for k in range(1, ADD_FLOORS + 1):
            c = o.copy()                      # linked duplicate, shares the mesh
            c.matrix_world = Matrix.Translation((0, 0, k * PITCH)) @ o.matrix_world
            link_like(c, o)
        slice_n += 1
        continue
    # crosses a cut plane: split in object space. Pieces are shared by instances with the same
    # mesh and the same height/orientation (they differ only in x/y translation).
    mw = o.matrix_world.copy()
    key = (o.data.name, tuple(round(v, 4) for r in mw.to_3x3() for v in r), round(mw.translation.z, 4))
    if key in cut_cache:
        pieces = cut_cache[key]
    else:
        pieces = cut_mesh(o.data, mw, CUT_LO, CUT_HI)
        cut_cache[key] = pieces
        cut_polys += len(o.data.polygons)
    below, middle, above = pieces
    if middle is not None:
        for k in range(0, ADD_FLOORS + 1):
            c = bpy.data.objects.new(f"{o.name}_mid{k}", middle)
            c.matrix_world = Matrix.Translation((0, 0, k * PITCH)) @ mw
            link_like(c, o)
    if above is not None:
        c = bpy.data.objects.new(f"{o.name}_up", above)
        c.matrix_world = lift_m @ mw
        link_like(c, o)
    if below is not None:
        o.data = below
    else:
        bpy.data.objects.remove(o)
    cut_n += 1
    if cut_n % 20 == 0:
        log(f"  cut {cut_n} objects ...")

for me in [m for m in bpy.data.meshes if m.users == 0]:
    bpy.data.meshes.remove(me)
log(f"Kept {keep_n}, lifted {up_n}, repeated {slice_n} whole objects x{ADD_FLOORS}, cut {cut_n} objects "
    f"({len(cut_cache)} unique cuts, {cut_polys/1e6:.1f}M polys)")
log(f"Added {ADD_FLOORS} floors of {PITCH} m (slice {CUT_LO}..{CUT_HI} m); everything above rose {LIFT} m")

# ------------------------------------------------------------------ 3. save
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "sky-tree-v2.blend"), compress=False)
log("Saved scene/sky-tree-v2.blend")

# ------------------------------------------------------------------ 4. previews
if not NO_RENDER:
    scene = bpy.context.scene
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"; prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        scene.cycles.device = "GPU"
    except Exception as e:
        log(f"GPU setup: {e}")
    bmn = Vector((PODIUM_X[0], -32.0, 0.0)); bmx = Vector((PODIUM_X[1], 21.0, 64.6 + LIFT))
    ctr = (bmn + bmx) / 2
    cam = scene.camera
    if cam is None:
        cd = bpy.data.cameras.new("Preview"); cam = bpy.data.objects.new("Preview", cd)
        scene.collection.objects.link(cam); scene.camera = cam
    cam.data.clip_end = 20000
    scene.render.resolution_x, scene.render.resolution_y = (640, 360) if QUICK else (1920, 1080)
    scene.cycles.samples = 8 if QUICK else 96
    scene.render.image_settings.file_format = "JPEG"
    views = {   # name: (azimuth deg, elevation deg, distance m, lens mm, look-at height m)
        "front": (0, 4, 230, 50, 42),        # like the client's Front Cam
        "aerial": (35, 38, 260, 40, 30),
        "east": (90, 10, 200, 40, 40),
        "south_close": (0, 12, 120, 35, 40),
    }
    for name, (az, el, dist, lens, h) in views.items():
        tgt = Vector((ctr.x, ctr.y, h))
        d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                    -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
        cam.location = tgt + d * dist
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        scene.render.filepath = os.path.join(OUT, f"v2_{name}.jpg")
        t = time.time(); bpy.ops.render.render(write_still=True)
        log(f"Preview v2_{name}: {time.time() - t:.0f}s")
log("Done")
LOG.close()
