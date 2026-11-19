"""
Convert the PC render output (render/out/web) into web media for public/skytree/media.

  python render/scripts/prep_media.py <render_out_web_dir> <public/skytree/media>

orbit/explode frames -> WebP 1600 px (+ s/ 960 px for phones); masks copied as PNG; stills -> WebP 2560 (+ s/ 720 px
thumbnails); panoramas -> JPEG 4096 x 2048 q85.
"""
import os, sys, shutil, glob, subprocess
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade import grade

src, dst = sys.argv[1], sys.argv[2]
def webp(i, o, w, q):
    os.makedirs(os.path.dirname(o), exist_ok=True)
    im = Image.open(i).convert("RGB")
    if GRADE: im = grade(im)
    if im.width > w: im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(o, "WEBP", quality=q, method=6)
GRADE = True
n = 0
for sub, pre in (("orbit/day", "f_"), ("orbit/dusk", "f_"), ("explode/day", "e_"), ("ground/day", "g_")):
    for f in sorted(glob.glob(os.path.join(src, sub, pre + "*.jpg"))):
        b = os.path.splitext(os.path.basename(f))[0]
        webp(f, os.path.join(dst, sub, b + ".webp"), 1600, 80)
        webp(f, os.path.join(dst, sub, "s", b + ".webp"), 960, 76); n += 1
for sub in ("orbit/mask", "explode/mask", "ground/mask"):
    os.makedirs(os.path.join(dst, sub), exist_ok=True)
    for f in glob.glob(os.path.join(src, sub, "*.png")):
        shutil.copy(f, os.path.join(dst, sub, os.path.basename(f)))
# 3 x 3 path grid: 2560 px masters (+ s/ 1600 px for landscape phones), masks + smooth vector outlines
paths = []
for key in sorted(os.listdir(os.path.join(src, "p"))) if os.path.isdir(os.path.join(src, "p")) else []:
    fr = sorted(glob.glob(os.path.join(src, "p", key, "day", "f_*.jpg")))
    if len(fr) < 41: print(f"path {key}: only {len(fr)} frames, skipped"); continue
    for f in fr:
        b = os.path.splitext(os.path.basename(f))[0]
        webp(f, os.path.join(dst, "p", key, "day", b + ".webp"), 2560, 82)
        webp(f, os.path.join(dst, "p", key, "day", "s", b + ".webp"), 1600, 78); n += 1
    md = os.path.join(dst, "p", key, "mask"); os.makedirs(md, exist_ok=True)
    for f in glob.glob(os.path.join(src, "p", key, "mask", "*.png")): shutil.copy(f, md)
    paths.append(key)
if paths:
    import json; json.dump(paths, open(os.path.join(dst, "p", "paths.json"), "w"))
here = os.path.dirname(os.path.abspath(__file__))
for d in ["orbit", "ground", "explode"] + [f"p/{k}" for k in paths]:
    if os.path.isdir(os.path.join(dst, d, "mask")):
        subprocess.run([sys.executable, os.path.join(here, "mask_polys.py"), os.path.join(dst, d, "mask"), os.path.join(dst, d, "polys.json")], check=True)
for f in glob.glob(os.path.join(src, "stills", "*.jpg")):
    b = os.path.splitext(os.path.basename(f))[0]
    webp(f, os.path.join(dst, "stills", b + ".webp"), 2560, 84)
    webp(f, os.path.join(dst, "stills", "s", b + ".webp"), 720, 78)
# fly-in film: graded exactly like the orbit so the hand-over is invisible
fl = sorted(glob.glob(os.path.join(src, "flyin", "fl_*.jpg")))
if fl:
    import tempfile
    try:
        import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FF = shutil.which("ffmpeg")
    tmp = tempfile.mkdtemp()
    for k, f in enumerate(fl): grade(Image.open(f).convert("RGB")).save(os.path.join(tmp, f"fl_{k:03d}.jpg"), quality=93)
    os.makedirs(os.path.join(dst, "flyin"), exist_ok=True)
    for name, wv, crf in (("flyin.mp4", 1600, 20), ("flyin_s.mp4", 960, 23)):
        subprocess.run([FF, "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(tmp, "fl_%03d.jpg"), "-vf", f"scale={wv}:-2",
                        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                        os.path.join(dst, "flyin", name)], check=True)
    shutil.rmtree(tmp); print(f"fly-in: {len(fl)} frames encoded")
GRADE = False
os.makedirs(os.path.join(dst, "pano"), exist_ok=True)
for f in glob.glob(os.path.join(src, "pano", "*.jpg")):
    if os.path.basename(f).startswith(("living@", "bedroom@")): continue   # rejected interior variants
    im = Image.open(f).convert("RGB")
    if im.width > 4096: im = im.resize((4096, 2048), Image.LANCZOS)
    im.save(os.path.join(dst, "pano", os.path.basename(f)), "JPEG", quality=85, optimize=True, progressive=True)
pv = {}
for f in sorted(glob.glob(os.path.join(dst, "pano", "*.jpg"))):
    b = os.path.splitext(os.path.basename(f))[0]; room, _, look = b.partition("@")
    pv.setdefault(room, ["day"]); 
    if look: pv[room].append(look)
import json as _j; _j.dump(pv, open(os.path.join(dst, "pano", "variants.json"), "w"))
lj = os.path.join(src, "levels.json")
if os.path.exists(lj): shutil.copy(lj, os.path.join(dst, "levels.json"))
print(f"frames {n}, done -> {dst}")
