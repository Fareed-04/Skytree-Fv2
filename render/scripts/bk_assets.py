"""
Load the downloaded BlenderKit models (render/assets/bk/<slug>/<slug>.blend|.glb) as instanceable collections.

Each loaded asset becomes a collection "BK_<slug>" (excluded from the view layer) with:
  instance_offset  at the base centre, so an instancing empty placed on the ground stands on it
  ["scale"]        factor that brings it to the manifest target size (height for plants, length for vehicles)
  ["yaw"]          rotation (rad) that turns its length axis onto world X (vehicles)
  ["kind"]         car / bus / palm / tree / shrub / flower / topiary
"""
import bpy, os, json, math
from mathutils import Vector

MAX_TEX = 1024

JUNK = ("plane", "floor", "ground", "backdrop", "studio", "shadow", "catcher", "cyclo", "background", "scale_ref",
        "human", "person", "dummy", "colorchecker", "color_checker", "macbeth")

def _bounds(objs):
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9)); n = 0
    for o in objs:
        if o.type != "MESH" or o.hide_render:
            continue
        for v in o.bound_box:
            w = o.matrix_world @ Vector(v); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w)); n += 1
    return (mn, mx) if n else (Vector(), Vector())

def _is_junk(o, kind):
    nm = o.name.lower()
    if nm.startswith("wgt") or (o.type == "MESH" and len(o.data.materials) == 0 and o.data.polygons and kind in ("car", "bus")):
        return True
    if any(j in nm for j in JUNK) and o.type == "MESH":
        d = o.dimensions
        flat = d.z < 0.08 * max(d.x, d.y, 1e-6)
        if flat or any(j in nm for j in ("human", "person", "dummy", "checker", "scale_ref")):
            return True
    return False

def load(render_dir, slug, info, parent_coll, log=print):
    d = os.path.join(render_dir, "assets", "bk", slug)
    blend = os.path.join(d, slug + ".blend"); glb = os.path.join(d, slug + ".glb")
    kind = info["kind"]
    before = set(bpy.data.objects)
    coll = bpy.data.collections.new(f"BK_{slug}"); parent_coll.children.link(coll)
    try:
        if os.path.exists(blend):
            with bpy.data.libraries.load(blend, link=False) as (src, dst):
                dst.objects = list(src.objects)
            new = [o for o in dst.objects if o is not None]
        elif os.path.exists(glb):
            bpy.ops.import_scene.gltf(filepath=glb)
            new = [o for o in bpy.data.objects if o not in before]
            for o in new:
                for uc in list(o.users_collection): uc.objects.unlink(o)
        else:
            log(f"  {slug}: not downloaded"); bpy.data.collections.remove(coll); return None
    except Exception as e:
        log(f"  {slug}: load failed {e}"); bpy.data.collections.remove(coll); return None
    keep = []
    for o in new:
        if o.type in ("LIGHT", "CAMERA", "LIGHT_PROBE", "SPEAKER"):
            continue
        if _is_junk(o, kind):
            continue
        coll.objects.link(o); keep.append(o)
        for md in getattr(o, "modifiers", []):        # keep render geometry sane (12 GB GPU, many instances)
            if md.type == "SUBSURF":
                md.render_levels = 0; md.levels = 0
            elif md.type == "MULTIRES":
                md.render_levels = min(md.render_levels, 1)
    for o in keep:                     # true displacement would subdivide millions of leaves: bump only
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m is not None:
                try: m.displacement_method = "BUMP"
                except Exception: pass
    # shrink the asset's textures (cars/trees are small on screen; 4K maps would not fit a 12 GB GPU)
    seen = set()
    def walk(nt):
        for nd in nt.nodes:
            if nd.type == "TEX_IMAGE" and nd.image and nd.image.name not in seen:
                seen.add(nd.image.name); im = nd.image
                try:
                    w, h = im.size
                    if max(w, h) > MAX_TEX:
                        f = MAX_TEX / max(w, h); im.scale(max(1, int(w * f)), max(1, int(h * f)))
                        if im.packed_file is None and im.filepath:
                            im.pack()
                except Exception:
                    pass
            elif nd.type == "GROUP" and nd.node_tree:
                walk(nd.node_tree)
    for o in keep:
        for slot in getattr(o, "material_slots", []):
            if slot.material and slot.material.node_tree:
                walk(slot.material.node_tree)
    # objects that are only particle/instance sources must stay out of the render at their own spot
    bpy.context.view_layer.update()
    mn, mx = _bounds(keep)
    size = mx - mn
    if size.length < 1e-4:
        log(f"  {slug}: empty"); return None
    coll.instance_offset = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    if kind in ("car", "bus"):
        length = max(size.x, size.y)
        coll["yaw"] = 0.0 if size.x >= size.y else math.pi / 2     # turn length onto world X
        coll["scale"] = info["target"] / length if length > 0.5 else 1.0
        # real cars are 1.3-2.1 m tall: if the asset is clearly not in metres, trust the target length
    else:
        coll["yaw"] = 0.0
        coll["scale"] = info["target"] / size.z if size.z > 0.05 else 1.0
    coll["kind"] = kind; coll["size"] = list(size); coll["height"] = size.z   # native height (plant() rescales)
    log(f"  {slug:15s} {kind:7s} size {size.x:5.1f} x {size.y:5.1f} x {size.z:5.1f} m  -> scale {coll['scale']:.2f}  ({len(keep)} objects)")
    return coll

def load_all(render_dir, parent_name="bk_lib", log=print):
    man = os.path.join(render_dir, "blenderkit_assets.json")
    if not os.path.exists(man):
        return {}
    items = json.load(open(man))
    parent = bpy.data.collections.get(parent_name) or bpy.data.collections.new(parent_name)
    if parent.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(parent)
    out = {}
    for it in items:
        c = load(render_dir, it["slug"], it, parent, log)
        if c: out[it["slug"]] = c
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.name == parent_name:
            lc.exclude = True
    return out
