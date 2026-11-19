# Sky Tree Tower — Fv2

Interactive explorer for Sky Tree Tower, Pine Avenue, Lahore.

- `public/skytree/index.html` — the explorer (`/skytree`): 9 pre-rendered camera paths, level hover, 360 tours.
- `public/skytree/site.html` — the editorial website (`/` and `/skytree/home`).
- `public/skytree/media/` — rendered frames (WebP, with phone-size `s/` copies), masks, panoramas.
- `render/` — the Blender 5.2 render kit (`scripts/produce.py` + batch files) that produces all media.

Deploy: import this repo in Vercel as a static project (no build step; `vercel.json` serves `public/`).
