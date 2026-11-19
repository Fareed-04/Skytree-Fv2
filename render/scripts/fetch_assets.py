"""
Downloads the free (CC0) Poly Haven assets listed in render/assets.json into render/assets/.

  Windows:  double-click render\\1-download-assets.bat
  Any:      python fetch_assets.py [--assets ../assets.json] [--out ../assets] [--max-res 8k] [--only hdris,textures,models]

Uses only the Python standard library, so it runs in Blender's bundled Python too.
Resumable: files already downloaded with the right size are skipped.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.polyhaven.com"
UA = {"User-Agent": "PanoraRenderKit/1.0"}
RES_ORDER = ["16k", "8k", "4k", "2k", "1k"]

ap = argparse.ArgumentParser()
ap.add_argument("--assets", default=os.path.join(HERE, "..", "assets.json"))
ap.add_argument("--out", default=os.path.join(HERE, "..", "assets"))
ap.add_argument("--max-res", default=None, help="cap every resolution, e.g. 1k for a quick test")
ap.add_argument("--only", default="hdris,textures,models")
try:
    import bpy  # noqa: F401  (running inside Blender: only parse what follows "--")
    _argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
except ImportError:
    _argv = sys.argv[1:]
args = ap.parse_args(_argv)

cfg = json.load(open(args.assets, encoding="utf-8"))
OUT = os.path.abspath(args.out)
log_path = os.path.join(OUT, "download-log.txt")
os.makedirs(OUT, exist_ok=True)


def log(msg):
    print(msg, flush=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def get_json(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)


def download(url, path, size=None):
    if os.path.exists(path) and (size is None or os.path.getsize(path) == size):
        return "skip"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp, path)
            return "ok"
        except Exception as e:
            if attempt == 3:
                log(f"  FAILED {url}: {e}")
                return "fail"
            time.sleep(2 + attempt * 3)


def pick_res(available, wanted):
    cap = args.max_res or wanted
    order = RES_ORDER[RES_ORDER.index(cap):] if cap in RES_ORDER else RES_ORDER
    for r in order:
        if r in available:
            return r
    return sorted(available, key=lambda r: RES_ORDER.index(r) if r in RES_ORDER else 99)[0]


def fetch_hdri(name, res):
    files = get_json(f"{API}/files/{name}")["hdri"]
    r = pick_res(files.keys(), res)
    f = files[r].get("hdr") or files[r].get("exr")
    ext = "hdr" if "hdr" in files[r] else "exr"
    return [(f["url"], os.path.join(OUT, "hdri", f"{name}_{r}.{ext}"), f.get("size"))]


def fetch_texture(name, res):
    files = get_json(f"{API}/files/{name}")
    out = []
    want = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "Displacement": "disp", "AO": "ao", "arm": "arm"}
    for key, short in want.items():
        if key not in files:
            continue
        r = pick_res(files[key].keys(), res)
        fmt = files[key][r]
        f = fmt.get("jpg") or fmt.get("png") or fmt.get("exr")
        ext = "jpg" if "jpg" in fmt else ("png" if "png" in fmt else "exr")
        out.append((f["url"], os.path.join(OUT, "textures", name, f"{name}_{short}_{r}.{ext}"), f.get("size")))
    return out


def fetch_model(name, res):
    files = get_json(f"{API}/files/{name}")
    g = files.get("gltf") or {}
    if not g:
        log(f"  {name}: no glTF available")
        return []
    r = pick_res(g.keys(), res)
    entry = g[r]["gltf"]
    base = os.path.join(OUT, "models", name)
    out = [(entry["url"], os.path.join(base, os.path.basename(entry["url"])), entry.get("size"))]
    for rel, inc in (entry.get("include") or {}).items():
        out.append((inc["url"], os.path.join(base, rel.replace("/", os.sep)), inc.get("size")))
    return out


only = set(args.only.split(","))
jobs = []
if "hdris" in only:
    h = cfg["hdris"]
    for group, names in h["items"].items():
        for n in names:
            jobs.append(("hdri", n, lambda n=n: fetch_hdri(n, h["resolution"])))
if "textures" in only:
    t = cfg["textures"]
    for n in t["items"]:
        jobs.append(("texture", n, lambda n=n: fetch_texture(n, t["resolution"])))
if "models" in only:
    m = cfg["models"]
    for n in m["items"]:
        jobs.append(("model", n, lambda n=n: fetch_model(n, m["resolution"])))

log(f"[panora] {len(jobs)} assets → {OUT}")
failed = []
for i, (kind, name, resolve) in enumerate(jobs, 1):
    try:
        items = resolve()
    except Exception as e:
        log(f"[{i}/{len(jobs)}] {kind} {name}: lookup failed ({e})")
        failed.append(name)
        continue
    total = sum((s or 0) for _, _, s in items) / 1e6
    res = [download(u, p, s) for u, p, s in items]
    status = "FAILED" if "fail" in res else ("already there" if all(x == "skip" for x in res) else "done")
    if "fail" in res:
        failed.append(name)
    log(f"[{i}/{len(jobs)}] {kind} {name}: {len(items)} files, {total:.0f} MB — {status}")

log("[panora] finished" + (f" with {len(failed)} failures: {', '.join(failed)}" if failed else " — all assets downloaded"))
