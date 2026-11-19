import zipfile, os, glob
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "web")
out = os.path.join(R, "..", "web_pack.zip")
keys = ["h2", "m1", "m3", "g1", "g3", "h1", "h3"]
files = []
for k in keys:
    files += glob.glob(os.path.join(R, "p", k, "day", "*.jpg")) + glob.glob(os.path.join(R, "p", k, "mask", "*.png"))
files += glob.glob(os.path.join(R, "explode", "day", "*.jpg")) + glob.glob(os.path.join(R, "orbit", "dusk", "*.jpg")) + glob.glob(os.path.join(R, "stills", "*.jpg"))
with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_STORED) as z:
    for f in files: z.write(f, os.path.relpath(f, R))
os.replace(out + ".part", out)
print("packed", len(files), os.path.getsize(out) // 1048576, "MB")
