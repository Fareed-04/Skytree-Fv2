# usage: python tiers.py full.ply clean_full.ply out_m.ply N_m out_p.ply N_p
# Cleans a trained splat (drops below-ground murk, far floaters) and makes lighter tiers that keep a fixed share
# of the budget for the ground so the site around the tower stays sharp, not only the tower.
import sys, numpy as np
from plyfile import PlyData, PlyElement
src, clean_out, out_m, n_m, out_p, n_p = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], int(sys.argv[6])
v = PlyData.read(src)['vertex'].data
x, y, z = v['x'], v['y'], v['z']; r = np.hypot(x, y)
op = 1 / (1 + np.exp(-v['opacity']))
s = np.sort(np.exp(np.stack([v['scale_0'], v['scale_1'], v['scale_2']], 1)), 1)
ok = (z > -1.0) & (r < 168) & (op > 0.01) & (z < 120)
ok &= ~((s[:, 2] > 12) & (op < 0.35))                     # big translucent fog splats
print('clean: kept', ok.sum(), 'of', len(v))
def write(path, idx, names, grow=0.0):
    d = np.empty(len(idx), dtype=[(n, 'f4') for n in names])
    for n in names: d[n] = v[n][idx]
    if grow:
        for k in ('scale_0', 'scale_1', 'scale_2'): d[k] += grow
    PlyData([PlyElement.describe(d, 'vertex')]).write(path); print(path, len(idx))
write(clean_out, np.where(ok)[0], list(v.dtype.names))
dc = [n for n in v.dtype.names if not n.startswith('f_rest')]
imp = op * np.sqrt(s[:, 2] * s[:, 1]) * ok
ground = ok & (z < 3.0)
for out, N, gshare in ((out_m, n_m, 0.22), (out_p, n_p, 0.25)):
    ng = min(int(N * gshare), ground.sum())
    gi = np.where(ground)[0]; gi = gi[np.argsort(-imp[gi])[:ng]]
    rest = imp.copy(); rest[gi] = 0; rest[ground & ~np.isin(np.arange(len(v)), gi)] *= 0.5
    oi = np.argsort(-rest)[:N - ng]
    idx = np.unique(np.concatenate([gi, oi]))
    total = ok.sum(); grow = np.log(min(1.3, (total / N) ** 0.10)) if N < total * 0.5 else 0.0
    write(out, idx, dc, grow)
