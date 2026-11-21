// Sky Tree Tower — Gaussian splat viewer (Spark + three.js). Phone-first: LoD splat budget per device,
// guided camera flights, constrained orbit, gentle idle drift.
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { SparkRenderer, SplatMesh, isMobile } from "@sparkjsdev/spark";

const BASE = "media/splat/";
const MOBILE = isMobile() || Math.min(screen.width, screen.height) < 820;
const $ = id => document.getElementById(id);

const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, MOBILE ? 1.5 : 2));
renderer.setSize(innerWidth, innerHeight);
$("stage").appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.5, 4000);
const spark = new SparkRenderer({ renderer, enableLod: true, lodSplatCount: MOBILE ? 1_200_000 : 3_000_000 });
scene.add(spark);

// sky: the same golden-hour sky the frames use, as an equirect backdrop
new THREE.TextureLoader().load(BASE + "sky.jpg", t => { t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace; scene.background = t; },
  undefined, () => { scene.background = new THREE.Color(0xb9c4cc); });

// the splat is trained in the render kit's frame: Blender metres, Z up, centred on the tower (x - CX, y - CY).
// three.js is Y up: rotate -90 deg about X.  B(x,y,z) -> T(x, z, -y)
const B = (x, y, z) => new THREE.Vector3(x, z, -y);
const meta = await fetch(BASE + "meta.json").then(r => r.ok ? r.json() : {}).catch(() => ({}));
// progressive loading: a small preview splat first (a few MB, on screen in seconds), then the sharp one for this
// device (phone or desktop) streams in behind it and replaces it the moment it is ready.
const mainFile = (MOBILE && meta.file_mobile) || meta.file || "skytree.spz";
const prevFile = meta.file_preview && meta.file_preview !== mainFile ? meta.file_preview : null;
function addSplat(file, onProgress){ const m = new SplatMesh({ url: BASE + file, lod: true, onProgress }); m.rotation.x = -Math.PI / 2; scene.add(m); return m; }
const pct = e => e.lengthComputable ? (100 * e.loaded / e.total) : 0;
let splat;
if (prevFile){
  const preview = addSplat(prevFile, e => { $("lbar").style.width = pct(e).toFixed(0) + "%"; });
  splat = preview;
  preview.initialized.then(() => {
    const pill = $("sharp"); if (pill) pill.style.display = "flex";
    const sharp = addSplat(mainFile, e => { const b = $("sbar"); if (b) b.style.width = pct(e).toFixed(0) + "%"; });
    sharp.visible = false;
    sharp.initialized.then(() => { sharp.visible = true; scene.remove(preview); try { preview.dispose(); } catch (e) {} splat = sharp;
      if (pill){ pill.style.opacity = 0; setTimeout(() => pill.remove(), 600); } });
  });
} else {
  splat = addSplat(mainFile, e => { $("lbar").style.width = pct(e).toFixed(0) + "%"; });
}
const firstSplat = splat;

// ground: real satellite imagery (Esri World Imagery) laid under the splat, so beyond the captured site you see
// the surrounding city instead of empty space. Three rings of detail; north = Blender +Y unless map_bearing_deg says otherwise.
const SITE = { lat: meta.site_lat ?? 31.3793117, lon: meta.site_lon ?? 74.2543937 };
const qs = new URLSearchParams(location.search);
const MAP_DEG = Number(qs.get("mapdeg") ?? meta.map_bearing_deg ?? 0);
const MAP_DX = Number(qs.get("mapdx") ?? meta.map_dx ?? 0), MAP_DY = Number(qs.get("mapdy") ?? meta.map_dy ?? 0);
const mapGroup = new THREE.Group(); mapGroup.rotation.y = THREE.MathUtils.degToRad(MAP_DEG); mapGroup.position.set(MAP_DX, 0, -MAP_DY); scene.add(mapGroup);
scene.fog = new THREE.Fog(0xc8cdcf, 900, MOBILE ? 5000 : 9000);
function tileXY(lon, lat, z){ const n = 2 ** z, r = lat * Math.PI / 180;
  return [(lon + 180) / 360 * n * 256, (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n * 256]; }
function mapLayer(z, halfM, y, order){
  const mpp = 156543.03392 * Math.cos(SITE.lat * Math.PI / 180) / 2 ** z;
  const half = Math.round(halfM / mpp), size = half * 2;
  const cv = document.createElement("canvas"); cv.width = cv.height = size; const g = cv.getContext("2d");
  g.fillStyle = "#8f8d84"; g.fillRect(0, 0, size, size);
  const [cx, cy] = tileXY(SITE.lon, SITE.lat, z); const x0 = cx - half, y0 = cy - half;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const mat = new THREE.MeshBasicMaterial({ map: tex, fog: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: order, polygonOffsetUnits: order });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(halfM * 2, halfM * 2), mat);
  mesh.rotation.x = -Math.PI / 2; mesh.position.y = y; mesh.renderOrder = -10 - order; mapGroup.add(mesh);
  const tx0 = Math.floor(x0 / 256), tx1 = Math.floor((x0 + size) / 256), ty0 = Math.floor(y0 / 256), ty1 = Math.floor((y0 + size) / 256);
  let pending = 0;
  for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++){
    const im = new Image(); im.crossOrigin = "anonymous"; pending++;
    im.onload = () => { g.drawImage(im, tx * 256 - x0, ty * 256 - y0); tex.needsUpdate = true; };
    im.src = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${ty}/${tx}`;
  }
}
// outer -> inner (inner layers draw on top); phones get lighter layers
setTimeout(() => {
  mapLayer(12, MOBILE ? 12000 : 20000, -0.9, 3);
  mapLayer(15, MOBILE ? 1500 : 2400, -0.7, 2);
  mapLayer(18, MOBILE ? 260 : 380, -0.5, 1);
}, 400);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.rotateSpeed = MOBILE ? 0.55 : 0.45;
controls.minDistance = 15; controls.maxDistance = 420; controls.maxPolarAngle = Math.PI * 0.495; controls.screenSpacePanning = true;
controls.panSpeed = 0.6; controls.zoomSpeed = 0.9;
const TARGET0 = B(0, 0, 32);

// guided views (Blender coordinates relative to the tower centre): position, look-at
const VIEWS = {
  front:    { t: "Front",          p: [0, -165, 30],   l: [0, -10, 34] },
  aerial:   { t: "Aerial",         p: [-120, -170, 150], l: [0, 0, 30] },
  entrance: { t: "Entrance",       p: [0, -62, 4],     l: [0, -27, 6] },
  terrace:  { t: "Terrace garden", p: [0, -55, 48],    l: [0, -10, 25] },
  rooftop:  { t: "Rooftop",        p: [-40, -45, 115], l: [-10, -6, 79] },
  east:     { t: "East side",      p: [150, -40, 40],  l: [0, -5, 35] },
};
camera.position.copy(B(...VIEWS.front.p).add(new THREE.Vector3(0, 0, 0))); controls.target.copy(B(...VIEWS.front.l)); controls.update();

let flight = null;
function flyTo(key, ms = 2200){
  const v = VIEWS[key]; if (!v) return;
  const p0 = camera.position.clone(), l0 = controls.target.clone(), p1 = B(...v.p), l1 = B(...v.l);
  // arc a little upward through the middle of the flight so it reads as a drone move, not a slide
  const mid = p0.clone().lerp(p1, 0.5); mid.y += Math.min(60, p0.distanceTo(p1) * 0.18);
  const t0 = performance.now(); flight = { p0, mid, p1, l0, l1, t0, ms };
  document.querySelectorAll("#views button").forEach(b => b.classList.toggle("on", b.dataset.k === key));
}
const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
function stepFlight(now){
  if (!flight) return; const f = flight, t = Math.min(1, (now - f.t0) / f.ms), e = ease(t);
  const a = f.p0.clone().lerp(f.mid, e), b = f.mid.clone().lerp(f.p1, e); camera.position.copy(a.lerp(b, e));
  controls.target.copy(f.l0.clone().lerp(f.l1, e)); if (t >= 1) flight = null;
}
const bar = $("views");
for (const [k, v] of Object.entries(VIEWS)){ const b = document.createElement("button"); b.textContent = v.t; b.dataset.k = k; b.onclick = () => { idle = 0; flyTo(k); }; bar.appendChild(b); }

// idle: slow orbit after 8 s without touch
let idle = 0, last = performance.now();
for (const ev of ["pointerdown", "wheel", "touchstart"]) renderer.domElement.addEventListener(ev, () => { idle = 0; flight = null; }, { passive: true });

addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
firstSplat.initialized.then(() => { $("loader").style.opacity = 0; setTimeout(() => $("loader").remove(), 700); flyTo("aerial", 3200); });

renderer.setAnimationLoop(now => {
  const dt = Math.min(0.05, (now - last) / 1000); last = now; idle += dt;
  stepFlight(now);
  if (!flight && idle > 8){ controls.autoRotate = true; controls.autoRotateSpeed = 0.35; } else controls.autoRotate = false;
  controls.update(dt);
  // keep the camera out of the ground and inside the captured site
  if (camera.position.y < 1.6) camera.position.y = 1.6;
  const r = Math.hypot(camera.position.x, camera.position.z); if (r > 430){ camera.position.x *= 430 / r; camera.position.z *= 430 / r; }
  renderer.render(scene, camera);
});
window.SkyTreeSplat = { flyTo, VIEWS, camera, controls };
