"""
Sky Tree Tower look-dev: materials, sky/lighting (day / dusk / night), landscape, street context, cameras.

  blender -b scene/sky-tree-v2.blend --python scripts/lookdev.py [-- --quick] [-- --no-render] [-- --only front_day]

Writes scene/sky-tree-v3.blend and renders scene/v3_<camera>_<mode>.jpg
Switch modes inside the .blend with the scene property "night" (0 day, 0.5 dusk, 1 night) + world/light
settings applied by apply_mode() below (stored as a text block "set_mode.py" in the .blend).
"""
import bpy, bmesh, math, os, sys, time, random, re, glob
from mathutils import Vector, Matrix, Euler

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in ARGV
NO_RENDER = "--no-render" in ARGV
ONLY = ARGV[ARGV.index("--only") + 1].split(",") if "--only" in ARGV else None

SRC = bpy.data.filepath
SCENE_DIR = os.path.dirname(SRC)
RENDER_DIR = os.path.dirname(SCENE_DIR)
ASSETS = os.path.join(RENDER_DIR, "assets")
MAPS = os.path.join(RENDER_DIR, "from-max", "maps")
random.seed(7)

T0 = time.time()
LOG = open(os.path.join(SCENE_DIR, "lookdev-log.txt"), "w")
def log(m):
    s = f"[{time.time() - T0:7.1f}s] {m}"
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

scene = bpy.context.scene
scene["night"] = 0.0

# ---------------------------------------------------------------- site constants (metres, world)
BX = (-182.0, -134.0)          # podium x extent
CX = (BX[0] + BX[1]) / 2       # building centre x  (-158)
FRONT_Y = -31.0                # podium front face
PLOT = (-184.7, -117.7, -50.0, 24.0)   # x0, x1, y0, y1
TOP_Z = 82.1
ROOF_Z = 77.8                  # above this, sloped stone faces are mansard roof -> slate

# ================================================================ helpers
def tex_path(name, kind, res="4k"):
    p = os.path.join(ASSETS, "textures", name, f"{name}_{kind}_{res}.jpg")
    return p if os.path.exists(p) else None

def load_img(path, colorspace="sRGB"):
    if not path or not os.path.exists(path):
        return None
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.colorspace_settings.name = colorspace
    except Exception:
        img.colorspace_settings.name = "Non-Color" if colorspace != "sRGB" else "sRGB"
    return img

def sock(node, ident):
    for s in list(node.inputs) + list(node.outputs):
        if s.identifier == ident or s.name == ident:
            if s.enabled:
                return s
    for s in list(node.inputs) + list(node.outputs):
        if s.identifier == ident or s.name == ident:
            return s
    raise KeyError(ident)

class NT:
    """Tiny node-tree builder."""
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree; self.nt.nodes.clear(); self.x = 0
    def n(self, kind, **props):
        nd = self.nt.nodes.new(kind); nd.location = (self.x, 0); self.x += 30
        for k, v in props.items():
            setattr(nd, k, v)
        return nd
    def link(self, a, b):
        self.nt.links.new(a, b)
    def val(self, v):
        nd = self.n("ShaderNodeValue"); nd.outputs[0].default_value = v; return nd.outputs[0]
    def rgb(self, c):
        nd = self.n("ShaderNodeRGB"); nd.outputs[0].default_value = (*c, 1); return nd.outputs[0]
    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, (int, float)): nd.inputs[i].default_value = v
            else: self.link(v, nd.inputs[i])
        return nd.outputs[0]
    def mix(self, fac, a, b, blend="MIX"):
        nd = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        for ident, v in (("Factor_Float", fac), ("A_Color", a), ("B_Color", b)):
            s = sock(nd, ident)
            if isinstance(v, (int, float)): s.default_value = v
            elif isinstance(v, tuple): s.default_value = (*v, 1) if len(v) == 3 else v
            else: self.link(v, s)
        return sock(nd, "Result_Color")
    def geo(self):
        return self.n("ShaderNodeNewGeometry")
    def attr_night(self):
        nd = self.n("ShaderNodeAttribute", attribute_type="VIEW_LAYER", attribute_name="night")
        return sock(nd, "Fac")
    def img(self, image, vec, colorspace=None):
        nd = self.n("ShaderNodeTexImage"); nd.image = image; nd.interpolation = "Linear"
        self.link(vec, nd.inputs["Vector"]); return nd.outputs["Color"]
    def triplanar(self, image, scale, rot=0.0):
        """World-space triplanar projection; returns colour socket."""
        g = self.geo()
        sc = self.n("ShaderNodeVectorMath", operation="SCALE"); self.link(g.outputs["Position"], sc.inputs[0])
        sock(sc, "Scale").default_value = 1.0 / scale
        sep = self.n("ShaderNodeSeparateXYZ"); self.link(sc.outputs[0], sep.inputs[0])
        cols = []
        for a, b in (("Y", "Z"), ("X", "Z"), ("X", "Y")):
            cmb = self.n("ShaderNodeCombineXYZ")
            self.link(sep.outputs[a], cmb.inputs["X"]); self.link(sep.outputs[b], cmb.inputs["Y"])
            cols.append(self.img(image, cmb.outputs[0]))
        # weights = |N|^4 normalised
        nsep = self.n("ShaderNodeSeparateXYZ"); self.link(g.outputs["Normal"], nsep.inputs[0])
        w = []
        for ax in "XYZ":
            a = self.math("ABSOLUTE", nsep.outputs[ax]); w.append(self.math("POWER", a, 4.0))
        tot = self.math("ADD", self.math("ADD", w[0], w[1]), w[2])
        out = None
        for c, wi in zip(cols, w):
            f = self.math("DIVIDE", wi, tot)
            vm = self.n("ShaderNodeVectorMath", operation="SCALE"); self.link(c, vm.inputs[0]); self.link(f, sock(vm, "Scale"))
            out = vm.outputs[0] if out is None else self._vadd(out, vm.outputs[0])
        return out
    def _vadd(self, a, b):
        nd = self.n("ShaderNodeVectorMath", operation="ADD"); self.link(a, nd.inputs[0]); self.link(b, nd.inputs[1]); return nd.outputs[0]
    def planar_xy(self, image, scale):
        g = self.geo()
        sc = self.n("ShaderNodeVectorMath", operation="SCALE"); self.link(g.outputs["Position"], sc.inputs[0])
        sock(sc, "Scale").default_value = 1.0 / scale
        return self.img(image, sc.outputs[0])
    def bsdf(self, **kw):
        nd = self.n("ShaderNodeBsdfPrincipled")
        for k, v in kw.items():
            s = nd.inputs[k]
            if isinstance(v, (int, float)): s.default_value = v
            elif isinstance(v, tuple): s.default_value = (*v, 1) if len(v) == 3 else v
            else: self.link(v, s)
        return nd
    def out(self, shader):
        o = self.n("ShaderNodeOutputMaterial"); self.link(shader, o.inputs["Surface"]); return o

def new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return m

# ================================================================ 1. building materials
def mat_stone():
    m = new_mat("ST_Limestone"); b = NT(m)
    vista = load_img(os.path.join(MAPS, "Vista Bone _ 120x240 cm _ Mat Beige Betonlook XXL Tegel (1).jpeg.jpg"))
    wall = load_img(tex_path("beige_wall_001", "diff"))
    tint = b.rgb((0.70, 0.635, 0.505))               # pale cream limestone (linear), as in the client renders
    col = tint
    if vista:
        t = b.triplanar(vista, 2.4)
        col = b.mix(0.30, tint, b.mix(1.0, tint, t, "MULTIPLY"))  # subtle panel variation
        col = b.mix(1.0, col, (1.55, 1.55, 1.55), "MULTIPLY")
        col = b.mix(0.55, tint, col)
    if wall:
        t2 = b.triplanar(wall, 6.0)
        col = b.mix(0.18, col, b.mix(1.0, col, t2, "OVERLAY"))
    # large-scale tonal variation so 80 m of facade isn't flat
    noise = b.n("ShaderNodeTexNoise"); sock(noise, "Scale").default_value = 0.035; sock(noise, "Detail").default_value = 3
    g = b.geo(); b.link(g.outputs["Position"], noise.inputs["Vector"])
    nv = b.math("MULTIPLY_ADD", noise.outputs["Fac"], 0.22, 0.89)
    hsv = b.n("ShaderNodeHueSaturation"); b.link(col, hsv.inputs["Color"]); b.link(nv, hsv.inputs["Value"])
    col = hsv.outputs["Color"]
    # crevice darkening (Corona AO look of the client renders)
    ao = b.n("ShaderNodeAmbientOcclusion", samples=8, only_local=False); ao.inputs["Distance"].default_value = 0.35
    aof = b.math("MULTIPLY_ADD", ao.outputs["AO"], 0.45, 0.55)
    vm = b.n("ShaderNodeVectorMath", operation="SCALE"); b.link(col, vm.inputs[0]); b.link(aof, sock(vm, "Scale"))
    col = vm.outputs[0]
    bump = None
    if wall:
        bp = b.n("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.12; bp.inputs["Distance"].default_value = 0.004
        b.link(t2, bp.inputs["Height"])
        bump = bp.outputs["Normal"]
    # night: warm wash of facade uplights is done with real spot lights; add tiny warm emission bias
    stone = b.bsdf(**{"Base Color": col, "Roughness": 0.62, "Specular IOR Level": 0.35})
    if bump: b.link(bump, stone.inputs["Normal"])
    # slate for mansard slopes above ROOF_Z
    slate = slate_bsdf(b)
    g2 = b.geo(); sep = b.n("ShaderNodeSeparateXYZ"); b.link(g2.outputs["Position"], sep.inputs[0])
    nsep = b.n("ShaderNodeSeparateXYZ"); b.link(g2.outputs["Normal"], nsep.inputs[0])
    above = b.math("GREATER_THAN", sep.outputs["Z"], ROOF_Z)
    sloped = b.math("MULTIPLY", b.math("GREATER_THAN", nsep.outputs["Z"], 0.18), b.math("LESS_THAN", nsep.outputs["Z"], 0.93))
    roof = b.math("MULTIPLY", above, sloped)
    mx = b.n("ShaderNodeMixShader"); b.link(roof, mx.inputs[0]); b.link(stone.outputs[0], mx.inputs[1]); b.link(slate, mx.inputs[2])
    b.out(mx.outputs[0])
    return m

def slate_bsdf(b):
    img = load_img(tex_path("roof_slates_02", "diff"))
    base = b.rgb((0.030, 0.036, 0.052))      # dark navy slate of the client renders
    col = base
    if img:
        t = b.triplanar(img, 2.5)
        col = b.mix(1.0, base, t, "MULTIPLY"); col = b.mix(1.0, col, (3.2, 3.2, 3.4), "MULTIPLY")
    s = b.bsdf(**{"Base Color": col, "Roughness": 0.38, "Specular IOR Level": 0.5, "Coat Weight": 0.25})
    return s.outputs[0]

def mat_slate():
    m = new_mat("ST_Slate"); b = NT(m); b.out(slate_bsdf(b)); return m

def mat_glass():
    m = new_mat("ST_Glass"); b = NT(m)
    info = b.n("ShaderNodeObjectInfo")
    lit = b.math("GREATER_THAN", info.outputs["Random"], 0.42)                   # ~58 % of rooms lit at night
    warm = b.mix(info.outputs["Random"], (1.0, 0.62, 0.32), (1.0, 0.80, 0.55))
    strength = b.math("MULTIPLY", b.math("MULTIPLY", b.attr_night(), lit), 3.5)
    s = b.bsdf(**{"Base Color": (0.018, 0.024, 0.030), "Metallic": 0.0, "Roughness": 0.03, "IOR": 1.52,
                  "Specular IOR Level": 0.9, "Emission Color": warm, "Emission Strength": strength})
    b.out(s.outputs[0]); return m

def mat_frame():
    m = new_mat("ST_Frame"); b = NT(m)
    s = b.bsdf(**{"Base Color": (0.028, 0.025, 0.022), "Metallic": 0.7, "Roughness": 0.32})
    b.out(s.outputs[0]); return m

def mat_gold():
    m = new_mat("ST_Gold"); b = NT(m)
    s = b.bsdf(**{"Base Color": (1.0, 0.70, 0.36), "Metallic": 1.0, "Roughness": 0.26})
    b.out(s.outputs[0]); return m

def mat_light():
    m = new_mat("ST_Light"); b = NT(m)
    st = b.math("MULTIPLY_ADD", b.attr_night(), 22.0, 4.0)
    e = b.n("ShaderNodeEmission"); e.inputs["Color"].default_value = (1.0, 0.72, 0.42, 1); b.link(st, e.inputs["Strength"])
    b.out(e.outputs[0]); return m

def mat_simple(name, color, rough=0.5, metal=0.0):
    m = new_mat(name); b = NT(m)
    b.out(b.bsdf(**{"Base Color": color, "Roughness": rough, "Metallic": metal}).outputs[0]); return m

def mat_ground(name, texname, scale, tint=(1, 1, 1), rough=0.8, fallback=(0.3, 0.3, 0.3)):
    m = new_mat(name); b = NT(m)
    img = load_img(tex_path(texname, "diff"))
    col = b.rgb(fallback)
    if img:
        col = b.mix(1.0, b.planar_xy(img, scale), tint, "MULTIPLY")
    s = b.bsdf(**{"Base Color": col, "Roughness": rough})
    nimg = load_img(tex_path(texname, "nor_gl"), "Non-Color")
    if nimg:
        nm = b.n("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
        b.link(b.planar_xy(nimg, scale), nm.inputs["Color"]); b.link(nm.outputs[0], s.inputs["Normal"])
    b.out(s.outputs[0]); return m

M = {
    "stone": mat_stone(), "slate": mat_slate(), "glass": mat_glass(), "frame": mat_frame(),
    "gold": mat_gold(), "light": mat_light(),
    "white": mat_simple("ST_White", (0.80, 0.78, 0.74), 0.4),
    "black": mat_simple("ST_Black", (0.012, 0.012, 0.012), 0.3),
    "darkmarble": mat_simple("ST_NeroMarble", (0.02, 0.02, 0.022), 0.12),
    "grass": None,
    "asphalt": mat_ground("ST_Asphalt", "asphalt_02", 6.0, (0.75, 0.75, 0.78), 0.85, (0.06, 0.06, 0.06)),
    "paving": mat_ground("ST_Paving", "herringbone_pavement_03", 2.5, (1.0, 0.95, 0.88), 0.75, (0.35, 0.32, 0.28)),
    "pavement": mat_ground("ST_Sidewalk", "precast_stone_paving", 3.0, (1.0, 1.0, 1.0), 0.8, (0.4, 0.4, 0.38)),
    "marble": mat_ground("ST_Marble", "marble_01", 2.0, (1, 1, 1), 0.2, (0.8, 0.8, 0.78)),
}

def mat_lawn():
    """Lush irrigated lawn: green with large-scale tonal patches, fine texture detail and a few drier spots."""
    m = new_mat("ST_Grass"); b = NT(m)
    g = b.geo()
    big = b.n("ShaderNodeTexNoise"); sock(big, "Scale").default_value = 0.02; sock(big, "Detail").default_value = 4
    b.link(g.outputs["Position"], big.inputs["Vector"])
    mid = b.n("ShaderNodeTexNoise"); sock(mid, "Scale").default_value = 0.35; sock(mid, "Detail").default_value = 6
    b.link(g.outputs["Position"], mid.inputs["Vector"])
    col = b.mix(big.outputs["Fac"], (0.045, 0.095, 0.020), (0.090, 0.150, 0.035))
    col = b.mix(b.math("MULTIPLY", mid.outputs["Fac"], 0.5), col, (0.11, 0.17, 0.05))
    dry = b.math("GREATER_THAN", big.outputs["Fac"], 0.68)
    col = b.mix(b.math("MULTIPLY", dry, 0.35), col, (0.20, 0.19, 0.09))
    img = load_img(tex_path("grass_ground", "diff"))
    if img:
        t = b.planar_xy(img, 2.0)
        hsv = b.n("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 0.0; b.link(t, hsv.inputs["Color"])
        col = b.mix(1.0, col, b.mix(1.0, hsv.outputs["Color"], (2.2, 2.2, 2.2), "MULTIPLY"), "MULTIPLY")
    s = b.bsdf(**{"Base Color": col, "Roughness": 0.95, "Specular IOR Level": 0.25})
    bp = b.n("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.4; b.link(mid.outputs["Fac"], bp.inputs["Height"])
    b.link(bp.outputs["Normal"], s.inputs["Normal"])
    b.out(s.outputs[0]); return m
M["grass"] = mat_lawn()

RULES = [  # (regex on base material name, key)
    (r"^Roofing_Shingles|^Tiles Roof", "slate"),
    (r"^Material #59(213456|213711)?$|^Material #96$|^Material #-2147483648", "glass"),
    (r"^Material #58(213444|213699)?$|^Material #108$|^Material #-2147483643$", "frame"),
    (r"^Stahl|^Material #2147483643$|^Material #2147483645$", "gold"),
    (r"^Material #2147483604$|^Material #-2147483641$|^Material #2147483636$", "light"),
    (r"^Material #2147437225$", "white"),
    (r"^Fasion Brands_black", "black"),
    (r"^Material #-2147483618$", "darkmarble"),
    (r"^Grass_B|^Material #2147483647$", "grass"),
    (r"^Asphalt", "asphalt"),
    (r"^Cobblestone", "paving"),
    (r"^Tiles White Marble", "marble"),
    (r"^Material #57$|^Material #21474836(31|33|34|35|46)$|^Material #-2147483645$|^Material #2147483577$|^01 - CoronaPhysicalMtl$", "stone"),
]
def classify(name):
    base = re.sub(r"\.\d{3}$", "", name)
    for rx, k in RULES:
        if re.search(rx, base):
            return k
    return None

swapped = {}
for me in bpy.data.meshes:
    for i, mt in enumerate(me.materials):
        if mt is None or mt.name.startswith("ST_"):
            continue
        k = classify(mt.name)
        if k:
            me.materials[i] = M[k]; swapped[k] = swapped.get(k, 0) + 1
for o in bpy.data.objects:            # object-linked slots too
    for s in o.material_slots:
        if s.link == "OBJECT" and s.material and not s.material.name.startswith("ST_"):
            k = classify(s.material.name)
            if k: s.material = M[k]
log(f"Building materials swapped: {swapped}")
building_objs = [o for o in bpy.data.objects if o.type == "MESH"]

# ================================================================ 2. ground, roads, context
site = bpy.data.collections.new("site"); scene.collection.children.link(site)

def box(name, x0, x1, y0, y1, z0, z1, mat, col=site):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0); v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0); v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    bm.to_mesh(me); bm.free(); me.materials.append(mat)
    o = bpy.data.objects.new(name, me); col.objects.link(o); return o

def plane(name, x0, x1, y0, y1, z, mat, col=site):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    me.materials.append(mat); o = bpy.data.objects.new(name, me); col.objects.link(o); return o

L = 1500.0
plane("Terrain", CX - L, CX + L, -L, L, -0.06, M["grass"])
# boulevard in front of the plot: sidewalk | 3 lanes | median | 3 lanes | sidewalk
ROAD = {"sw1": (-57.0, -50.0), "r1": (-68.0, -57.0), "med": (-73.0, -68.0), "r2": (-84.0, -73.0), "sw2": (-91.0, -84.0)}
m_line = mat_simple("ST_RoadLine", (0.75, 0.75, 0.72), 0.6)
m_kerb = mat_simple("ST_Kerb", (0.55, 0.53, 0.50), 0.7)
m_yellow = mat_simple("ST_KerbYellow", (0.65, 0.48, 0.05), 0.6)
box("Sidewalk_N", CX - L, CX + L, *ROAD["sw1"], -0.06, 0.15, M["pavement"])
box("Sidewalk_S", CX - L, CX + L, *ROAD["sw2"], -0.06, 0.15, M["pavement"])
plane("Road_N", CX - L, CX + L, *ROAD["r1"], 0.0, M["asphalt"])
plane("Road_S", CX - L, CX + L, *ROAD["r2"], 0.0, M["asphalt"])
box("Median", CX - L, CX + L, ROAD["med"][0] + 0.4, ROAD["med"][1] - 0.4, -0.06, 0.25, M["grass"])
box("Median_kerbN", CX - L, CX + L, ROAD["med"][1] - 0.4, ROAD["med"][1], -0.06, 0.28, m_yellow)
box("Median_kerbS", CX - L, CX + L, ROAD["med"][0], ROAD["med"][0] + 0.4, -0.06, 0.28, m_yellow)
# lane markings (dashed) - one long mesh per lane line
def dashes(name, y, dash=3.0, gap=6.0):
    me = bpy.data.meshes.new(name); vs = []; fs = []
    x = CX - L
    while x < CX + L:
        i = len(vs); vs += [(x, y - 0.08, 0.01), (x + dash, y - 0.08, 0.01), (x + dash, y + 0.08, 0.01), (x, y + 0.08, 0.01)]
        fs.append((i, i + 1, i + 2, i + 3)); x += dash + gap
    me.from_pydata(vs, [], fs); me.materials.append(m_line)
    o = bpy.data.objects.new(name, me); site.objects.link(o)
for k in ("r1", "r2"):
    y0, y1 = ROAD[k]; w = (y1 - y0) / 3
    dashes(f"Lane_{k}_a", y0 + w); dashes(f"Lane_{k}_b", y0 + 2 * w)
    for yy in (y0 + 0.35, y1 - 0.35):   # solid edge lines
        plane(f"Edge_{k}_{yy:.1f}", CX - L, CX + L, yy - 0.07, yy + 0.07, 0.012, m_line)
# plot driveway openings in the kerb are implied; plot itself is already in the model.

# ---- camera positions (defined here so trees, poles and blocks keep their sightlines clear)
CAMS = {  # name: (location, look-at, lens, shift_y, level)
    "CAM_front": ((CX, FRONT_Y - 150, 10.0), (CX, FRONT_Y, 10.0), 32, 0.165, True),
    "CAM_aerial": ((CX + 125, FRONT_Y - 140, 150), (CX - 4, -6, 22), 32, 0.0, False),
    "CAM_corner": ((CX + 110, FRONT_Y - 90, 6.0), (CX - 4, -8, 6.0), 26, 0.24, True),
    "CAM_entrance": ((CX + 14, FRONT_Y - 30, 1.6), (CX, FRONT_Y, 7), 30, 0.0, False),
}
def seg_dist(px, py, a, b):
    ax, ay = a[0], a[1]; bx, by = b[0], b[1]
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2)) if L2 else 0.0
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t
def blocked(x, y, pad=8.0):
    for name, (loc, tgt, *_r) in CAMS.items():
        if loc[2] > 60: continue
        end = (CX, FRONT_Y + 10)
        d, t = seg_dist(x, y, loc, end)
        seg_len = math.hypot(end[0] - loc[0], end[1] - loc[1])
        if d < pad + 0.12 * t * seg_len and t * seg_len < seg_len - 22:   # widening corridor, open near the building
            return True
        if math.hypot(x - loc[0], y - loc[1]) < 14: return True
    return False

# ---- context buildings (simple massing with procedural window grid)
def mat_context():
    m = new_mat("ST_Context"); b = NT(m)
    g = b.geo(); sep = b.n("ShaderNodeSeparateXYZ"); b.link(g.outputs["Position"], sep.inputs[0])
    u = b.math("ADD", sep.outputs["X"], sep.outputs["Y"])
    cmb = b.n("ShaderNodeCombineXYZ"); b.link(u, cmb.inputs["X"]); b.link(sep.outputs["Z"], cmb.inputs["Y"])
    def brick():
        br = b.n("ShaderNodeTexBrick", offset=0.0, squash=1.0)
        b.link(cmb.outputs[0], br.inputs["Vector"])
        br.inputs["Scale"].default_value = 1.0; br.inputs["Mortar Size"].default_value = 0.75
        br.inputs["Brick Width"].default_value = 3.0; br.inputs["Row Height"].default_value = 3.3
        br.inputs["Mortar Smooth"].default_value = 0.0
        return br
    br = brick()
    br.inputs["Color1"].default_value = (0.020, 0.030, 0.040, 1); br.inputs["Color2"].default_value = (0.045, 0.055, 0.065, 1)
    info = b.n("ShaderNodeObjectInfo")
    palette = b.n("ShaderNodeValToRGB"); b.link(info.outputs["Random"], palette.inputs[0])
    els = palette.color_ramp.elements; palette.color_ramp.interpolation = "CONSTANT"
    els[0].position = 0.0; els[0].color = (0.62, 0.55, 0.42, 1)
    els[1].position = 0.30; els[1].color = (0.70, 0.66, 0.58, 1)
    e = els.new(0.55); e.color = (0.68, 0.52, 0.20, 1)   # the yellow blocks in the client aerial
    e = els.new(0.80); e.color = (0.55, 0.52, 0.50, 1)
    sock(br, "Mortar").default_value = (0.5, 0.5, 0.5, 1)
    b.link(palette.outputs["Color"], br.inputs["Mortar"])
    nz = b.n("ShaderNodeSeparateXYZ"); b.link(g.outputs["Normal"], nz.inputs[0])
    is_roof = b.math("GREATER_THAN", b.math("ABSOLUTE", nz.outputs["Z"]), 0.5)
    col = b.mix(is_roof, br.outputs["Color"], (0.42, 0.41, 0.40))
    glassy = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, br.outputs["Fac"]), b.math("SUBTRACT", 1.0, is_roof))
    rough = b.math("MULTIPLY_ADD", glassy, -0.75, 0.85)
    br2 = brick(); br2.inputs["Color1"].default_value = (1, 1, 1, 1); br2.inputs["Color2"].default_value = (0, 0, 0, 1)
    br2.inputs["Bias"].default_value = -0.45
    lit = b.math("MULTIPLY", b.math("GREATER_THAN", sock(br2, "Color"), 0.55), glassy)
    em = b.math("MULTIPLY", b.math("MULTIPLY", lit, b.attr_night()), 0.9)
    camd = b.n("ShaderNodeCameraData")
    hz = b.math("SUBTRACT", 1.0, b.math("EXPONENT", b.math("MULTIPLY", sock(camd, "View Distance"), -1.0 / 650.0)))
    col = b.mix(b.math("MULTIPLY", hz, b.math("SUBTRACT", 1.0, b.attr_night())), col, (0.62, 0.68, 0.76))
    s = b.bsdf(**{"Base Color": col, "Roughness": rough, "Emission Color": (1.0, 0.75, 0.45), "Emission Strength": em})
    b.out(s.outputs[0]); return m
m_ctx = mat_context()
ctx = bpy.data.collections.new("context"); scene.collection.children.link(ctx)
ctx_specs = [  # x0, x1, y0, y1, height  (mid-rise neighbours, kept back from the plot)
    (-300, -255, -40, 0, 18), (-305, -260, 40, 80, 15), (-60, -20, 60, 100, 21),
    (-230, -180, 120, 150, 14), (-130, -90, 150, 190, 24), (-290, -245, 140, 180, 17),
    (-380, -330, -30, 30, 26), (-10, 40, 60, 110, 19), (-330, -280, 200, 250, 18), (-180, -130, 230, 270, 30),
    (-80, -30, -170, -130, 15), (-360, -300, -170, -130, 18), (40, 90, -170, -130, 22), (-460, -400, -150, -110, 14),
    (70, 120, 0, 60, 16), (-470, -420, 0, 70, 22), (-100, -40, 230, 280, 26), (-280, -220, 300, 350, 30),
]
ctx_specs = [c for c in ctx_specs if not any(blocked(x, y, 4) for x in (c[0], c[1], (c[0]+c[1])/2) for y in (c[2], c[3], (c[2]+c[3])/2))]
for i, (x0, x1, y0, y1, h) in enumerate(ctx_specs):
    box(f"Context_{i:02d}", x0, x1, y0, y1, -0.05, h, m_ctx, ctx)
log(f"Ground, boulevard and {len(ctx_specs)} context buildings added")

# ================================================================ 3. vegetation + street lights
assets = bpy.data.collections.new("assets_lib"); scene.collection.children.link(assets)
def import_asset(name):
    p = os.path.join(ASSETS, "models", name, f"{name}_2k.gltf")
    if not os.path.exists(p):
        return None
    before = set(bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=p)
    except Exception as e:
        log(f"  import {name} failed: {e}"); return None
    new = [o for o in bpy.data.objects if o not in before]
    c = bpy.data.collections.new(f"A_{name}"); assets.children.link(c)
    for o in new:
        for uc in list(o.users_collection): uc.objects.unlink(o)
        c.objects.link(o)
    # put origin at ground: shift so min z = 0 at x/y centre
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    for o in new:
        if o.type == "MESH":
            for v in o.bound_box:
                w = o.matrix_world @ Vector(v); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    c.instance_offset = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    c["height"] = mx.z - mn.z
    return c

lib = {}
for n in ("jacaranda_tree", "island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02", "pachira_aquatica_01",
          "shrub_01", "shrub_02", "shrub_03", "shrub_04", "flower_gazania", "flower_empodium", "periwinkle_plant", "grass_medium_02"):
    c = import_asset(n)
    if c: lib[n] = c
for lc in bpy.context.view_layer.layer_collection.children:
    if lc.name == "assets_lib":
        lc.exclude = True
log(f"Imported {len(lib)} plant assets: {', '.join(f'{k} {v.get('height', 0):.1f}m' for k, v in lib.items())}")

veg = bpy.data.collections.new("vegetation"); scene.collection.children.link(veg)
# BlenderKit models (palms, real street trees, shrubs, flowers, cars) - see fetch_blenderkit.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(RENDER_DIR, "scripts"))
try:
    import bk_assets
    BK = bk_assets.load_all(RENDER_DIR, log=log)
except Exception as e:
    BK = {}; log(f"BlenderKit assets not loaded: {e}")
lib.update(BK)
log(f"BlenderKit assets: {len(BK)} ({', '.join(BK)})")

def plant(kind, x, y, height=None, z=0.0, rot=None, check=True):
    c = lib.get(kind)
    if c is None: return None
    if check and z < 1.0 and blocked(x, y): return None
    e = bpy.data.objects.new(f"P_{kind}", None); e.instance_type = "COLLECTION"; e.instance_collection = c
    s = 1.0
    if height and c.get("height", 0) > 0.05:
        s = height / c["height"]
    e.location = (x, y, z); e.scale = (s, s, s); e.rotation_euler = (0, 0, rot if rot is not None else random.uniform(0, 6.283))
    veg.objects.link(e); return e

def in_box(x, y, bx, pad=0.0):
    return bx[0] - pad < x < bx[1] + pad and bx[2] - pad < y < bx[3] + pad

def pick(*names):
    got = [n for n in names if n in lib]
    return random.choice(got) if got else None

PH_TREES = [k for k in ("island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02") if k in lib]
BK_TREES = [k for k in ("maple_a", "maple_b", "eucalyptus", "broadleaf") if k in lib]
PALMS = [k for k in ("palm_dense", "palm_tall", "palm_bent") if k in lib]
STREET = BK_TREES or PH_TREES
PARK = BK_TREES or PH_TREES          # Poly Haven trees are 2-5 M polys each: only a fallback
n_tree = n_small = 0
MED_Y = sum(ROAD["med"]) / 2
# median: a row of palms with flowering shrubs between them (as in the client's renders)
x = CX - 420.0
while x < CX + 420.0:
    if PALMS and abs(x - CX) > 9:
        if plant(random.choice(PALMS), x + random.uniform(-0.8, 0.8), MED_Y + random.uniform(-0.4, 0.4), random.uniform(10.5, 14.5)): n_tree += 1
    for k in range(3):
        xx = x + 3.0 + k * 2.6
        f = pick("abelia_small", "geranium", "hydrangea_red") if random.random() < 0.8 else None
        if f and plant(f, xx, MED_Y + random.uniform(-1.0, 1.0), {"abelia_small": 0.9, "geranium": 0.35, "hydrangea_red": 0.8}.get(f, 0.8), z=0.25, check=False): n_small += 1
    x += random.uniform(10.0, 12.5)
# sidewalk street trees (gap in front of the entrance keeps the facade visible from the front camera)
x = CX - 420.0
while x < CX + 420.0:
    for y, ok in ((ROAD["sw1"][0] + 2.2, abs(x - CX) > 36), (ROAD["sw2"][1] - 2.2, abs(x - CX) > 16)):
        if ok and STREET and plant(random.choice(STREET), x + random.uniform(-1.5, 1.5), y, random.uniform(9.0, 13.0)): n_tree += 1
    x += random.uniform(12.0, 16.0)
# parkland: dense, varied canopy all around (not on roads, plot, context buildings, or camera sightlines)
ctx_boxes = [(x0, x1, y0, y1) for (x0, x1, y0, y1, h) in ctx_specs]
for i in range(2200):
    r = random.uniform(30, 700); a = random.uniform(0, 6.283)
    x, y = CX + r * math.cos(a), -10 + r * math.sin(a)
    if ROAD["sw2"][0] - 3 < y < ROAD["sw1"][1] + 3: continue
    if in_box(x, y, PLOT, 5): continue
    if any(in_box(x, y, b, 5) for b in ctx_boxes): continue
    if y < -95 and abs(x - CX) < 70 and y > -200: continue      # front-camera foreground stays open lawn
    kind = random.choice(PARK + (["jacaranda_tree"] if "jacaranda_tree" in lib and random.random() < 0.12 else []))
    if kind and plant(kind, x, y, random.uniform(10.0, 19.0)): n_tree += 1
# plot: palms + jacarandas at the front corners, cypress topiaries flanking the entrance,
# hedges along the plot edges, flower beds along the front plaza
for (x, y) in ((PLOT[0] + 3.5, PLOT[2] + 3.0), (PLOT[1] - 3.5, PLOT[2] + 3.0), (PLOT[0] + 9.0, PLOT[2] + 4.0), (PLOT[1] - 9.0, PLOT[2] + 4.0)):
    if plant(pick(*PALMS) if PALMS else "jacaranda_tree", x, y, random.uniform(11, 14), check=False): n_tree += 1
for (x, y) in ((PLOT[0] + 4, -36), (PLOT[1] - 4, -36)):
    if plant(pick("jacaranda_tree", *BK_TREES), x, y, random.uniform(9, 11), check=False): n_tree += 1
for dx in (-12.5, -7.5, 7.5, 12.5):
    if plant("cypress_spiral", CX + dx, FRONT_Y - 2.2, 2.9, check=False): n_small += 1
SHRUBS = [k for k in ("abelia", "abelia_small") if k in lib] or [k for k in ("shrub_01", "shrub_02", "shrub_03", "shrub_04") if k in lib]
FLOWERS = [k for k in ("hydrangea_red", "roses_yellow", "geranium") if k in lib] or [k for k in ("flower_gazania", "flower_empodium", "periwinkle_plant") if k in lib]
x = PLOT[0] + 1.0
while x < PLOT[1] - 1.0:
    if not (CX - 15 < x < CX + 15) and SHRUBS:     # leave the entrance / driveway open
        if plant(random.choice(SHRUBS), x, PLOT[2] + 1.0, random.uniform(1.0, 1.3), check=False): n_small += 1
        if FLOWERS and plant(random.choice(FLOWERS), x + random.uniform(-0.4, 0.4), PLOT[2] + 2.3, random.uniform(0.5, 0.9), check=False): n_small += 1
    x += 1.5
for y in [PLOT[2] + 4 + i * 1.6 for i in range(int((PLOT[3] - PLOT[2] - 8) / 1.6))]:
    for xx in (PLOT[0] + 0.9, PLOT[1] - 0.9):
        if SHRUBS and plant(random.choice(SHRUBS), xx, y, random.uniform(1.2, 1.6), check=False): n_small += 1
# flower beds along the podium front (between the arcade and the plaza)
for x in [BX[0] + 2 + i * 1.4 for i in range(int((BX[1] - BX[0] - 4) / 1.4))]:
    if abs(x - CX) > 15 and FLOWERS and plant(random.choice(FLOWERS), x, FRONT_Y - 1.0, random.uniform(0.5, 0.8), check=False): n_small += 1
# podium-roof garden: planters along the front parapet between the pavilions
for x in [CX - 9 + i * 1.5 for i in range(13)]:
    if SHRUBS and plant(random.choice(SHRUBS), x, FRONT_Y + 2.5, 0.9, z=24.8, check=False): n_small += 1

# ---- traffic: cars in all six lanes, a bus, and cars at the drop-off
traffic = bpy.data.collections.new("traffic"); scene.collection.children.link(traffic)
CARS = [k for k, c in lib.items() if c.get("kind") == "car"]
PAINT = [(0.80, 0.80, 0.78), (0.02, 0.02, 0.022), (0.55, 0.56, 0.57), (0.82, 0.82, 0.80), (0.30, 0.31, 0.32),
         (0.62, 0.60, 0.55), (0.04, 0.06, 0.12), (0.75, 0.75, 0.74), (0.18, 0.02, 0.03)]
import colorsys
for i, slug in enumerate(CARS):        # Lahore palette: mostly white / silver / black / grey
    col = PAINT[i % len(PAINT)]
    for o in lib[slug].all_objects:
        for sl in getattr(o, "material_slots", []):
            m = sl.material
            if not m or not m.node_tree or re.search(r"light|lamp|glass|brake|indicat|signal|led|emiss|tail|caliper|logo|plate", m.name, re.I):
                continue
            for nd in m.node_tree.nodes:
                if nd.type == "BSDF_PRINCIPLED" and not nd.inputs["Base Color"].is_linked:
                    r, g, bl, _a = nd.inputs["Base Color"].default_value
                    h, sat, v = colorsys.rgb_to_hsv(r, g, bl)
                    named = re.search(r"paint|body|carpaint|maincolor|color", m.name, re.I)
                    if (sat > 0.25 and v > 0.04) or named:
                        nd.inputs["Base Color"].default_value = (*col, 1)
def car(slug, x, y, heading):
    c = lib[slug]
    e = bpy.data.objects.new(f"V_{slug}", None); e.instance_type = "COLLECTION"; e.instance_collection = c
    s = c.get("scale", 1.0); e.scale = (s, s, s)
    e.location = (x, y, 0.0); e.rotation_euler = (0, 0, c.get("yaw", 0.0) + heading)
    traffic.objects.link(e); return e
n_car = 0
if CARS:
    for road, heading in (("r1", 0.0), ("r2", math.pi)):
        y0, y1 = ROAD[road]; w = (y1 - y0) / 3
        for lane in range(3):
            y = y0 + w * (lane + 0.5)
            x = CX - 380 + random.uniform(0, 20)
            while x < CX + 380:
                near = abs(x - CX) < 120
                if random.random() < (0.85 if near else 0.6):
                    loc_ok = all(math.hypot(x - L[0][0], y - L[0][1]) > 18 for L in CAMS.values())
                    if loc_ok:
                        car(random.choice(CARS), x, y + random.uniform(-0.25, 0.25), heading + random.uniform(-0.015, 0.015)); n_car += 1
                x += random.uniform(9.0, 16.0) if near else random.uniform(14.0, 40.0)
    if "bus" in lib:
        car("bus", CX - 70, ROAD["r2"][0] + (ROAD["r2"][1] - ROAD["r2"][0]) * 0.17, math.pi); n_car += 1
    # drop-off: a few cars parked along the front plaza, clear of the entrance
    for dx in (-30, -24, 22, 28):
        car(random.choice(CARS), CX + dx, PLOT[2] + 6.5, math.pi / 2 + random.uniform(-0.05, 0.05)); n_car += 1
log(f"Traffic: {n_car} vehicles from {len(CARS)} car models")
log(f"Vegetation: {n_tree} trees, {n_small} shrubs/flowers (instanced)")

# ---- street lights
m_pole = mat_simple("ST_Pole", (0.05, 0.05, 0.055), 0.4, 0.6)
m_lamp = new_mat("ST_LampHead"); b = NT(m_lamp)
e = b.n("ShaderNodeEmission"); e.inputs["Color"].default_value = (1.0, 0.78, 0.5, 1)
b.link(b.math("MULTIPLY_ADD", b.attr_night(), 60.0, 0.2), e.inputs["Strength"]); b.out(e.outputs[0])
def make_pole():
    me = bpy.data.meshes.new("StreetLight"); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.14, radius2=0.08, depth=9.0, matrix=Matrix.Translation((0, 0, 4.5)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 1.2, 9.0)) @ Matrix.Diagonal((0.08, 2.4, 0.08, 1)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 2.3, 8.92)) @ Matrix.Diagonal((0.35, 0.9, 0.12, 1)))
    bm.to_mesh(me); bm.free()
    me.materials.append(m_pole); me.materials.append(m_lamp)
    for p in me.polygons:   # lamp head underside emits
        c = p.center
        p.material_index = 1 if (c.y > 1.9 and c.z < 8.9) else 0
    return me
pole_me = make_pole()
lights_col = bpy.data.collections.new("street_lights"); scene.collection.children.link(lights_col)
x = CX - 400.0; n_pole = 0
while x < CX + 400.0:
    for y, rz in ((ROAD["sw1"][0] + 0.6, math.pi), (ROAD["sw2"][1] - 0.6, 0.0)):
        if blocked(x, y, 3.0): continue
        o = bpy.data.objects.new("StreetLight", pole_me); o.location = (x, y, 0.15); o.rotation_euler = (0, 0, rz)
        lights_col.objects.link(o); n_pole += 1
    x += 32.0
log(f"Street lights: {n_pole}")

# ================================================================ 4. night facade lighting (spots, energy set per mode)
night_lights = []
def spot(name, loc, rot, energy, size_deg, color=(1.0, 0.78, 0.52), radius=0.1):
    ld = bpy.data.lights.new(name, "SPOT"); ld.energy = energy; ld.spot_size = math.radians(size_deg); ld.spot_blend = 0.6
    ld.color = color; ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld); o.location = loc; o.rotation_euler = rot
    scene.collection.objects.link(o); night_lights.append((o, energy)); return o
dg = bpy.context.evaluated_depsgraph_get()
def facade_y(x, z, y_from=-120.0):
    hit, loc, n, i, ob, mt = scene.ray_cast(dg, Vector((x, y_from, z)), Vector((0, 1, 0)), distance=200)
    return loc.y if hit else None
# podium: uplights at the base of the front pilasters
x = BX[0] + 1.0
while x <= BX[1] - 1.0:
    fy = facade_y(x, 3.0)
    if fy is not None:
        spot("Up_podium", (x, fy - 0.9, 0.3), (math.radians(-8), 0, 0), 900, 28)
    x += 3.0
# towers: uplights on the podium roof washing the tower faces
for x in [BX[0] + 1.5 + i * 2.6 for i in range(int((BX[1] - BX[0] - 3) / 2.6) + 1)]:
    fy = facade_y(x, 45.0)
    if fy is not None and fy > FRONT_Y + 2:
        spot("Up_tower", (x, fy - 1.2, 25.0), (math.radians(-4), 0, 0), 2600, 16)
# crowns: floodlights from the tower roofs' lower cornice
for x in (BX[0] + 8.5, BX[1] - 8.5, CX):
    fy = facade_y(x, 70.0)
    if fy is not None:
        spot("Up_crown", (x, fy - 6.0, 62.0), (math.radians(-18), 0, 0), 9000, 30)
log(f"Facade lights: {len(night_lights)}")

# ================================================================ 5. world + modes
def find_hdr(name):
    p = os.path.join(ASSETS, "hdri", f"{name}_8k.hdr")
    return p if os.path.exists(p) else None
world = bpy.data.worlds.get("Sky") or bpy.data.worlds.new("Sky"); scene.world = world
world.use_nodes = True; wn = world.node_tree; wn.nodes.clear()
tc = wn.nodes.new("ShaderNodeTexCoord"); mp = wn.nodes.new("ShaderNodeMapping"); env = wn.nodes.new("ShaderNodeTexEnvironment")
bg = wn.nodes.new("ShaderNodeBackground"); wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); wn.links.new(mp.outputs[0], env.inputs["Vector"])
wn.links.new(env.outputs[0], bg.inputs[0]); wn.links.new(bg.outputs[0], wo.inputs["Surface"])
mp.name = "SkyRot"; env.name = "SkyImg"; bg.name = "SkyBg"

def sun_azimuth(img):
    """Find the sun in an equirect HDRI: returns (azimuth rad in image u, elevation rad)."""
    try:
        sm = img.copy(); sm.scale(256, 128)
        px = list(sm.pixels); bpy.data.images.remove(sm)
        best, bi = -1, 0
        for i in range(0, len(px), 4):
            v = px[i] + px[i + 1] + px[i + 2]
            if v > best: best, bi = v, i // 4
        u = (bi % 256 + 0.5) / 256; vv = (bi // 256 + 0.5) / 128
        return (u - 0.5) * 2 * math.pi, (vv - 0.5) * math.pi
    except Exception:
        return 0.0, 0.6

MODES = {   # hdri, strength, wanted sun azimuth (deg, 0 = from the front/south, + = from the east), night, exposure
    "day":   ("kloofendal_48d_partly_cloudy_puresky", 1.0, 35.0, 0.0, 0.25),
    "dusk":  ("belfast_sunset_puresky", 1.0, 60.0, 0.55, 0.3),
    "night": ("qwantani_night_puresky", 0.12, 30.0, 1.0, 0.3),
}
_cache = {}
def apply_mode(mode):
    name, strength, want_az, night, expo = MODES[mode]
    p = find_hdr(name) or find_hdr("kloppenheim_05_puresky")
    if p:
        img = bpy.data.images.load(p, check_existing=True); env.image = img
        if p not in _cache: _cache[p] = sun_azimuth(img)
        u_az, el = _cache[p]
        # Blender equirect: direction azimuth = atan2(y, x); image u -> angle. Rotate so the sun sits at want_az
        # where az 0 means the sun is due south (-y) of the building, i.e. lighting the front facade.
        mp.inputs["Rotation"].default_value[2] = -math.pi / 2 - u_az - math.radians(want_az)
    bg.inputs["Strength"].default_value = strength
    scene["night"] = night
    for o, en in night_lights:
        o.data.energy = en * (night ** 1.5)
        o.hide_render = night < 0.05
    scene.view_settings.exposure = expo
    log(f"Mode {mode}: {os.path.basename(p) if p else 'no hdri'}")

# ================================================================ 6. render settings + cameras
scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for d in prefs.devices: d.use = d.type != "CPU"
    scene.cycles.device = "GPU"
except Exception as e:
    log(f"GPU setup: {e}")
scene.cycles.samples = 16 if QUICK else 384
scene.cycles.adaptive_threshold = 0.02 if QUICK else 0.008
scene.cycles.use_denoising = True
try: scene.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception: pass
scene.cycles.max_bounces = 8; scene.cycles.glossy_bounces = 4; scene.cycles.transparent_max_bounces = 16
scene.cycles.sample_clamp_indirect = 8.0; scene.cycles.caustics_reflective = False; scene.cycles.caustics_refractive = False
scene.render.resolution_x, scene.render.resolution_y = (640, 360) if QUICK else (1920, 1080)
scene.render.resolution_percentage = 100
scene.render.use_simplify = True
scene.render.simplify_subdivision_render = 0
for m in bpy.data.materials:
    try: m.displacement_method = "BUMP"
    except Exception: pass
try:
    scene.cycles.texture_limit_render = "OFF"     # sky + building stay sharp; asset maps are shrunk at load time
except Exception:
    pass
scene.render.image_settings.file_format = "JPEG"; scene.render.image_settings.quality = 92
scene.view_settings.view_transform = "AgX"
for look in ("AgX - Medium High Contrast", "AgX - Punchy", "Medium High Contrast"):
    try:
        scene.view_settings.look = look; break
    except Exception:
        pass

cams = {}
def camera(name, loc, target, lens, shift_y=0.0, level=True):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 5000; cd.clip_start = 0.5; cd.shift_y = shift_y
    o = bpy.data.objects.new(name, cd); scene.collection.objects.link(o)
    o.location = loc; d = Vector(target) - Vector(loc)
    if level:   # architectural camera: horizontal, verticals stay vertical, framing by lens shift
        yaw = math.atan2(d.y, d.x) - math.pi / 2
        o.rotation_euler = (math.radians(90), 0, yaw)
    else:
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cams[name] = o; return o
# front (client's Front Cam), aerial (client's Ariel View), 3/4 from the south-east, entrance close-up
for name, (loc, tgt, lens, sh, level) in CAMS.items():
    camera(name, loc, tgt, lens, sh, level)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCENE_DIR, "sky-tree-v3.blend"), compress=False)
log("Saved scene/sky-tree-v3.blend")

# ================================================================ 7. renders
SHOTS = [("CAM_front", "day"), ("CAM_aerial", "day"), ("CAM_corner", "day"), ("CAM_entrance", "day"),
         ("CAM_front", "dusk"), ("CAM_front", "night"), ("CAM_corner", "night")]
if not NO_RENDER:
    for cam, mode in SHOTS:
        key = f"{cam[4:]}_{mode}"
        if ONLY and key not in ONLY: continue
        apply_mode(mode); scene.camera = cams[cam]
        scene.render.filepath = os.path.join(SCENE_DIR, f"v3_{key}.jpg")
        t = time.time(); bpy.ops.render.render(write_still=True)
        log(f"Render v3_{key}: {time.time() - t:.0f}s")
apply_mode("day"); scene.camera = cams["CAM_front"]
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCENE_DIR, "sky-tree-v3.blend"), compress=False)
log("Done")
LOG.close()
