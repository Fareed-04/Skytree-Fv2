"""
Download the free BlenderKit models listed in render/blenderkit_assets.json (cars, palms, trees, shrubs)
into render/assets/bk/<slug>/. Royalty-free licence, no account needed for free assets. Resumable.

  blender -b --factory-startup --python scripts/fetch_blenderkit.py      (or plain python)
"""
import json, os, sys, uuid, urllib.request, time, subprocess, shutil, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.dirname(HERE)
OUT = os.path.join(RENDER, "assets", "bk")
UA = {"User-Agent": "Mozilla/5.0 (Panora render kit)"}
SCENE = str(uuid.uuid4())

CURL = shutil.which("curl") or shutil.which("curl.exe") or r"C:\Windows\System32\curl.exe"

def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)

def get_json(url):
    try:
        return json.load(get(url))
    except Exception as e:          # Blender's Python on Windows can fail TLS verification: use Windows' curl
        out = subprocess.run([CURL, "-sSL", "-A", UA["User-Agent"], url], capture_output=True, timeout=120)
        if out.returncode != 0:
            raise RuntimeError(f"urllib: {e}; curl: {out.stderr.decode(errors='ignore')[:200]}")
        return json.loads(out.stdout)

def download(url, dst):
    try:
        with get(url, 600) as r, open(dst, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b)
    except Exception as e:
        out = subprocess.run([CURL, "-sSL", "-A", UA["User-Agent"], "-o", dst, url], capture_output=True, timeout=1800)
        if out.returncode != 0:
            raise RuntimeError(f"urllib: {e}; curl: {out.stderr.decode(errors='ignore')[:200]}")

def main(only=None, manifest="blenderkit_assets.json"):
    items = json.load(open(os.path.join(RENDER, manifest)))
    os.makedirs(OUT, exist_ok=True)
    log = open(os.path.join(OUT, "download-log.txt"), "a")
    ok = 0
    for it in items:
        if only and it["slug"] not in only:
            continue
        ext = ".glb" if it["fileType"] == "gltf" else ".blend"
        d = os.path.join(OUT, it["slug"]); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, it["slug"] + ext)
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            print(f"  have {it['slug']}"); ok += 1; continue
        for attempt in range(3):
            try:
                info = get_json(f"{it['downloadUrl']}?scene_uuid={SCENE}")
                url = info.get("filePath") or info["filePaths"][0]["url"]
                tmp = dst + ".part"
                download(url, tmp)
                os.replace(tmp, dst)
                json.dump(it, open(os.path.join(d, "info.json"), "w"), indent=1)
                msg = f"  got {it['slug']} ({os.path.getsize(dst) / 1e6:.1f} MB) - {it['name']}"
                print(msg); log.write(msg + "\n"); ok += 1
                break
            except Exception as e:
                msg = f"  retry {it['slug']}: {type(e).__name__}: {e}"
                print(msg); log.write(msg + "\n"); log.flush(); time.sleep(3)
        else:
            log.write(f"  FAILED {it['slug']}\n")
    print(f"BlenderKit assets ready: {ok}/{len(items)}")

if __name__ == "__main__":
    try:
        import bpy  # noqa: F401  (inside Blender: only arguments after "--" are ours)
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    except ImportError:
        argv = sys.argv[1:]
    manifest = "blenderkit_assets.json"
    if "--manifest" in argv:
        k = argv.index("--manifest"); manifest = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    main(set(argv) or None, manifest)
