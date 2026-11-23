# Split the phone-tier splat (m.ply) into per-floor pieces for the Live 3D explode.
# usage: python make_floors.py m.ply levels.json outdir   (then splat-transform each .ply -> .spz)
import sys, json, os, numpy as np
from plyfile import PlyData, PlyElement
from matplotlib.path import Path
POD = [[-23.8,-26.4],[23.8,-26.4],[23.8,26.4],[-23.8,26.4]]
U   = [[-23.6,-17.8],[-7.8,-17.8],[-7.8,5.6],[7.8,5.6],[7.8,-17.8],[23.6,-17.8],[23.6,27.0],[-23.6,27.0]]
UPH = [[-24.8,-18.6],[-7.4,-18.6],[-7.4,5.6],[7.4,5.6],[7.4,-18.6],[24.8,-18.6],[24.8,27.0],[-24.8,27.0]]
src, levels, out = sys.argv[1], sys.argv[2], sys.argv[3]
L = json.load(open(levels))['levels']; v = PlyData.read(src)['vertex'].data.copy()
x, y, z = v['x'], v['y'], v['z']; pts = np.stack([x, y], 1)
inPod, inU, inUP = Path(POD).contains_points(pts), Path(U).contains_points(pts), Path(UPH).contains_points(pts)
lab = np.full(len(v), -1)
for l in L:
    i, zb, zt = l['index'], l['zBottom'], (200 if l['name'] == 'PH' else l['zTop'])
    poly = inPod if i <= 2 else (inUP if l['name'] == 'PH' else inU)
    m = (z >= (0.15 if i == 0 else zb)) & (z < zt) & poly
    lab[m & (lab < 0)] = i
lab[(lab < 0) & inPod & (z >= 24.0) & (z < 40)] = 2      # podium-roof garden rides with level 2
# keep each floor's splats inside its slab: shrink splats whose vertical reach crosses into the gap
w, qx, qy, qz = (v['rot_0'], v['rot_1'], v['rot_2'], v['rot_3']); n = np.sqrt(w*w + qx*qx + qy*qy + qz*qz) + 1e-12
w, qx, qy, qz = w/n, qx/n, qy/n, qz/n
r20, r21, r22 = 2*(qx*qz - w*qy), 2*(qy*qz + w*qx), 1 - 2*(qx*qx + qy*qy)       # third row of R (z component of each axis)
s0, s1, s2 = np.exp(v['scale_0']), np.exp(v['scale_1']), np.exp(v['scale_2'])
ext = 2.5 * np.sqrt((r20*s0)**2 + (r21*s1)**2 + (r22*s2)**2)                     # half vertical reach (~2.5 sigma)
for l in L:
    i = l['index']; zb, zt = l['zBottom'], l['zTop']; m = lab == i
    if not m.any(): continue
    zz = z[m]
    if i == 0:   d = zt - zz                                  # ground floor: only its top face opens up
    elif i == 14: d = zz - zb                                 # penthouse: only its underside
    else:        d = np.minimum(zz - zb, zt - zz)
    room = d.clip(0.0, None) + 0.9                             # allow ~0.9 m of overhang past the slab face
    f = np.minimum(1.0, room / ext[m]); f[ext[m] < 1.2] = 1.0  # small splats are never touched
    for k in ('scale_0', 'scale_1', 'scale_2'): v[k][np.where(m)[0]] += np.log(f)
os.makedirs(out, exist_ok=True)
for i in range(-1, len(L)):
    PlyData([PlyElement.describe(v[lab == i], 'vertex')]).write(os.path.join(out, 'base.ply' if i < 0 else f'f{i:02d}.ply'))
print('ok', np.bincount(lab + 1))
