// Sky Tree Tower · Live 3D explorer (Gaussian splat).
// Everything from the rendered explorer (floors, details, residences, shortlist, enquiry, 360 interiors,
// presentation, gallery, map) running on top of a real-time splat: hover any floor from any angle, click for
// details, explode the floors and orbit freely around them, fly inside Residence 10-A.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { SparkRenderer, SplatMesh, isMobile } from "@sparkjsdev/spark";

const M = "media/", BASE = M + "splat/";
const MOBILE = isMobile() || Math.min(screen.width, screen.height) < 820;
const TOUCH = matchMedia("(hover: none)").matches;
const $ = id => document.getElementById(id);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/* ================================================================== data (same as the rendered explorer) */
const LEVELS = [
  {n:"G",kind:"Retail · Grand Lobby",use:"lobby"},{n:"1",kind:"Retail & Dining",use:"retail"},{n:"2",kind:"Club & Amenities",use:"amenity"},
  ...Array.from({length:11},(_,i)=>({n:String(3+i),kind:"Residences",use:"res"})),
  {n:"PH",kind:"Sky Penthouses",use:"ph"}];
// floor heights (Blender metres, from the render kit's levels.json)
const Z = [[0,11.63],[11.63,18.93],[18.93,25.03],[25.03,28.53],[28.53,32.03],[32.03,35.53],[35.53,39.03],[39.03,42.53],
  [42.53,46.03],[46.03,49.53],[49.53,53.03],[53.03,56.53],[56.53,60.03],[60.03,63.53],[63.53,82.1]];
// floor plates measured from the trained splat (metres, tower-centred, +y = back, front faces Pine Avenue at -y)
const POD = [[-23.8,-26.4],[23.8,-26.4],[23.8,26.4],[-23.8,26.4]];
const U   = [[-23.6,-17.8],[-7.8,-17.8],[-7.8,5.6],[7.8,5.6],[7.8,-17.8],[23.6,-17.8],[23.6,27.0],[-23.6,27.0]];
const UPH = [[-24.8,-18.6],[-7.4,-18.6],[-7.4,5.6],[7.4,5.6],[7.4,-18.6],[24.8,-18.6],[24.8,27.0],[-24.8,27.0]];
const plateOf = i => i <= 2 ? POD : i === 14 ? UPH : U;
const UNITS = [
  {id:"A",beds:3,area:2150,price:"PKR 9.8 Cr"},{id:"B",beds:2,area:1480,price:"PKR 6.4 Cr"},
  {id:"C",beds:2,area:1460,price:"PKR 6.3 Cr"},{id:"D",beds:3,area:2120,price:"PKR 9.6 Cr"}];
const rnd = s => { let x = Math.sin(s * 99.13) * 43758.5453; return x - Math.floor(x); };
function status(level, uid){ if (level===10 && uid==="A") return "av"; const r = rnd(level*7 + uid.charCodeAt(0)); return r<.5?"av":r<.72?"res":"sold"; }
const ST = {av:["Available","var(--av)"],res:["Reserved","var(--res)"],sold:["Sold","var(--sold)"]};
const S = { hover:-1, sel:-1, avail:false, exploded:false, anim:false, busy:false, view:"aerial" };

/* ================================================================== renderer */
function webgl2(){ try { return !!document.createElement("canvas").getContext("webgl2"); } catch(e){ return false; } }
if (!webgl2()){ $("nogl").style.display = "flex"; $("loader")?.remove(); throw new Error("no webgl2"); }
const stage = $("stage");
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, MOBILE ? 1.5 : 2));
renderer.setSize(innerWidth, innerHeight);
stage.insertBefore(renderer.domElement, stage.firstChild);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.5, 30000);
const spark = new SparkRenderer({ renderer, enableLod: true, lodSplatCount: MOBILE ? 1_300_000 : 3_000_000 });
scene.add(spark);
new THREE.TextureLoader().load(BASE + "sky.jpg", t => { t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace; scene.background = t; },
  undefined, () => { scene.background = new THREE.Color(0xb9c4cc); });
// everything building-related lives in "world": Blender frame (metres, Z up, centred on the tower)
const world = new THREE.Group(); world.rotation.x = -Math.PI / 2; scene.add(world);
const B = (x, y, z) => new THREE.Vector3(x, z, -y);            // Blender -> three (for camera poses)

const meta = await fetch(BASE + "meta.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}));

/* ================================================================== splat: preview first, then the sharp one */
const mainFile = (MOBILE && meta.file_mobile) || meta.file || "skytree.spz";
const prevFile = meta.file_preview && meta.file_preview !== mainFile ? meta.file_preview : null;
const pct = e => e.lengthComputable ? (100 * e.loaded / e.total) : 0;
function addSplat(file, onProgress, parent = world, lod = true){ const m = new SplatMesh({ url: BASE + file + (meta.rev ? "?r=" + meta.rev : ""), lod, onProgress }); parent.add(m); return m; }
let mainSplat;
const firstReady = new Promise(res => {
  if (prevFile){
    const preview = addSplat(prevFile, e => { $("lbar").style.width = pct(e).toFixed(0) + "%"; });
    mainSplat = preview;
    preview.initialized.then(() => {
      res();
      const pill = $("sharp"); pill.style.display = "flex";
      const sharp = addSplat(mainFile, e => { $("sbar").style.width = pct(e).toFixed(0) + "%"; });
      sharp.visible = false;
      sharp.initialized.then(() => {
        sharp.visible = !S.exploded; world.remove(preview); try { preview.dispose(); } catch (e) {} mainSplat = sharp;
        pill.style.opacity = 0; setTimeout(() => pill.remove(), 700);
        if (!MOBILE) setTimeout(() => loadPieces(), 3000);      // desktops: have the explode ready before it's asked for
      });
    });
  } else {
    mainSplat = addSplat(mainFile, e => { $("lbar").style.width = pct(e).toFixed(0) + "%"; });
    mainSplat.initialized.then(res);
  }
});

/* ================================================================== satellite ground (Esri World Imagery) */
const SITE = { lat: meta.site_lat ?? 31.3793117, lon: meta.site_lon ?? 74.2543937 };
const qs = new URLSearchParams(location.search);
const MAP_DEG = Number(qs.get("mapdeg") ?? meta.map_bearing_deg ?? 0);
const mapGroup = new THREE.Group(); mapGroup.rotation.y = THREE.MathUtils.degToRad(MAP_DEG);
mapGroup.position.set(Number(qs.get("mapdx") ?? meta.map_dx ?? 0), 0, -Number(qs.get("mapdy") ?? meta.map_dy ?? 0)); scene.add(mapGroup);
scene.fog = new THREE.Fog(0xc8cdcf, 900, MOBILE ? 5000 : 9000);
function tileXY(lon, lat, z){ const n = 2 ** z, r = lat * Math.PI / 180;
  return [(lon + 180) / 360 * n * 256, (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n * 256]; }
function mapLayer(z, halfM, y, order){
  const mpp = 156543.03392 * Math.cos(SITE.lat * Math.PI / 180) / 2 ** z, half = Math.round(halfM / mpp), size = half * 2;
  const cv = document.createElement("canvas"); cv.width = cv.height = size; const g = cv.getContext("2d");
  g.fillStyle = "#8f8d84"; g.fillRect(0, 0, size, size);
  const [cx, cy] = tileXY(SITE.lon, SITE.lat, z), x0 = cx - half, y0 = cy - half;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(halfM * 2, halfM * 2), new THREE.MeshBasicMaterial({ map: tex, fog: true, depthWrite: false }));
  mesh.rotation.x = -Math.PI / 2; mesh.position.y = y; mesh.renderOrder = -10 - order; mapGroup.add(mesh);
  for (let ty = Math.floor(y0 / 256); ty <= Math.floor((y0 + size) / 256); ty++) for (let tx = Math.floor(x0 / 256); tx <= Math.floor((x0 + size) / 256); tx++){
    const im = new Image(); im.crossOrigin = "anonymous";
    im.onload = () => { g.drawImage(im, tx * 256 - x0, ty * 256 - y0); tex.needsUpdate = true; };
    im.src = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${ty}/${tx}`;
  }
}
setTimeout(() => { mapLayer(12, MOBILE ? 12000 : 20000, -0.9, 3); mapLayer(15, MOBILE ? 1500 : 2400, -0.7, 2); mapLayer(18, MOBILE ? 260 : 380, -0.5, 1); }, 500);
// soft lawn-toned apron: the rendered site (trees, lawns, roads) blends into the real satellite photo instead of
// meeting it at a hard, mismatched edge; also fills any thin spots in the splat's own ground with a matching tone
if (qs.get("noblend") !== "1"){
  const R0 = 118, R1 = 250, S = 512, cv = document.createElement("canvas"); cv.width = cv.height = S; const g = cv.getContext("2d");
  const gr = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  gr.addColorStop(0, "rgba(98,100,77,1)"); gr.addColorStop(R0 / R1, "rgba(98,100,77,0.97)");
  gr.addColorStop((R0 + R1) / 2 / R1, "rgba(104,106,84,0.55)"); gr.addColorStop(1, "rgba(110,110,92,0)");
  g.fillStyle = gr; g.fillRect(0, 0, S, S);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const apron = new THREE.Mesh(new THREE.CircleGeometry(R1, 96), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, fog: true }));
  apron.rotation.x = -Math.PI / 2; apron.position.y = -0.3; apron.renderOrder = -5; scene.add(apron);
}

/* ================================================================== floors: 3D overlays + pick volumes */
const GAP = 6.5;                                                      // explode spacing (m)
const offsetOf = i => i === 0 ? 0 : i * GAP + (i === 14 ? GAP : 0);
const lvG = [], fills = [], edges = [], picks = [];
function shapeOf(poly, grow = 0){ const s = new THREE.Shape();
  poly.forEach(([x, y], k) => { const gx = x + Math.sign(x) * grow, gy = y + Math.sign(y) * grow; k ? s.lineTo(gx, gy) : s.moveTo(gx, gy); }); return s; }
const GOLD = new THREE.Color(0xf1cd82);
LEVELS.forEach((L, i) => {
  const g = new THREE.Group(); world.add(g); lvG.push(g);
  const [zb, zt0] = Z[i], zt = i === 14 ? 87 : zt0;
  const geo = new THREE.ExtrudeGeometry(shapeOf(plateOf(i), 0.35), { depth: zt - zb - 0.14, bevelEnabled: false });
  geo.translate(0, 0, zb + 0.07);
  const fm = new THREE.MeshBasicMaterial({ color: GOLD, transparent: true, opacity: 0, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, fog: false });
  const fill = new THREE.Mesh(geo, fm); fill.renderOrder = 1000; fill.visible = false; g.add(fill); fills.push(fill);
  const em = new THREE.LineBasicMaterial({ color: 0xffe2a0, transparent: true, opacity: 0, depthWrite: false, depthTest: false, fog: false });
  const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), em); edge.renderOrder = 1001; edge.visible = false; g.add(edge); edges.push(edge);
  const pm = new THREE.MeshBasicMaterial({ visible: false });
  const pick = new THREE.Mesh(new THREE.ExtrudeGeometry(shapeOf(plateOf(i), 0.6), { depth: zt - zb, bevelEnabled: false }).translate(0, 0, zb), pm);
  pick.userData.level = i; g.add(pick); picks.push(pick);
});
function floorAvail(i){ const L = LEVELS[i]; if (!L || L.use !== "res") return null; return UNITS.filter(u => status(+L.n, u.id) === "av").length; }
const AVC = { hi: new THREE.Color(0x7fd1a0), mid: new THREE.Color(0xe0b35a), none: new THREE.Color(0xd4736a) };
function paint(){
  for (let i = 0; i < LEVELS.length; i++){
    const f = fills[i], e = edges[i]; let fo = 0, eo = 0, col = GOLD;
    if (S.avail){ const a = floorAvail(i); if (a !== null){ col = a >= 3 ? AVC.hi : a >= 1 ? AVC.mid : AVC.none; fo = .30; eo = .35; } }
    if (i === S.sel){ col = GOLD; fo = .30; eo = 1; } else if (i === S.hover){ col = GOLD; fo = .22; eo = .9; }
    f.material.color.copy(col); f.material.opacity = fo; e.material.opacity = eo; e.material.color.set(i === S.sel || i === S.hover ? 0xffe2a0 : col);
    f.visible = fo > 0; e.visible = eo > 0;
  }
}
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
function levelAt(x, y){
  if (S.busy) return -1;
  ndc.set(x / innerWidth * 2 - 1, -(y / innerHeight) * 2 + 1); ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObjects(picks, false)[0]; return hit ? hit.object.userData.level : -1;
}

/* ================================================================== camera + controls */
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.rotateSpeed = MOBILE ? 0.55 : 0.5;
controls.zoomSpeed = 0.9; controls.panSpeed = 0.8; controls.screenSpacePanning = true;
controls.minDistance = 12; controls.maxDistance = 560; controls.maxPolarAngle = THREE.MathUtils.degToRad(88);
const VIEWS = {
  aerial:   { t: "Aerial",         p: [-125, -175, 150], l: [0, 0, 32] },
  front:    { t: "Front",          p: [0, -168, 34],     l: [0, -8, 36] },
  entrance: { t: "Grand entrance", p: [0, -64, 4.5],     l: [0, -27, 7] },
  street:   { t: "Street level",   p: [26, -92, 2.2],    l: [0, -20, 22] },
  terrace:  { t: "Terrace garden", p: [0, -58, 46],      l: [0, -6, 26] },
  crown:    { t: "Crown",          p: [-48, -62, 108],   l: [0, 0, 78] },
  east:     { t: "East side",      p: [160, -46, 46],    l: [0, -4, 36] },
  back:     { t: "Rear garden",    p: [-70, 150, 70],    l: [0, 0, 32] },
};
camera.position.copy(B(-320, -420, 300)); controls.target.copy(B(0, 0, 35)); controls.update();
let flight = null;
function flyTo(p, l, ms = 2200, arc = true){
  return new Promise(done => {
    const p0 = camera.position.clone(), l0 = controls.target.clone(), p1 = Array.isArray(p) ? B(...p) : p, l1 = Array.isArray(l) ? B(...l) : l;
    const mid = p0.clone().lerp(p1, 0.5); if (arc) mid.y += Math.min(70, p0.distanceTo(p1) * 0.16);
    flight = { p0, mid, p1, l0, l1, t0: performance.now(), ms, done };
  });
}
function stepFlight(now){
  if (!flight) return; const f = flight, t = Math.min(1, (now - f.t0) / f.ms), e = ease(t);
  const a = f.p0.clone().lerp(f.mid, e), b = f.mid.clone().lerp(f.p1, e); camera.position.copy(a.lerp(b, e));
  controls.target.copy(f.l0.clone().lerp(f.l1, e)); if (t >= 1){ flight = null; f.done(); }
}
const goView = k => { const v = VIEWS[k]; if (!v) return Promise.resolve(); $("views").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.k === k)); return flyTo(v.p, v.l, 2400); };
// fly so a floor fills the view, keeping the current direction of looking
function focusFloor(i){
  const [zb, zt] = Z[i], zm = (zb + Math.min(zt, 72)) / 2 + (S.exploded ? offsetOf(i) : 0);
  const tgt = B(0, 0, zm), dir = camera.position.clone().sub(controls.target); dir.y = 0;
  if (dir.lengthSq() < 1) dir.set(0, 0, 1); dir.normalize();
  const portrait = innerHeight > innerWidth, dist = (portrait ? 250 : 150) * (S.exploded ? 1.3 : 1);
  const pos = tgt.clone().add(dir.clone().multiplyScalar(dist)); pos.y = zm + (portrait ? 40 : 28);
  // keep the building clear of the details panel (desktop: panel on the right; phones: bottom sheet)
  const px2m = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * dist / innerHeight;
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), dir).normalize();
  if (innerWidth > 760){ const sh = Math.min(420, innerWidth) / 2 * px2m; tgt.add(right.clone().multiplyScalar(sh)); pos.add(right.clone().multiplyScalar(sh)); }
  else { const dv = innerHeight * 0.30 * px2m; tgt.y -= dv; pos.y -= dv; }
  return flyTo(pos, tgt, 1500, false);
}

/* ================================================================== explode (real 3D, free orbit) */
let pieces = null, piecesLoading = null;
function loadPieces(onProgress){
  if (piecesLoading) return piecesLoading;
  const names = ["base", ...LEVELS.map((_, i) => "f" + String(i).padStart(2, "0"))];
  const prog = new Array(names.length).fill(0);
  piecesLoading = Promise.all(names.map((n, k) => {
    const parent = k === 0 ? world : lvG[k - 1];
    const m = addSplat("floors/" + n + ".spz", e => { prog[k] = e.lengthComputable ? e.loaded / e.total : 0; onProgress?.(prog.reduce((a, b) => a + b, 0) / names.length); }, parent, false);
    m.visible = false; return m.initialized.then(() => m);
  })).then(ms => (pieces = ms));
  return piecesLoading;
}
const bExp = $("explodeBtn");
function expLabel(t){ bExp.querySelector(".lab").textContent = t; }
async function toggleExplode(){
  if (S.anim) return; S.anim = true; setHover(-1);
  const opening = !S.exploded;
  if (opening){
    if (!pieces){ expLabel("Loading 0%"); await loadPieces(p => expLabel(`Loading ${Math.round(p * 100)}%`)); }
    pieces.forEach(m => m.visible = true); mainSplat.visible = false;
    document.body.classList.add("exploded"); bExp.classList.add("on"); expLabel("Close explode");
    if (S.sel < 0) flyTo(MOBILE && innerHeight > innerWidth ? [-300, -380, 150] : [-250, -300, 140], [0, 0, 96], 2600);
  } else { bExp.classList.remove("on"); expLabel("Explode floors"); document.body.classList.remove("exploded"); }
  const t0 = performance.now(), dur = 1900;
  await new Promise(done => { const step = now => { const t = Math.min(1, (now - t0) / dur), e = ease(opening ? t : 1 - t);
      lvG.forEach((g, i) => g.position.z = offsetOf(i) * e); world.updateMatrixWorld(true); pieces.forEach(m => { try { m.updateVersion(); } catch(err){} }); if (t < 1) requestAnimationFrame(step); else done(); }; requestAnimationFrame(step); });
  if (!opening){ mainSplat.visible = true; pieces.forEach(m => m.visible = false); lvG.forEach(g => g.position.z = 0); goView("aerial"); }
  S.exploded = opening; S.anim = false; paint();
  if (opening && S.sel >= 0) focusFloor(S.sel);
}
bExp.onclick = toggleExplode;

/* ================================================================== pins (anchored in 3D) */
const PINS = [
  { k: "pine", b: "360", t: "Pine Avenue", p: [45, -65, 4], n: null, act: () => openTour(false, false, "pine") },
  { k: "terrace", b: "360", t: "Terrace garden", p: [0, -6, 27.5], n: [0, -1, .4], act: () => openTour(false, false, "terrace") },
  { k: "rooftop", b: "360", t: "Rooftop garden", p: [0, 14, 89], n: [0, 0, 1], act: () => openTour(false, false, "rooftop") },
  { k: "res10a", b: "10-A", t: "Step inside", p: [-15.7, -18.6, 51.3], n: [0, -1, 0], act: () => enterUnit() },
];
const pinBox = $("pins"), tmpV = new THREE.Vector3(), camW = new THREE.Vector3();
PINS.forEach(P => { const el = document.createElement("button"); el.className = "pin3d"; el.innerHTML = `<span><b>${P.b}</b>${P.t}</span>`; el.onclick = P.act; el.style.display = "none"; pinBox.appendChild(el); P.el = el; });
function pinSync(){
  for (const P of PINS){
    const ok = P.k === "pine" || P.k === "res10a" ? true : (PV && PV[P.k]);
    if (!ok){ P.el.style.display = "none"; continue; }
    tmpV.set(...P.p).applyMatrix4(world.matrixWorld);
    let vis = true;
    if (P.n){ const nw = new THREE.Vector3(...P.n).applyQuaternion(world.quaternion); camW.copy(camera.position).sub(tmpV).normalize(); vis = nw.dot(camW) > 0.15; }
    const d = camera.position.distanceTo(tmpV); if (d > 420 || d < 6) vis = false;
    tmpV.project(camera);
    const x = (tmpV.x * .5 + .5) * innerWidth, y = (-tmpV.y * .5 + .5) * innerHeight;
    if (!vis || tmpV.z > 1 || x < 80 || x > innerWidth - 90 || y < 90 || y > innerHeight - 80){ P.el.style.display = "none"; continue; }
    P.el.style.display = "block"; P.el.style.left = x + "px"; P.el.style.top = (y - 12) + "px";
  }
}

/* floor labels beside each floor while exploded */
const lblBox = document.createElement("div"); document.body.appendChild(lblBox);
const fl = LEVELS.map((L, i) => { const el = document.createElement("button"); el.className = "flbl"; el.textContent = L.n;
  el.title = i === 0 ? "Ground" : L.n === "PH" ? "Penthouse" : "Floor " + L.n;
  el.onclick = () => select(i, true); el.onmouseenter = () => { S.hover = i; paint(); railMark(); }; el.onmouseleave = () => { S.hover = -1; paint(); railMark(); };
  lblBox.appendChild(el); return el; });
function labelSync(){
  const show = S.exploded || S.anim;
  // put the labels on whichever side of the tower faces the camera's right
  const camB = new THREE.Vector3().copy(camera.position).applyMatrix4(new THREE.Matrix4().copy(world.matrixWorld).invert());
  const ang = Math.atan2(camB.y, camB.x), sx = Math.cos(ang + Math.PI / 2) * -30, sy = Math.sin(ang + Math.PI / 2) * -30;
  fl.forEach((el, i) => {
    const op = show ? Math.min(1, lvG[i].position.z / Math.max(1, offsetOf(i)) * 1.5 || (i === 0 ? (S.exploded ? 1 : 0) : 0)) : 0;
    if (op <= 0.02){ el.style.display = "none"; return; }
    const [zb, zt] = Z[i]; tmpV.set(sx, sy, (zb + Math.min(zt, 70)) / 2 + lvG[i].position.z).applyMatrix4(world.matrixWorld).project(camera);
    if (tmpV.z > 1){ el.style.display = "none"; return; }
    el.style.display = "block"; el.style.opacity = op; el.classList.toggle("on", i === S.sel || i === S.hover);
    el.style.left = ((tmpV.x * .5 + .5) * innerWidth) + "px"; el.style.top = ((-tmpV.y * .5 + .5) * innerHeight) + "px";
  });
}
const flCss = document.createElement("style");
flCss.textContent = `.flbl{position:fixed;z-index:12;transform:translate(-50%,-50%);min-width:30px;padding:5px 8px;border-radius:999px;background:rgba(13,12,10,.66);border:1px solid rgba(230,194,122,.55);color:#f4ecdc;font:600 11px/1 Manrope,system-ui,sans-serif;cursor:pointer;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);transition:background .15s,color .15s}
.flbl:hover,.flbl.on{background:#e6c27a;color:#1a1408}`;
document.head.appendChild(flCss);

/* ================================================================== interaction */
const tip = $("tip"), hint = $("hint");
let down = null, idle = 0;
renderer.domElement.addEventListener("pointerdown", e => { down = { x: e.clientX, y: e.clientY, t: performance.now(), b: e.button }; idle = 0; flight = null; stage.classList.add("drag"); });
renderer.domElement.addEventListener("pointermove", e => {
  if (down){ if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6 && S.hover !== -1) setHover(-1); return; }
  if (e.pointerType === "mouse" && !S.anim) setHover(levelAt(e.clientX, e.clientY), e.clientX, e.clientY);
});
renderer.domElement.addEventListener("pointerup", e => { stage.classList.remove("drag");
  if (down && down.b === 0 && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 6 && performance.now() - down.t < 600 && !S.anim){
    const l = levelAt(e.clientX, e.clientY); if (l >= 0) select(l, true); else if (S.sel >= 0) closeSheet(); }
  down = null; });
renderer.domElement.addEventListener("pointerleave", () => { if (!down) setHover(-1); });
renderer.domElement.addEventListener("wheel", () => { idle = 0; flight = null; }, { passive: true });
function setHover(l, x, y){
  if (l !== S.hover){ S.hover = l; paint(); railMark(); }
  if (l >= 0 && x != null){ const L = LEVELS[l]; tip.innerHTML = `<b>${l===0?"Ground":L.n==="PH"?"Penthouse":"Floor "+L.n}</b> · ${L.kind}${L.use==="res"?` · ${floorAvail(l)} available`:""}`;
    tip.style.left = x + "px"; tip.style.top = y + "px"; tip.style.opacity = 1; renderer.domElement.style.cursor = "pointer"; }
  else { tip.style.opacity = 0; renderer.domElement.style.cursor = ""; }
}

/* ================================================================== rail */
const rail = $("rail");
LEVELS.forEach((L, i) => { const b = document.createElement("button"); b.textContent = L.n; b.dataset.i = i;
  b.onmouseenter = () => { S.hover = i; paint(); }; b.onmouseleave = () => { S.hover = -1; paint(); };
  b.onclick = () => select(i, true); rail.appendChild(b); });
const rl = document.createElement("div"); rl.className = "lbl"; rl.textContent = "FLOORS"; rail.appendChild(rl);
function railMark(){ [...rail.querySelectorAll("button")].forEach(b => { b.classList.toggle("sel", +b.dataset.i === S.sel); b.classList.toggle("hov", +b.dataset.i === S.hover); }); }

/* ================================================================== sheet (floor details) */
const sheet = $("sheet"), shBody = $("shBody");
$("shClose").onclick = () => closeSheet();
function closeSheet(){ sheet.classList.remove("open"); document.body.classList.remove("sheet-open"); S.sel = -1; railMark(); paint(); setHash(""); }
function select(i, fly){
  S.sel = i; S.hover = -1; tip.style.opacity = 0; railMark(); paint();
  if (fly) focusFloor(i);
  const L = LEVELS[i];
  $("shKind").textContent = L.kind;
  $("shTitle").textContent = i===0 ? "Ground Floor" : L.n==="PH" ? "Penthouse Level" : `Floor ${L.n}`;
  let h = "";
  if (L.use === "res"){
    const lvl = +L.n; const st = UNITS.map(u => status(lvl, u.id)); const avail = st.filter(s=>s==="av").length;
    h += `<div class="kv"><div><span>Residences</span><b>${UNITS.length}</b></div><div><span>Available</span><b>${avail}</b></div><div><span>Sizes</span><b>1,460–2,150 sq ft</b></div><div><span>Ceiling</span><b>3.2 m</b></div></div>`;
    h += `<div id="plan">${planSVG(lvl)}</div><div class="legend"><span><i style="background:var(--av)"></i>Available</span><span><i style="background:var(--res)"></i>Reserved</span><span><i style="background:var(--sold)"></i>Sold</span></div>`;
    UNITS.forEach((u,k) => { const s = ST[st[k]];
      h += `<button class="unit" data-u="${u.id}"><span class="dot" style="background:${s[1]}"></span><span class="n">${lvl}-${u.id}</span><span class="m">${u.beds} bed · ${u.area.toLocaleString()} sq ft</span><span class="p">${st[k]==="sold"?"Sold":u.price}</span><span class="fav ${isFav(lvl+"-"+u.id)?"on":""}" data-f="${lvl}-${u.id}">${isFav(lvl+"-"+u.id)?"♥":"♡"}</span></button>`; });
    if (lvl === 10) h += `<button class="btn fill" id="shTour">◎ Step inside Residence 10-A</button>`;
  } else if (L.use === "ph"){
    h += `<div class="kv"><div><span>Penthouses</span><b>2</b></div><div><span>Terraces</span><b>Private</b></div><div><span>Sizes</span><b>4,800+ sq ft</b></div><div><span>Views</span><b>360°</b></div></div><p style="color:var(--mute);line-height:1.7">Two sky penthouses beneath the slate mansard crowns, each with private terraces and panoramic views across Lahore.</p>`;
    if (PV && PV.rooftop) h += `<button class="btn" id="shRoof">◎ Rooftop garden 360°</button>`;
  } else {
    const d = {lobby:"A double-height grand lobby framed by Corinthian colonnades, with flagship retail along the arcade.", retail:"Curated retail and dining overlooking Pine Avenue.", amenity:"Residents' club: gym, spa, lounge and the podium-roof garden with its two domed pavilions."}[L.use];
    h += `<p style="color:var(--mute);line-height:1.7;margin-bottom:12px">${d}</p>`;
    if (L.use === "amenity" && PV && PV.terrace) h += `<button class="btn" id="shTerr">◎ Terrace garden 360°</button>`;
    if (L.use === "lobby") h += `<button class="btn" id="shLobby">◎ Fly to the grand entrance</button>`;
  }
  h += `<button class="btn" id="shEnq">Enquire about this floor</button>`;
  shBody.innerHTML = h; sheet.classList.add("open"); document.body.classList.add("sheet-open");
  shBody.querySelectorAll(".unit,.u").forEach(b => b.onclick = e => { const f = e.target.closest(".fav");
    if (f){ e.stopPropagation(); toggleFav(f.dataset.f); f.classList.toggle("on", isFav(f.dataset.f)); f.textContent = isFav(f.dataset.f) ? "♥" : "♡"; return; }
    unitClick(+L.n, b.dataset.u); });
  setHash(`floor=${L.n}`);
  const t = $("shTour"); if (t) t.onclick = enterUnit;
  const r = $("shRoof"); if (r) r.onclick = () => openTour(false, false, "rooftop");
  const te = $("shTerr"); if (te) te.onclick = () => openTour(false, false, "terrace");
  const lb = $("shLobby"); if (lb) lb.onclick = () => { closeSheet(); goView("entrance"); };
  $("shEnq").onclick = () => openModal("mEnquire");
}
const VIEWS_U = {A:"Pine Avenue & sunset", B:"Pine Avenue", C:"Garden court", D:"Garden court & sunrise"};
function unitClick(lvl, uid){
  const u = UNITS.find(x=>x.id===uid), s = status(lvl, uid), key = `${lvl}-${uid}`;
  $("uTitle").textContent = `Residence ${key}`;
  const px = parseFloat(u.price.replace(/[^0-9.]/g, "")) * (1 + (lvl - 3) * 0.012), price = `PKR ${px.toFixed(2)} Cr`;
  $("uBody").innerHTML = `<div class="plan">${unitPlanSVG(u)}</div><div>
    <h4>${u.beds}-Bed Residence</h4><div class="meta">Floor ${lvl} · ${VIEWS_U[uid]} · <span style="color:${ST[s][1]}">${ST[s][0]}</span></div>
    <ul><li><span>Covered area</span>${u.area.toLocaleString()} sq ft</li><li><span>Bedrooms</span>${u.beds} en-suite</li>
    <li><span>Ceiling</span>3.2 m</li><li><span>Price</span>${s === "sold" ? "Sold" : price}</li></ul>
    <div class="pay">Indicative plan: 20% booking · 40% over 36 monthly instalments · 40% on possession.<br>Preview data for this demo.</div>
    ${lvl === 10 && uid === "A" ? `<button class="btn fill" id="uTour">◎ Step inside Residence 10-A</button>` : ""}
    <button class="btn" id="uFav">${isFav(key) ? "♥ In your shortlist" : "♡ Add to shortlist"}</button>
    <button class="btn" id="uEnq">Enquire about ${key}</button></div>`;
  openModal("mUnit"); setHash(`unit=${key}`);
  const t = $("uTour"); if (t) t.onclick = () => { $("mUnit").classList.remove("open"); enterUnit(); };
  $("uFav").onclick = e => { toggleFav(key); e.target.textContent = isFav(key) ? "♥ In your shortlist" : "♡ Add to shortlist"; if (S.sel >= 0) select(S.sel); };
  $("uEnq").onclick = () => { $("mUnit").classList.remove("open"); openEnquiry(key); };
}
function unitPlanSVG(u){
  const big = u.beds === 3, W = big ? 520 : 440, H = 300;
  const rooms = big ? [["Living & Dining",0,0,260,170],["Kitchen",260,0,120,110],["Master Bed",380,0,140,170],["Bed 2",260,110,120,120],["Bed 3",0,170,150,130],["Bath",150,170,60,60],["Bath",380,170,70,60],["Balcony",450,170,70,130],["Foyer",150,230,110,70]]
                   : [["Living & Dining",0,0,230,170],["Kitchen",230,0,100,110],["Master Bed",330,0,110,170],["Bed 2",0,170,150,130],["Bath",150,170,60,70],["Foyer",210,170,120,130],["Balcony",330,170,110,130]];
  return `<svg viewBox="-10 -10 ${W+20} ${H+20}">${rooms.map(([n,x,y,w,h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${n==="Balcony"?"#1d2a20":"#1b1814"}" stroke="#d9b46a" stroke-width="2"/>
    <text x="${x+w/2}" y="${y+h/2}" fill="#f4ecdc" font-size="${w<80?10:13}" text-anchor="middle" dominant-baseline="middle" font-family="Manrope">${n}</text>`).join("")}</svg>`;
}
function planSVG(lvl){
  const c = id => ST[status(lvl,id)][1];
  return `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg" font-family="Manrope" font-size="11">
  <rect x="6" y="6" width="388" height="248" rx="8" fill="none" stroke="rgba(232,214,170,.25)"/>
  <g class="u" data-u="A"><rect x="18" y="18" width="130" height="110" rx="4" fill="${c("A")}" fill-opacity=".22" stroke="${c("A")}"/><text x="83" y="70" text-anchor="middle" fill="#f4ecdc" font-weight="600">${lvl}-A</text><text x="83" y="88" text-anchor="middle" fill="rgba(244,236,220,.6)">3 bed · 2,150</text></g>
  <g class="u" data-u="B"><rect x="18" y="134" width="130" height="108" rx="4" fill="${c("B")}" fill-opacity=".22" stroke="${c("B")}"/><text x="83" y="185" text-anchor="middle" fill="#f4ecdc" font-weight="600">${lvl}-B</text><text x="83" y="203" text-anchor="middle" fill="rgba(244,236,220,.6)">2 bed · 1,480</text></g>
  <g class="u" data-u="C"><rect x="252" y="134" width="130" height="108" rx="4" fill="${c("C")}" fill-opacity=".22" stroke="${c("C")}"/><text x="317" y="185" text-anchor="middle" fill="#f4ecdc" font-weight="600">${lvl}-C</text><text x="317" y="203" text-anchor="middle" fill="rgba(244,236,220,.6)">2 bed · 1,460</text></g>
  <g class="u" data-u="D"><rect x="252" y="18" width="130" height="110" rx="4" fill="${c("D")}" fill-opacity=".22" stroke="${c("D")}"/><text x="317" y="70" text-anchor="middle" fill="#f4ecdc" font-weight="600">${lvl}-D</text><text x="317" y="88" text-anchor="middle" fill="rgba(244,236,220,.6)">3 bed · 2,120</text></g>
  <rect x="160" y="40" width="80" height="180" rx="4" fill="rgba(244,236,220,.05)" stroke="rgba(232,214,170,.3)"/>
  <text x="200" y="120" text-anchor="middle" fill="rgba(244,236,220,.55)">Lifts</text><text x="200" y="136" text-anchor="middle" fill="rgba(244,236,220,.55)">& Lobby</text>
  <text x="200" y="250" text-anchor="middle" fill="rgba(244,236,220,.4)" font-size="9">PINE AVENUE ↓</text></svg>`;
}

/* ================================================================== shortlist, enquiry, availability, share, deep links */
const favs = new Set(JSON.parse((() => { try { return localStorage.getItem("st-favs") || "[]"; } catch(e){ return "[]"; } })()));
const isFav = k => favs.has(k);
function toggleFav(k){ favs.has(k) ? favs.delete(k) : favs.add(k); try { localStorage.setItem("st-favs", JSON.stringify([...favs])); } catch(e){} $("listN").textContent = favs.size; }
function openList(){
  const rows = [...favs].sort().map(k => { const [l, id] = k.split("-"), u = UNITS.find(x => x.id === id), s = status(+l, id);
    if (!u) return ""; const px = parseFloat(u.price.replace(/[^0-9.]/g, "")) * (1 + (+l - 3) * 0.012);
    return `<tr><td><b>${k}</b></td><td>${u.beds} bed</td><td>${u.area.toLocaleString()} sq ft</td><td>Floor ${l}</td><td>${VIEWS_U[id]}</td>
      <td style="color:${ST[s][1]}">${ST[s][0]}</td><td>${s==="sold"?"—":"PKR "+px.toFixed(2)+" Cr"}</td><td><button class="rm" data-k="${k}">✕</button></td></tr>`; }).join("");
  $("cmp").innerHTML = favs.size ? `<table><tr><th>Unit</th><th>Type</th><th>Area</th><th>Level</th><th>View</th><th>Status</th><th>Price</th><th></th></tr>${rows}</table>
    <button class="btn fill" id="listEnq" style="max-width:340px;margin:22px auto 0">Enquire about these ${favs.size}</button>`
    : `<p class="empty">Tap ♡ on any residence to compare it here.<br>Open a floor from the building or the floor list to begin.</p>`;
  document.querySelectorAll("#cmp .rm").forEach(b => b.onclick = () => { toggleFav(b.dataset.k); openList(); });
  const e = $("listEnq"); if (e) e.onclick = () => openEnquiry([...favs].join(", "));
  openModal("mList");
}
$("listBtn").onclick = openList; $("listN").textContent = favs.size;
function openEnquiry(what){ const sel = $("enqUnit"); if (what){ let o = [...sel.options].find(x => x.textContent.startsWith(what));
    if (!o){ o = document.createElement("option"); o.textContent = what; sel.appendChild(o); } sel.value = o.textContent; } openModal("mEnquire"); }
$("availBtn").onclick = e => { S.avail = !S.avail; e.currentTarget.classList.toggle("on", S.avail); $("avLegend").classList.toggle("on", S.avail); paint(); };
function setHash(h){ try { history.replaceState(null, "", h ? "#" + h : location.pathname + location.search); } catch(e){} }
$("shareBtn").onclick = async () => { const url = location.href;
  try { if (navigator.share) await navigator.share({title:"Sky Tree Tower · Live 3D", url}); else { await navigator.clipboard.writeText(url); toast("Link copied"); } } catch(e){} };
let toastT; function toast(t){ let el = $("toast"); if (!el){ el = document.createElement("div"); el.id="toast";
  el.style.cssText="position:fixed;left:50%;top:calc(90px + env(safe-area-inset-top));transform:translateX(-50%);z-index:45;background:rgba(13,12,10,.9);border:1px solid var(--line);padding:10px 16px;border-radius:12px;font-size:13px;transition:opacity .3s"; document.body.appendChild(el); }
  el.textContent = t; el.style.opacity = 1; clearTimeout(toastT); toastT = setTimeout(()=>el.style.opacity=0, 2600); }
function applyHash(){ const h = new URLSearchParams(location.hash.slice(1));
  if (h.get("view") && VIEWS[h.get("view")]) goView(h.get("view"));
  if (h.get("present")) presEnter();
  if (h.get("floor")){ const i = LEVELS.findIndex(L => L.n === h.get("floor")); if (i >= 0) select(i, true); }
  if (h.get("unit")){ const [l, id] = h.get("unit").split("-"); const i = LEVELS.findIndex(L => L.n === l); if (i >= 0){ select(i, true); unitClick(+l, id); } }
  if (h.get("tab") === "location") tabs.querySelector("[data-tab=location]").click();
  if (h.get("explode")) setTimeout(toggleExplode, 400);
  if (h.get("tour")) setTimeout(enterUnit, 600);
  if (h.get("enquire")) setTimeout(() => openEnquiry(), 400); }

/* ================================================================== 360 interiors (same rooms + hotspots as the rendered explorer) */
const ROOMS = [
  {id:"living", t:"Living & Dining", yaw:0, links:[{to:"view", yaw:88, pitch:-2, t:"Balcony view"}, {to:"bedroom", yaw:-150, pitch:-6, t:"Master bedroom"}], info:[{yaw:0, pitch:-4, t:"Kitchen & dining"}]},
  {id:"bedroom", t:"Master Bedroom", yaw:20, links:[{to:"living", yaw:126, pitch:-4, t:"Living & dining"}, {to:"view", yaw:88, pitch:2, t:"Balcony view"}], info:[]},
  {id:"view", t:"Balcony · Floor 10", yaw:0, links:[{to:"living", yaw:-158, pitch:-4, t:"Back inside"}, {to:"pine", yaw:0, pitch:-28, t:"Down to Pine Avenue"}], info:[]},
  {id:"terrace", t:"Terrace Garden", yaw:0, links:[{to:"rooftop", yaw:0, pitch:48, t:"Up to the rooftop garden"}, {to:"pine", yaw:180, pitch:-30, t:"Down to Pine Avenue"}], info:[{yaw:0, pitch:-8, t:"Skylight & flower court"}]},
  {id:"rooftop", t:"Rooftop Garden", yaw:180, links:[{to:"terrace", yaw:90, pitch:-40, t:"Down to the terrace garden"}], info:[{yaw:180, pitch:-12, t:"Sky lounge · Pine Avenue below"}]},
  {id:"pine", t:"Pine Avenue", yaw:0, links:[{to:"view", yaw:-14, pitch:24, t:"Up to Residence 10-A"}], info:[{yaw:12, pitch:6, t:"Sky Tree Tower"}]}];
const LOOKS = ["morning","day","sunset","night"];
let viewer = null, PV = null, LOOK = "day", tourRoom = "living";
const pvReady = fetch(`${M}pano/variants.json`, {cache:"no-cache"}).then(r => r.ok ? r.json() : null).catch(() => null)
  .then(j => (PV = j || {living:["day"], bedroom:["day"], view:["day"]}));
const roomOK = id => !!(PV && PV[id]);
const lookFor = (room, look) => (PV[room] || ["day"]).includes(look) ? look : "day";
const sceneId = (room, look) => look === "day" ? room : room + "@" + look;
function pill(div, a){ div.classList.add("hs-pill"); if (a.info) div.classList.add("hs-info");
  const d = document.createElement("div"); d.innerHTML = `<i>${a.info ? "i" : "➜"}</i>${a.t}`; div.appendChild(d); }
function goRoom(room, keepView){ if (!roomOK(room)) return; tourRoom = room; const id = sceneId(room, lookFor(room, LOOK));
  if (keepView) viewer.loadScene(id, viewer.getPitch(), viewer.getYaw(), viewer.getHfov()); else viewer.loadScene(id); todSync(); }
function todSync(){ const t = $("tod"), av = PV[tourRoom] || ["day"]; t.classList.toggle("on", av.length > 1);
  const cur = lookFor(tourRoom, LOOK); $("todR").value = LOOKS.indexOf(cur);
  t.querySelectorAll(".tl span").forEach((sp, k) => { sp.classList.toggle("na", !av.includes(LOOKS[k])); sp.classList.toggle("cur", LOOKS[k] === cur); }); }
$("todR").addEventListener("input", e => { let k = +e.target.value; const av = PV[tourRoom] || ["day"];
  if (!av.includes(LOOKS[k])){ for (let d = 1; d < 4; d++){ if (av.includes(LOOKS[k+d])){ k += d; break; } if (av.includes(LOOKS[k-d])){ k -= d; break; } } }
  LOOK = LOOKS[k]; goRoom(tourRoom, true); });
async function waitPannellum(){ for (let k = 0; k < 60 && !window.pannellum; k++) await sleep(100); return !!window.pannellum; }
async function openTour(arrive, silent, start){
  if (!silent) openModal("mTour");
  await pvReady;
  const head = $("mTour").querySelector(".mh h3");
  if (viewer){ if (start && start !== tourRoom) goRoom(start); else if (arrive && !silent){ goRoom("living"); viewer.setHfov(55, 0); setTimeout(() => viewer.setHfov(100, 1600), 700); }
    head.textContent = (start && start !== "living" && start !== "bedroom" && start !== "view") ? "Sky Tree Tower · 360°" : "Unit 10-A · Virtual Tour"; return; }
  if (!(await waitPannellum())) return;
  const scenes = {};
  ROOMS.filter(r => roomOK(r.id)).forEach(r => (PV[r.id] || ["day"]).forEach(look => {
    scenes[sceneId(r.id, look)] = {title:r.t, panorama:`${M}pano/${look === "day" ? r.id : r.id + "@" + look}.jpg`, yaw:r.yaw, hfov:100, autoLoad:true,
      hotSpots: [...r.links.filter(l => roomOK(l.to)).map(l => ({pitch:l.pitch, yaw:l.yaw, createTooltipFunc:pill, createTooltipArgs:{t:l.t}, clickHandlerFunc:() => goRoom(l.to)})),
                 ...r.info.map(a => ({pitch:a.pitch, yaw:a.yaw, createTooltipFunc:pill, createTooltipArgs:{t:a.t, info:1}}))]}; }));
  tourRoom = start && roomOK(start) ? start : "living";
  const first = sceneId(tourRoom, lookFor(tourRoom, LOOK)); if (arrive) scenes[first].hfov = 48;
  viewer = pannellum.viewer("pano", {default:{firstScene:first, sceneFadeDuration:700, autoRotate:-1.5, showControls:false}, scenes});
  if (arrive && !silent) viewer.on("load", function once(){ viewer.off("load", once); viewer.setHfov(100, 1800); });
  const rb = $("rooms"); rb.innerHTML = "";
  ROOMS.filter(r => roomOK(r.id)).forEach(r => { const b = document.createElement("button"); b.textContent = r.t; b.dataset.r = r.id; b.onclick = () => goRoom(r.id); rb.appendChild(b); });
  viewer.on("scenechange", id => { tourRoom = id.split("@")[0]; rb.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.r === tourRoom)); todSync(); });
  rb.querySelector(`[data-r="${tourRoom}"]`)?.classList.add("on"); todSync();
  head.textContent = (tourRoom === "living" || tourRoom === "bedroom" || tourRoom === "view") ? "Unit 10-A · Virtual Tour" : "Sky Tree Tower · 360°";
}
function prepTour(){ const m = $("mTour"); m.classList.add("pre"); if (!viewer) openTour(true, true); else viewer.loadScene("living", 0, 0, 48); }
function arrive(){ const m = $("mTour"); m.classList.remove("pre"); m.classList.add("open", "arrive"); if (viewer){ try { viewer.setHfov(100, 2400); } catch(e){} }
  setTimeout(() => m.classList.remove("arrive"), 1900); }
// the 3D way in: glide to the front of Residence 10-A (floor 10, west wing), then push through the glass into the 360 tour
let entering = false;
async function enterUnit(){
  if (entering) return; entering = true;
  if (S.exploded) await toggleExplode();
  closeSheet(); setHover(-1); document.body.classList.add("busy"); S.busy = true; prepTour();
  const zf = 51.3, xw = -15.7, yf = -17.8;
  await flyTo([xw - 18, yf - 70, zf + 10], [xw, yf, zf], 2400);
  stage.classList.add("dive");
  await flyTo([xw, yf - 2.2, zf], [xw, yf + 10, zf - 0.6], 1500, false);
  arrive();
  await sleep(400); stage.classList.remove("dive");
  camera.position.copy(B(xw - 30, yf - 95, zf + 14)); controls.target.copy(B(xw, yf, zf - 6)); controls.update();
  document.body.classList.remove("busy"); S.busy = false; entering = false;
}
$("tourBtn").onclick = enterUnit;

/* ================================================================== modals, tabs, map, gallery */
function openModal(id){ $(id).classList.add("open"); }
document.querySelectorAll("[data-close]").forEach(b => b.onclick = () => { b.closest(".modal").classList.remove("open","pre","arrive"); setTab("explore"); });
const tabs = $("tabs");
function setTab(t){ tabs.querySelectorAll("button").forEach(b=>b.classList.toggle("on", b.dataset.tab===t)); }
tabs.onclick = e => { const t = e.target.closest("button")?.dataset.tab; if (!t) return; setTab(t);
  document.querySelectorAll(".modal").forEach(m=>m.classList.remove("open"));
  if (t==="gallery"){ openModal("mGallery"); buildGallery(); }
  if (t==="location"){ openModal("mLocation"); openMap(); } };
let mapLoading = null;
function loadScript(u){ return new Promise((ok, no) => { const s = document.createElement("script"); s.src = u; s.onload = ok; s.onerror = no; document.head.appendChild(s); }); }
async function openMap(){
  const host = $("nbHost");
  if (!mapLoading){ const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"; document.head.appendChild(l);
    mapLoading = loadScript("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js").then(() => loadScript("neighbourhood.js?v=3")); }
  try { await mapLoading; window.SkyTreeMap.open(host); } catch(e){ host.innerHTML = '<p style="padding:30px;color:var(--mute)">The map needs an internet connection.</p>'; }
}
$("enquireBtn").onclick = () => openModal("mEnquire");
$("enqForm").onsubmit = e => { e.preventDefault(); $("enqOk").style.display="block"; };
const enqU = $("enqUnit"); for (let l=3;l<=13;l++) UNITS.forEach(u => { const o = document.createElement("option"); o.textContent = `${l}-${u.id} · ${u.beds} bed`; enqU.appendChild(o); });
const STILLS = ["front_day","aerial_day","corner_day","entrance_day","front_dusk","front_night","corner_night"];
function buildGallery(){ const g = $("gal"); if (g.children.length) return;
  STILLS.forEach(s => { const im = document.createElement("img"); im.loading="lazy"; im.src = `${M}stills/s/${s}.webp`; im.dataset.full = `${M}stills/${s}.webp`; im.alt = s.replace("_"," ");
    im.onerror = () => im.remove(); im.onclick = () => { const lb = $("lightbox"); lb.querySelector("img").src = im.dataset.full; lb.classList.add("open"); }; g.appendChild(im); }); }
$("lightbox").onclick = e => e.currentTarget.classList.remove("open");

/* ================================================================== views strip, street toggle */
const vs = $("views");
for (const [k, v] of Object.entries(VIEWS)){ const b = document.createElement("button"); b.textContent = v.t; b.dataset.k = k; b.onclick = () => { idle = 0; if (S.exploded) toggleExplode(); goView(k); }; vs.appendChild(b); }
$("viewsBtn").onclick = e => { vs.classList.toggle("on"); e.currentTarget.classList.toggle("on", vs.classList.contains("on")); };
const bView = $("viewBtn");
bView.onclick = async () => { if (S.exploded) await toggleExplode(); S.view = S.view === "street" ? "aerial" : "street"; goView(S.view === "street" ? "street" : "aerial");
  bView.classList.toggle("on", S.view === "street"); bView.querySelector(".lab").textContent = S.view === "street" ? "Aerial view" : "Street level"; bView.firstChild.textContent = S.view === "street" ? "✈" : "⌂"; };

/* ================================================================== presentation (guided camera, captions) */
const SPOTS = [
  {p:[-260,-520,260], l:[0,0,40], t:"Pine Avenue landmark", n:"The tower in its setting: the boulevard, the neighbourhood and the skyline."},
  {p:[90,-240,70], l:[0,-10,38], t:"Approach from the boulevard", n:"Direct frontage on Pine Avenue with a private forecourt."},
  {p:[0,-150,40], l:[0,-8,40], t:"Signature facade", n:"Limestone piers, bronze glazing and the SKY TREE crest."},
  {p:[-48,-62,108], l:[0,0,78], t:"The crown", n:"Slate mansard crowns over the sky penthouses."},
  {p:[0,-58,46], l:[0,-6,26], t:"Terrace garden", n:"The podium-roof garden between the twin wings."},
  {p:[160,-46,46], l:[0,-4,36], t:"The east elevation", n:"Balconies, the emblem and the residents' drive."},
  {p:[26,-92,2.2], l:[0,-20,22], t:"Arrival on Pine Avenue", n:"Landscaped forecourt, palms and the arcade."},
  {p:[0,-64,4.5], l:[0,-27,7], t:"Grand entrance", n:"The double-height lobby beneath the tower."}];
let pIdx = 0;
function presShow(){ const s = SPOTS[pIdx]; $("pNum").textContent = `${pIdx+1} / ${SPOTS.length}`; $("pTitle").textContent = s.t; $("pNote").textContent = s.n; }
async function presGo(dir, to){ pIdx = to != null ? to : (pIdx + dir + SPOTS.length) % SPOTS.length; presShow(); const s = SPOTS[pIdx]; idle = 0; await flyTo(s.p, s.l, 3200); }
async function presEnter(){ if (S.exploded) await toggleExplode(); closeSheet(); document.body.classList.add("present"); presGo(0, 0);
  try { if (!document.fullscreenElement && innerWidth > 760) document.documentElement.requestFullscreen(); } catch(e){} }
function presExit(){ document.body.classList.remove("present"); try { if (document.fullscreenElement) document.exitFullscreen(); } catch(e){} }
$("presBtn").onclick = presEnter; $("pPrev").onclick = () => presGo(-1); $("pNext").onclick = () => presGo(1); $("pExit").onclick = presExit;
addEventListener("keydown", e => {
  if (e.key==="Escape"){ document.querySelectorAll(".modal.open").forEach(m=>m.classList.remove("open")); $("lightbox").classList.remove("open"); setTab("explore"); }
  if (document.body.classList.contains("present")){ if (e.key==="ArrowRight"||e.key===" "||e.key==="PageDown"){ e.preventDefault(); presGo(1); } else if (e.key==="ArrowLeft"||e.key==="PageUp"){ e.preventDefault(); presGo(-1); } else if (e.key==="Escape") presExit(); return; }
  if (document.querySelector(".modal.open")) return;
  if (e.key === "e" || e.key === "E") toggleExplode();
  if ((e.key === "ArrowUp" || e.key === "ArrowDown") && S.sel >= 0){ e.preventDefault(); const n = Math.max(0, Math.min(LEVELS.length - 1, S.sel + (e.key === "ArrowUp" ? 1 : -1))); select(n, true); }
});

/* ================================================================== loop */
addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
let last = performance.now();
renderer.setAnimationLoop(now => {
  const dt = Math.min(0.05, (now - last) / 1000); last = now; idle += dt;
  stepFlight(now);
  const calm = !flight && idle > 10 && S.sel < 0 && !document.querySelector(".modal.open") && !document.body.classList.contains("present") && !S.busy;
  controls.autoRotate = calm; controls.autoRotateSpeed = 0.35;
  controls.enabled = !S.busy;
  controls.update(dt);
  if (!S.busy){
    if (camera.position.y < 1.4) camera.position.y = 1.4;
    const r = Math.hypot(camera.position.x, camera.position.z), rmax = S.exploded ? 600 : 470;
    if (r > rmax){ camera.position.x *= rmax / r; camera.position.z *= rmax / r; }
    const tr = Math.hypot(controls.target.x, controls.target.z); if (tr > 140){ controls.target.x *= 140 / tr; controls.target.z *= 140 / tr; }
    controls.target.y = Math.max(0, Math.min(S.exploded ? 200 : 110, controls.target.y));
  }
  world.updateMatrixWorld(); camera.updateMatrixWorld();
  try { pinSync(); labelSync(); } catch(e){}
  renderer.render(scene, camera);
});

/* ================================================================== boot */
paint();
await firstReady;
const ld = $("loader"); ld.style.opacity = 0; setTimeout(() => ld.remove(), 800);
await flyTo(VIEWS.aerial.p, VIEWS.aerial.l, 3600);
applyHash();
setTimeout(() => { hint.style.opacity = 0; }, 7000);
window.SkyTree3D = { get pieces(){ return pieces; }, lvG, get main(){ return mainSplat; }, flyTo, goView, select, toggleExplode, enterUnit, openTour, camera, controls, levelAt };
