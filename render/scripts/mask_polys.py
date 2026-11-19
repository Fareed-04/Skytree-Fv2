"""Turn level-ID masks (red = (level+1)*16) into smooth vector outlines per frame.
usage: python mask_polys.py <mask_dir> <out_json>
Writes {"frame_name": {level: [[x,y,x,y,...], ...]}} with coordinates normalised to 0..10000."""
import sys, os, json, cv2, numpy as np
src, out = sys.argv[1], sys.argv[2]
K = 4                                            # supersample before smoothing so edges come out clean
res = {}
for fn in sorted(os.listdir(src)):
    if not fn.endswith(".png"): continue
    r = cv2.imread(os.path.join(src, fn), cv2.IMREAD_COLOR)[..., 2].astype(np.int32)
    h, w = r.shape; lv = np.rint(r / 16.0).astype(np.int32) - 1
    frame = {}
    for L in np.unique(lv):
        if L < 0: continue
        m = (lv == L).astype(np.uint8) * 255
        if cv2.countNonZero(m) < 12: continue
        m = cv2.resize(m, (w * K, h * K), interpolation=cv2.INTER_NEAREST)
        m = cv2.GaussianBlur(m, (0, 0), K * 0.9); _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        polys = []
        for c in cs:
            if cv2.contourArea(c) < 40 * K * K: continue
            a = cv2.approxPolyDP(c, K * 0.6, True).reshape(-1, 2)
            polys.append([int(round(v)) for p in a for v in (p[0] * 10000 / (w * K), p[1] * 10000 / (h * K))])
        if polys: frame[int(L)] = polys
    res[fn[:-4]] = frame
json.dump(res, open(out, "w"), separators=(",", ":"))
print(out, len(res), "frames", os.path.getsize(out) // 1024, "KB")
