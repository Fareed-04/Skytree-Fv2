"""
Export a light copy of scene/sky-tree.blend for analysis (floor/bay positions for the rebuild).

  blender -b scene/sky-tree.blend --python scripts/export_lite.py

Writes (sky-tree.blend itself is not changed):
  scene/lite.glb             every unique mesh decimated to ~5 %, instances kept
  scene/scene-objects.json   object name, collection, mesh name, world bounds, matrix
"""
import bpy, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "scene")
RATIO = 0.05
t0 = time.time()
def log(m):
    print(f"[{time.time()-t0:7.1f}s] {m}", flush=True)

objs = [o for o in bpy.data.objects if o.type == "MESH"]
rows = []
for o in objs:
    bb = [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
    rows.append({
        "name": o.name, "mesh": o.data.name,
        "col": o.users_collection[0].name if o.users_collection else "",
        "polys": len(o.data.polygons),
        "min": [round(min(v[i] for v in bb), 3) for i in range(3)],
        "max": [round(max(v[i] for v in bb), 3) for i in range(3)],
        "matrix": [[round(x, 5) for x in r] for r in o.matrix_world],
        "mats": [s.material.name if s.material else None for s in o.material_slots],
    })
json.dump(rows, open(os.path.join(OUT, "scene-objects.json"), "w"), indent=0)
log(f"scene-objects.json: {len(rows)} objects")

# decimate each unique mesh once, keep sharing
dg = bpy.context.evaluated_depsgraph_get()
meshes = {o.data for o in objs}
tmp_col = bpy.data.collections.new("tmp"); bpy.context.scene.collection.children.link(tmp_col)
for i, me in enumerate(meshes):
    if len(me.polygons) > 200:
        t = bpy.data.objects.new("tmp", me); tmp_col.objects.link(t)
        m = t.modifiers.new("d", "DECIMATE"); m.ratio = RATIO; m.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        new = bpy.data.meshes.new_from_object(t.evaluated_get(dg))
        new.name = me.name + "_lite"
        me.user_remap(new)
        bpy.data.objects.remove(t)
    if i % 50 == 0:
        log(f"decimated {i}/{len(meshes)}")
bpy.data.collections.remove(tmp_col)
for o in bpy.data.objects:
    if o.type != "MESH":
        o.hide_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "lite.glb"), export_format="GLB",
                          use_visible=True, export_apply=False, export_materials="EXPORT",
                          export_cameras=False, export_lights=False, export_extras=False)
log("lite.glb written. Done (sky-tree.blend not modified).")
