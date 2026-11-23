# Split the phone-tier splat (skytree_m.spz converted to m.ply) into per-floor pieces for the Live 3D explode.
# usage: python make_floors.py m.ply levels.json outdir      then convert each .ply to .spz with splat-transform
import sys, json, os, numpy as np
from plyfile import PlyData, PlyElement
from matplotlib.path import Path
POD = [[-23.8,-26.4],[23.8,-26.4],[23.8,26.4],[-23.8,26.4]]
U   = [[-23.6,-17.8],[-7.8,-17.8],[-7.8,5.6],[7.8,5.6],[7.8,-17.8],[23.6,-17.8],[23.6,27.0],[-23.6,27.0]]
UPH = [[-24.8,-18.6],[-7.4,-18.6],[-7.4,5.6],[7.4,5.6],[7.4,-18.6],[24.8,-18.6],[24.8,27.0],[-24.8,27.0]]
src, levels, out = sys.argv[1], sys.argv[2], sys.argv[3]
L = json.load(open(levels))['levels']; v = PlyData.read(src)['vertex'].data
x, y, z = v['x'], v['y'], v['z']; pts = np.stack([x, y], 1)
inPod, inU, inUP = Path(POD).contains_points(pts), Path(U).contains_points(pts), Path(UPH).contains_points(pts)
lab = np.full(len(v), -1)
for l in L:
    i, zb, zt = l['index'], l['zBottom'], (200 if l['name'] == 'PH' else l['zTop'])
    poly = inPod if i <= 2 else (inUP if l['name'] == 'PH' else inU)
    m = (z >= (0.15 if i == 0 else zb)) & (z < zt) & poly
    lab[m & (lab < 0)] = i
lab[(lab < 0) & inPod & (z >= 24.0) & (z < 40)] = 2      # podium-roof garden rides with level 2
os.makedirs(out, exist_ok=True)
for i in range(-1, len(L)):
    PlyData([PlyElement.describe(v[lab == i], 'vertex')]).write(os.path.join(out, 'base.ply' if i < 0 else f'f{i:02d}.ply'))
print('ok')
