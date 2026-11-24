/* Sky Tree · UI v2 — progressive disclosure layer shared by the rendered explorer and the Ultra Experience.
   It builds a calm surface (brand · Enquire · menu, and a four-item dock) and drives the existing controls,
   so every feature keeps working exactly as before. */
function u2init(){
const $ = id => document.getElementById(id);
const ULTRA = /splat\.html/.test(location.pathname);
const ic = {
  views:'<svg viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  floors:'<svg viewBox="0 0 24 24"><path d="M12 3 2 8l10 5 10-5-10-5z"/><path d="m2 13 10 5 10-5"/><path d="m2 18 10 5 10-5" opacity=".5"/></svg>',
  door:'<svg viewBox="0 0 24 24"><path d="M5 21V4a1 1 0 0 1 1-1h9l4 3v15"/><path d="M3 21h18"/><circle cx="13.5" cy="12.5" r=".6" fill="currentColor"/></svg>',
  ultra:'<svg viewBox="0 0 24 24"><path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="m3 7 9 5 9-5M12 12v10"/></svg>',
  film:'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/></svg>',
  car:'<svg class="car" viewBox="0 0 10 10"><path d="M2 6.5 5 3.5l3 3"/></svg>',
  img:'<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/></svg>',
  pin:'<svg viewBox="0 0 24 24"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  heart:'<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
  play:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m10 8.5 5 3.5-5 3.5z"/></svg>',
  share:'<svg viewBox="0 0 24 24"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="m16 6-4-4-4 4M12 2v13"/></svg>',
  avail:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>'
};
const click = id => { const e = $(id); if (e) e.click(); };
const isOn = id => { const e = $(id); return !!e && e.classList.contains("on"); };

/* ---------- header: brand · Enquire · menu ---------- */
const hb = document.querySelector(".hbtns");
const mb = document.createElement("button"); mb.id = "u2menuBtn"; mb.title = "Menu"; mb.innerHTML = '<i></i><span class="dot"></span>'; hb.appendChild(mb);

/* ---------- dock ---------- */
const dock = document.createElement("div"); dock.id = "u2dock";
dock.innerHTML = `<button data-p="u2views">${ic.views}<span>Views</span>${ic.car}</button>
<button data-p="u2floors">${ic.floors}<span>Floors</span>${ic.car}</button>
<button id="u2inside">${ic.door}<span>Step inside</span></button>
<button id="u2ultra" class="ultra">${ULTRA ? ic.film : ic.ultra}<span class="lg">${ULTRA ? "Cinematic views" : "Ultra Experience"}</span><span class="sh">${ULTRA ? "Cinematic" : "Ultra 3D"}</span></button>`;
document.body.appendChild(dock);
$("u2inside").onclick = () => { closeAll(); click("tourBtn"); };
$("u2ultra").onclick = () => { closeAll(); click(ULTRA ? "renderBtn" : "splatBtn"); };
$("u2ultra").title = ULTRA ? "Back to the cinematic rendered views" : "Ultra Experience: fly freely around the tower in real-time 3D";

/* ---------- popovers ---------- */
const pops = {};
function pop(id, html){ const p = document.createElement("div"); p.className = "u2pop"; p.id = id; p.innerHTML = html; document.body.appendChild(p); pops[id] = p; return p; }
let openId = null;
function place(p, anchor){ if (innerWidth <= 760) return;
  const r = anchor.getBoundingClientRect(), w = p.offsetWidth;
  p.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width/2 - w/2)) + "px"; p.style.bottom = (innerHeight - r.top + 10) + "px"; p.style.top = "auto"; }
function openPop(id, anchor){ if (openId === id){ closeAll(); return; } closeAll(); const p = pops[id]; refresh[id] && refresh[id]();
  p.classList.add("on"); openId = id; if (anchor){ anchor.classList.add("on"); if (id !== "u2menu") place(p, anchor); } }
function closeAll(){ for (const k in pops) pops[k].classList.remove("on"); dock.querySelectorAll("[data-p]").forEach(b => b.classList.remove("on")); mb.classList.remove("on"); openId = null; }
dock.querySelectorAll("[data-p]").forEach(b => b.onclick = e => { e.stopPropagation(); openPop(b.dataset.p, b); });
mb.onclick = e => { e.stopPropagation(); openPop("u2menu", mb); };
document.addEventListener("pointerdown", e => { if (!openId) return; if (e.target.closest(".u2pop,#u2dock,#u2menuBtn")) return; closeAll(); }, true);
addEventListener("keydown", e => { if (e.key === "Escape" && openId) closeAll(); });
const refresh = {};

/* Views */
const vp = pop("u2views", "");
if (!ULTRA){
  vp.innerHTML = `<h6>Height</h6><div class="seg" id="u2h"><button data-h="h">High</button><button data-h="m">Mid</button><button data-h="g">Street</button></div>
  <h6>Distance</h6><div class="seg" id="u2d"><button data-d="1">Near</button><button data-d="2">Mid</button><button data-d="3">Far</button></div>
  <h6>Light</h6><div class="seg" id="u2l"><button data-l="modeDay">Golden hour</button><button data-l="modeDusk">Dusk</button></div>`;
  const cur = () => { const b = document.querySelector("#pad button.on"); return b ? b.dataset.k : "g2"; };
  const go = k => { const b = document.querySelector(`#pad button[data-k="${k}"]`); if (b && !b.disabled) b.click(); setTimeout(refresh.u2views, 700); };
  vp.querySelectorAll("[data-h]").forEach(b => b.onclick = () => go(b.dataset.h + cur()[1]));
  vp.querySelectorAll("[data-d]").forEach(b => b.onclick = () => go(cur()[0] + b.dataset.d));
  vp.querySelectorAll("[data-l]").forEach(b => b.onclick = () => { click(b.dataset.l); setTimeout(refresh.u2views, 900); });
  refresh.u2views = () => { const k = cur();
    vp.querySelectorAll("[data-h]").forEach(b => b.classList.toggle("on", b.dataset.h === k[0]));
    vp.querySelectorAll("[data-d]").forEach(b => b.classList.toggle("on", b.dataset.d === k[1]));
    vp.querySelectorAll("[data-l]").forEach(b => b.classList.toggle("on", isOn(b.dataset.l))); };
} else {
  const vs = [...document.querySelectorAll("#views button")];
  vp.innerHTML = `<h6>Fly to</h6><div class="chips" id="u2vs" style="grid-template-columns:repeat(2,1fr)"></div>`;
  const g = vp.querySelector("#u2vs");
  vs.forEach(b => { const c = document.createElement("button"); c.textContent = b.textContent; c.onclick = () => { b.click(); closeAll(); }; g.appendChild(c); });
}

/* Floors */
const fp = pop("u2floors", `<button class="row" id="u2exp">${ic.floors}<span>Explode floors</span><i class="sw"></i></button><hr>
<div id="u2fl"></div>`);
const railBtn = n => [...document.querySelectorAll("#rail button")].find(b => b.textContent.trim() === n);
const FL = [["PH","Sky Penthouses"],null,["2","Club & Amenities"],["1","Retail & Dining"],["G","Grand Lobby"]];
const fl = fp.querySelector("#u2fl");
const row = (n, t) => { const b = document.createElement("button"); b.className = "flr"; b.dataset.n = n; b.innerHTML = `<b>${n}</b><span>${t}</span>`; return b; };
for (const f of FL){
  if (f){ fl.appendChild(row(f[0], f[1])); continue; }
  const h = document.createElement("h6"); h.textContent = "Residences"; h.style.margin = "10px 10px 6px"; fl.appendChild(h);
  const c = document.createElement("div"); c.className = "chips"; c.style.margin = "0 4px 8px";
  for (let n = 13; n >= 3; n--){ const b = document.createElement("button"); b.textContent = n; b.dataset.n = n; c.appendChild(b); }
  fl.appendChild(c);
}
fl.querySelectorAll("[data-n]").forEach(b => {
  b.onmouseenter = () => { const r = railBtn(b.dataset.n); r && r.onmouseenter && r.onmouseenter(); };
  b.onmouseleave = () => { const r = railBtn(b.dataset.n); r && r.onmouseleave && r.onmouseleave(); };
  b.onclick = () => { const r = railBtn(b.dataset.n); closeAll(); r && r.click(); };
});
$("u2exp").onclick = () => { click("explodeBtn"); closeAll(); };
refresh.u2floors = () => { $("u2exp").classList.toggle("on", isOn("explodeBtn"));
  const sel = document.querySelector("#rail button.sel"); const n = sel ? sel.textContent.trim() : null;
  fl.querySelectorAll("[data-n]").forEach(b => b.classList.toggle("on", b.dataset.n === n)); };

/* Menu */
const mp = pop("u2menu", `
<button class="row" data-tab="gallery">${ic.img}<span>Gallery</span></button>
<button class="row" data-tab="location">${ic.pin}<span>Location</span></button>
<hr>
<button class="row" id="u2av">${ic.avail}<span>Availability</span><i class="sw"></i></button>
<button class="row" id="u2list">${ic.heart}<span>Shortlist</span><em id="u2n">0</em></button>
<hr>
<button class="row" id="u2pres">${ic.play}<span>Guided presentation</span></button>
<button class="row" id="u2share">${ic.share}<span>Share this view</span></button>`);
mp.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => { closeAll(); const t = document.querySelector(`#tabs [data-tab="${b.dataset.tab}"]`); t && t.click(); });
$("u2av").onclick = () => { click("availBtn"); setTimeout(refresh.u2menu, 50); };
$("u2list").onclick = () => { closeAll(); click("listBtn"); };
$("u2pres").onclick = () => { closeAll(); click("presBtn"); };
$("u2share").onclick = () => { closeAll(); click("shareBtn"); };
refresh.u2menu = () => { $("u2av").classList.toggle("on", isOn("availBtn")); const n = ($("listN") || {}).textContent || "0"; $("u2n").textContent = n; };
/* a small gold dot on the menu when something is shortlisted */
const ln = $("listN"); if (ln) new MutationObserver(() => mb.querySelector(".dot").classList.toggle("on", +ln.textContent > 0)).observe(ln, {childList:true, characterData:true, subtree:true});
/* closing a modal or the sheet never leaves a stale popover behind */
addEventListener("hashchange", closeAll);
}
(function wait(){ if (document.querySelector('#rail button') && document.querySelector('.hbtns')) u2init(); else setTimeout(wait, 60); })();
