"""Search BlenderKit for free complete interior scenes; save results + thumbnails to out/bk_search/."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_blenderkit as fb
OUT = os.path.join(fb.RENDER, "out", "bk_search"); os.makedirs(OUT, exist_ok=True)
res = {}
for q in ["living room", "apartment", "luxury living room", "modern interior", "penthouse", "kitchen living room", "neoclassic living room", "interior scene"]:
    for at in ["scene", "model"]:
        url = "https://www.blenderkit.com/api/v1/search/?query=" + urllib.parse.quote(f"{q} asset_type:{at} is_free:true order:-score") + "&page_size=40"
        try: j = fb.get_json(url)
        except Exception as e: print("ERR", q, e); continue
        for r in j.get("results", []):
            if r.get("assetType") != at: continue
            if at == "model" and "interior" not in (r.get("name","") + " " + " ".join(r.get("tags", []))).lower(): continue
            f = [x for x in r.get("files", []) if x.get("fileType") == "blend"]
            if not f: continue
            res[r["id"]] = {"name": r.get("name"), "type": at, "q": q, "free": r.get("isFree"), "score": r.get("score"),
                            "bytes": f[0].get("fileSize") or r.get("fileSize"), "downloadUrl": f[0].get("downloadUrl"),
                            "thumb": r.get("thumbnailMiddleUrl") or r.get("thumbnailSmallUrl"), "tags": r.get("tags", [])[:12],
                            "desc": (r.get("description") or "")[:200], "faces": (r.get("dictParameters") or {}).get("faceCount")}
json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
print(len(res), "results")
for k, v in list(res.items())[:80]:
    if v["thumb"]:
        try: fb.download(v["thumb"], os.path.join(OUT, k + ".jpg"))
        except Exception as e: print("thumb", e)
print("done")
