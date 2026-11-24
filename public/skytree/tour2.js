/* Sky Tree · tour v2: glass floor-plan mini-map (where am I, tap to jump) and fly-through transitions between 360s.
   Shared by the rendered explorer and the Ultra Experience; the tour code calls window.SkyTour.fly(). */
(() => {
const M = "media/";
/* Residence 10-A, metres (x right, y down / away from the balcony).  The 360 points sit where the cameras stood. */
const PLAN_W = 17.2, PLAN_H = 13.6;
const DOTS = {           // room id -> [x, y] on the plan
  living:  [5.2, 3.6], bedroom: [14.4, 4.6], view: [8.6, -0.9]
};
const LABEL = { living: "Living & Dining", bedroom: "Master Bedroom", view: "Balcony" };
const TRANS = {};        // "from>to" -> video url; filled from media/pano/trans/index.json when rendered fly-throughs exist
fetch(M + "pano/trans/index.json", {cache: "no-cache"}).then(r => r.ok ? r.json() : {}).then(j => Object.assign(TRANS, j || {})).catch(() => {});

function planSVG(){
  const s = 20, X = v => (v * s).toFixed(1), W = 0.22;   // wall thickness 22 cm
  const wall = (x1, y1, x2, y2, t = W) => `<line x1="${X(x1)}" y1="${X(y1)}" x2="${X(x2)}" y2="${X(y2)}" class="w" style="stroke-width:${t * s}"/>`;
  const thin = (x1, y1, x2, y2) => `<line x1="${X(x1)}" y1="${X(y1)}" x2="${X(x2)}" y2="${X(y2)}" class="t"/>`;
  const rect = (x, y, w, h, c = "f") => `<rect x="${X(x)}" y="${X(y)}" width="${X(w)}" height="${X(h)}" class="${c}" rx="${c === "f" ? 3 : 0}"/>`;
  const door = (x, y, r, a0) => { const a = a0 * Math.PI / 180, b = (a0 + 90) * Math.PI / 180;
    return `<path class="t" d="M${X(x)} ${X(y)} L${X(x + Math.cos(a) * r)} ${X(y + Math.sin(a) * r)} A${X(r)} ${X(r)} 0 0 1 ${X(x + Math.cos(b) * r)} ${X(y + Math.sin(b) * r)}"/>`; };
  const glass = (x1, x2, y) => `<line x1="${X(x1)}" y1="${X(y - .06)}" x2="${X(x2)}" y2="${X(y - .06)}" class="g"/><line x1="${X(x1)}" y1="${X(y + .06)}" x2="${X(x2)}" y2="${X(y + .06)}" class="g"/>`;
  const txt = (x, y, t) => `<text x="${X(x)}" y="${X(y)}">${t}</text>`;
  let g = "";
  // balcony (outside, along the front) with balustrade posts
  g += `<path class="t" d="M${X(0.6)} ${X(0)} L${X(0.6)} ${X(-1.9)} L${X(16.6)} ${X(-1.9)} L${X(16.6)} ${X(0)}"/>`;
  for (let x = 1.1; x < 16.4; x += 0.75) g += thin(x, -1.9, x, -1.62);
  // shell
  g += wall(0, 0, 0, PLAN_H) + wall(0, PLAN_H, PLAN_W, PLAN_H) + wall(PLAN_W, PLAN_H, PLAN_W, 0);
  g += wall(0, 0, 0.7, 0) + wall(7.9, 0, 9.6, 0) + wall(16.5, 0, PLAN_W, 0);
  g += glass(0.7, 7.9, 0) + glass(9.6, 16.5, 0);
  // master bedroom (front right) + its bath and wardrobe
  g += wall(9.6, 0, 9.6, 6.6) + wall(9.6, 6.6, 12.0, 6.6) + wall(13.0, 6.6, PLAN_W, 6.6);
  g += door(12.0, 6.6, 1.0, -90 + 180);
  g += rect(11.0, 1.6, 2.2, 2.4) + rect(10.1, 2.0, 0.45, 0.5) + rect(13.65, 2.0, 0.45, 0.5);           // bed + side tables
  g += rect(15.6, 1.2, 1.3, 3.8) + rect(10.0, 5.2, 2.6, 0.5);                                          // tv unit, wardrobe
  g += wall(13.6, 6.6, 13.6, 9.6, .12) + wall(13.6, 9.6, PLAN_W, 9.6, .12) + door(13.6, 8.6, .8, -90);  // ensuite
  g += rect(15.4, 7.0, 1.5, 0.7, "f") + `<circle cx="${X(14.4)}" cy="${X(9.0)}" r="${X(.28)}" class="f"/>`;
  // living & dining (front left), open kitchen behind
  g += rect(1.3, 1.4, 3.6, 0.9) + rect(1.3, 2.3, 0.9, 1.9) + rect(5.4, 1.6, 1.4, 1.0) + rect(2.6, 3.0, 1.8, 1.0, "r");   // L-sofa, table, rug
  g += rect(6.0, 4.6, 2.6, 1.0) + [6.4, 7.3, 8.2].map(x => `<circle cx="${X(x)}" cy="${X(4.3)}" r="${X(.2)}" class="f"/><circle cx="${X(x)}" cy="${X(5.9)}" r="${X(.2)}" class="f"/>`).join("");
  g += wall(0, 7.2, 3.6, 7.2, .12) + rect(4.4, 7.6, 3.4, 0.8) + rect(0.3, 7.5, 0.7, 4.0) + rect(4.6, 9.4, 2.8, 0.7, "f");  // kitchen
  // bedrooms 2 & 3 at the back, foyer + powder room
  g += wall(0, 11.0, 3.6, 11.0, .12) + wall(3.6, 7.2, 3.6, 9.0, .12) + wall(3.6, 10.0, 3.6, PLAN_H, .12);
  g += wall(8.8, 7.2, 8.8, PLAN_H) + wall(8.8, 9.8, 9.6, 9.8, .12) + door(8.8, 10.8, .85, 0);
  g += wall(9.6, 9.6, 9.6, PLAN_H, .12) + door(9.6, 11.6, .8, 0) + rect(10.5, 11.0, 2.0, 1.6) + rect(12.8, 11.4, 0.45, 0.5);
  g += wall(9.6, 9.6, 13.6, 9.6, .12) + door(11.2, 9.6, .8, 90 + 90);
  g += rect(14.2, 10.6, 2.0, 2.0) + rect(1.0, 11.6, 1.8, 1.4);
  g += txt(2.4, 6.3, "LIVING") + txt(5.5, 8.9, "KITCHEN") + txt(11.0, 5.0, "MASTER") + txt(14.4, 12.8, "BED 2") + txt(10.4, 13.1, "BED 3") + txt(4.6, 12.4, "FOYER") + txt(6.2, -0.55, "BALCONY");
  const pad = 14, vw = PLAN_W * s + pad * 2, vh = (PLAN_H + 2.2) * s + pad * 2;
  return `<svg viewBox="${-pad} ${-2.2 * s - pad} ${vw} ${vh}" xmlns="http://www.w3.org/2000/svg">${g}<g id="tpDots"></g></svg>`;
}

const host = document.querySelector("#mTour .mb"); if (!host) return;
const box = document.createElement("div"); box.id = "tplan";
box.innerHTML = `<button class="hd" id="tpToggle"><span>Residence 10-A</span><em id="tpRoom"></em><i></i></button><div class="pl">${planSVG()}</div>`;
host.appendChild(box);
const dotsG = box.querySelector("#tpDots"), s = 20;
let have = new Set();
function drawDots(cur){
  have = new Set([...document.querySelectorAll("#rooms button")].map(b => b.dataset.r));
  dotsG.innerHTML = Object.entries(DOTS).filter(([id]) => have.has(id)).map(([id, [x, y]]) =>
    `<g class="dot${id === cur ? " on" : ""}" data-r="${id}" transform="translate(${x * s} ${y * s})"><circle r="16" class="hit"/><circle r="9" class="halo"/><circle r="4.2" class="core"/>${id === cur ? '<path class="cone" d="M0 0 L-16 -30 A34 34 0 0 1 16 -30 Z"/>' : ""}<title>${LABEL[id] || id}</title></g>`).join("");
  dotsG.querySelectorAll(".dot").forEach(d => d.onclick = () => { const b = document.querySelector(`#rooms button[data-r="${d.dataset.r}"]`); b && b.click(); });
  const inside = cur in DOTS; box.classList.toggle("off", !inside);
  box.querySelector("#tpRoom").textContent = LABEL[cur] || "";
}
let cur = null, viewerRef = null;
function sync(){ const b = document.querySelector("#rooms button.on"); const r = b ? b.dataset.r : null; if (r !== cur){ cur = r; drawDots(cur); } }
new MutationObserver(sync).observe(document.getElementById("rooms"), {subtree: true, attributes: true, childList: true});
box.querySelector("#tpToggle").onclick = () => box.classList.toggle("min");
if (innerWidth < 760) box.classList.add("min");
/* the view cone follows where you look */
(function cone(){ requestAnimationFrame(cone); if (!viewerRef || !cur) return; const c = dotsG.querySelector(".dot.on .cone"); if (!c) return;
  try { const off = {living: 0, bedroom: 90, view: 0}[cur] || 0; c.setAttribute("transform", `rotate(${(viewerRef.getYaw() + off).toFixed(1)})`); } catch(e){} })();

/* fly-through: a rendered 1-1.5 s flight when we have one, otherwise a quick push toward the hotspot with motion blur */
const pano = document.getElementById("pano");
const vid = document.createElement("video"); vid.id = "tpFly"; vid.muted = true; vid.playsInline = true; vid.preload = "auto"; host.appendChild(vid);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function fly(from, to, link, viewer, go){
  viewerRef = viewer;
  const url = TRANS[from + ">" + to];
  if (url){
    try {
      vid.src = url; vid.currentTime = 0; vid.classList.add("on");
      if (link) viewer.lookAt(link.pitch, link.yaw, viewer.getHfov(), 350);
      await vid.play(); await sleep(Math.max(300, (vid.duration || 1.2) * 1000 - 380));
      go(); await sleep(420); vid.classList.remove("on"); return;
    } catch(e){ vid.classList.remove("on"); }
  }
  pano.classList.add("flyout");
  if (link) try { viewer.lookAt(link.pitch, link.yaw, 46, 520); } catch(e){}
  await sleep(480);
  pano.classList.remove("flyout"); pano.classList.add("flyin"); go();
  await sleep(40); pano.classList.add("flyin2"); await sleep(720); pano.classList.remove("flyin", "flyin2");
}
window.SkyTour = { fly, setViewer: v => viewerRef = v };
document.addEventListener("click", () => { if (!viewerRef && window.pannellum){ /* the viewer exposes itself via fly() calls */ } });
})();
