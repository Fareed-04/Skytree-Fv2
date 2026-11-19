/* Sky Tree Tower — neighbourhood map (Navigo-style).
   Satellite base, 1/3/5 km rings, category toggles with live OpenStreetMap places (Overpass), key city destinations
   with drive-time estimates, place search and a nearby list. Loaded on demand from index.html. */
(function () {
  "use strict";
  // Indicative plot pin. Override with ?pin=31.40,74.21 or by editing SITE.
  const SITE = { lat: 31.3793117, lon: 74.2543937, name: "Sky Tree Tower", addr: "Pine Avenue, Lahore" };
  const q = new URLSearchParams(location.search).get("pin");
  if (q && /^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(q)) { const [a, b] = q.split(",").map(Number); SITE.lat = a; SITE.lon = b; }
  const RADIUS = 5000;
  const ICON = {
    dining: '<path d="M7 2v9a3 3 0 0 0 2 2.8V22h2v-8.2A3 3 0 0 0 13 11V2h-1.5v7h-1V2H9v7H8V2zm9 0c-1.7 0-3 2-3 5v6h2v9h2V2z"/>',
    shopping: '<path d="M6 7V6a6 6 0 0 1 12 0v1h3l-1 15H4L3 7zm2 0h8V6a4 4 0 0 0-8 0z"/>',
    leisure: '<path d="M12 2a5 5 0 0 1 5 5c0 2.4-1.7 4.4-4 4.9V15h5v2h-5v5h-2v-5H6v-2h5v-3.1A5 5 0 0 1 12 2z"/>',
    education: '<path d="M12 3 1 9l11 6 9-4.9V17h2V9zM5 13.2V17l7 4 7-4v-3.8L12 17z"/>',
    health: '<path d="M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z"/>',
    transport: '<path d="M6 2h12a3 3 0 0 1 3 3v11a3 3 0 0 1-2 2.8V21h-3v-2H8v2H5v-2.2A3 3 0 0 1 3 16V5a3 3 0 0 1 3-3zm0 3v6h12V5zm1.5 8a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm9 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>',
    worship: '<path d="M12 2c2 2 4 3.5 4 6v1h3v13h-5v-5a2 2 0 0 0-4 0v5H5V9h3V8c0-2.5 2-4 4-6z"/>',
    landmarks: '<path d="M12 2 4 6v2h16V6zM5 10v8h2v-8zm4 0v8h2v-8zm4 0v8h2v-8zm4 0v8h2v-8zM3 20v2h18v-2z"/>',
  };
  const CATS = [
    { id: "landmarks", t: "Key places", c: "#d9b46a" },
    { id: "dining", t: "Restaurants", c: "#ff8a5c" },
    { id: "shopping", t: "Shopping", c: "#ec6fa8" },
    { id: "leisure", t: "Entertainment", c: "#8f7bff" },
    { id: "transport", t: "Transport", c: "#4fb6ff" },
    { id: "education", t: "Education", c: "#ffd34e" },
    { id: "health", t: "Healthcare", c: "#5fd68f" },
    { id: "worship", t: "Mosques", c: "#b7c4cf" },
  ];
  // Major Lahore destinations (city scale; positions approximate) — always available, even offline.
  const LANDMARKS = [
    { n: "Allama Iqbal International Airport", lat: 31.5216, lon: 74.4036, k: "Airport" },
    { n: "Emporium Mall, Johar Town", lat: 31.4669, lon: 74.2652, k: "Shopping mall" },
    { n: "Packages Mall", lat: 31.4710, lon: 74.3556, k: "Shopping mall" },
    { n: "Shaukat Khanum Memorial Hospital", lat: 31.4458, lon: 74.2669, k: "Hospital" },
    { n: "LUMS University", lat: 31.4707, lon: 74.4111, k: "University" },
    { n: "Gaddafi Stadium", lat: 31.5134, lon: 74.3330, k: "Stadium" },
    { n: "Bahria Town Lahore", lat: 31.3685, lon: 74.1850, k: "Community" },
  ];
  const QUERY = {
    dining: '["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]',
    shopping: ['["shop"~"^(mall|supermarket|department_store|bakery|clothes|electronics)$"]', '["amenity"="marketplace"]'],
    leisure: ['["leisure"~"^(park|sports_centre|stadium|golf_course|water_park|amusement_arcade|fitness_centre)$"]', '["amenity"~"^(cinema|theatre|events_venue)$"]', '["tourism"~"^(theme_park|zoo|attraction)$"]'],
    education: '["amenity"~"^(school|college|university|kindergarten)$"]',
    health: ['["amenity"~"^(hospital|clinic|pharmacy|doctors)$"]'],
    transport: ['["highway"="bus_stop"]', '["public_transport"="station"]', '["railway"~"^(station|halt)$"]', '["amenity"~"^(fuel|bus_station)$"]'],
    worship: '["amenity"="place_of_worship"]',
  };
  const MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"];

  const toRad = d => d * Math.PI / 180;
  function km(a, b) { const R = 6371, dLa = toRad(b.lat - a.lat), dLo = toRad(b.lon - a.lon);
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); }
  function eta(d) { const road = d * 1.32; const speed = road < 3 ? 22 : road < 12 ? 32 : 42; return Math.max(1, Math.round(road / speed * 60)); }
  function fmt(d) { return d < 1 ? `${Math.round(d * 1000)} m` : `${d.toFixed(d < 10 ? 1 : 0)} km`; }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let map, layers = {}, data = {}, on = new Set(["landmarks", "dining", "shopping", "leisure"]), routeLine = null, ui = {};

  function svgIcon(cat, size) { const c = CATS.find(x => x.id === cat);
    return L.divIcon({ className: "nb-pin", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<span style="--c:${c.c}"><svg viewBox="0 0 24 24">${ICON[cat]}</svg></span>` }); }

  function build(host) {
    host.innerHTML = `
      <div class="nb">
        <div id="nbMap"></div>
        <div class="nb-card"><img src="media/stills/s/front_dusk.webp" alt=""><div><small>Pine Avenue · Lahore</small><b>Sky Tree Tower</b><span id="nbStat">Loading nearby places…</span></div></div>
        <form class="nb-search" id="nbSearch"><input id="nbQ" placeholder="Search a place in Lahore…" autocomplete="off"><button aria-label="Search"><svg viewBox="0 0 24 24"><path d="M10 3a7 7 0 0 1 5.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1 1 10 3zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10z"/></svg></button></form>
        <div class="nb-tools"><button id="nbBase" title="Map style">Map</button><button id="nbHome" title="Re-centre">◎</button></div>
        <aside class="nb-list" id="nbList"><h5>Nearby</h5><div id="nbItems"></div></aside>
        <nav class="nb-dock" id="nbDock"></nav>
      </div>`;
    ui = { stat: host.querySelector("#nbStat"), items: host.querySelector("#nbItems"), dock: host.querySelector("#nbDock") };
    map = L.map("nbMap", { zoomControl: false, attributionControl: true, preferCanvas: true }).setView([SITE.lat, SITE.lon], 13);
    const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" });
    const lab = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, opacity: .9 });
    const roads = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, opacity: .55 });
    const dark = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 20, subdomains: "abcd", attribution: "© OpenStreetMap, © CARTO" });
    let satOn = true; sat.addTo(map); roads.addTo(map); lab.addTo(map);
    host.querySelector("#nbBase").onclick = e => { satOn = !satOn;
      [sat, roads, lab].forEach(l => satOn ? l.addTo(map) : map.removeLayer(l)); satOn ? map.removeLayer(dark) : dark.addTo(map);
      e.currentTarget.textContent = satOn ? "Map" : "Satellite"; };
    host.querySelector("#nbHome").onclick = () => map.flyTo([SITE.lat, SITE.lon], 14, { duration: 1.2 });

    // rings
    [1, 3, 5].forEach(r => {
      L.circle([SITE.lat, SITE.lon], { radius: r * 1000, color: "#f4ecdc", weight: 1.4, opacity: .75, fill: r === 1, fillColor: "#d9b46a", fillOpacity: .06, interactive: false }).addTo(map);
      const top = [SITE.lat + r / 111.2, SITE.lon];
      L.marker(top, { interactive: false, icon: L.divIcon({ className: "nb-ring", iconSize: [64, 26], iconAnchor: [32, 13], html: `<span>${r} KM</span>` }) }).addTo(map);
    });
    // the tower
    L.marker([SITE.lat, SITE.lon], { zIndexOffset: 1000, icon: L.divIcon({ className: "nb-site", iconSize: [54, 66], iconAnchor: [27, 62],
      html: `<div class="pulse"></div><svg viewBox="0 0 54 66"><path d="M27 64C27 64 4 40 4 25a23 23 0 0 1 46 0c0 15-23 39-23 39z" fill="#d9b46a" stroke="#1a1408" stroke-width="2"/><path d="M20 36V18l7-5 7 5v18zM24 22h2v3h-2zm4 0h2v3h-2zm-4 6h2v3h-2zm4 0h2v3h-2z" fill="#1a1408"/></svg>` }) })
      .addTo(map).bindTooltip(`<b>${SITE.name}</b><br>${SITE.addr}`, { direction: "top", offset: [0, -58], className: "nb-tt" });

    // dock
    CATS.forEach(c => { const b = document.createElement("button"); b.dataset.c = c.id; b.style.setProperty("--c", c.c);
      b.innerHTML = `<svg viewBox="0 0 24 24">${ICON[c.id]}</svg><span>${c.t}</span><em></em>`; b.classList.toggle("on", on.has(c.id));
      b.onclick = () => { on.has(c.id) ? on.delete(c.id) : on.add(c.id); b.classList.toggle("on", on.has(c.id)); refresh(); };
      ui.dock.appendChild(b); });

    // search (Nominatim, biased to Lahore)
    host.querySelector("#nbSearch").onsubmit = async e => { e.preventDefault(); const s = host.querySelector("#nbQ").value.trim(); if (!s) return;
      try { const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&viewbox=74.0,31.7,74.6,31.2&bounded=1&q=${encodeURIComponent(s)}`);
        const j = await r.json(); if (!j.length) { ui.stat.textContent = "No match found in Lahore"; return; }
        showRoute({ n: j[0].display_name.split(",")[0], lat: +j[0].lat, lon: +j[0].lon, cat: "landmarks", k: "Search result" }, true);
      } catch (_) { ui.stat.textContent = "Search unavailable offline"; } };

    data.landmarks = LANDMARKS.map(p => ({ ...p, cat: "landmarks", d: km(SITE, p) }));
    refresh(); loadLive();
    setTimeout(() => map.invalidateSize(), 60);
  }

  function showRoute(p, add) {
    if (routeLine) map.removeLayer(routeLine);
    const d = km(SITE, p);
    routeLine = L.polyline([[SITE.lat, SITE.lon], [p.lat, p.lon]], { color: "#d9b46a", weight: 3, dashArray: "6 8", opacity: .95 }).addTo(map);
    const m = add ? L.marker([p.lat, p.lon], { icon: svgIcon(p.cat, 30) }).addTo(map) : null;
    L.popup({ className: "nb-pop", offset: [0, -8], closeButton: false })
      .setLatLng([p.lat, p.lon]).setContent(`<b>${esc(p.n)}</b><small>${esc(p.k || "")}</small><span>${fmt(d)} · ~${eta(d)} min drive</span>`).openOn(map);
    map.flyToBounds(L.latLngBounds([[SITE.lat, SITE.lon], [p.lat, p.lon]]).pad(0.35), { duration: 1.1, maxZoom: 16 });
    if (m) setTimeout(() => map.once("click", () => map.removeLayer(m)), 400);
  }

  function refresh() {
    Object.values(layers).forEach(l => map.removeLayer(l)); layers = {};
    let all = [];
    CATS.forEach(c => {
      const list = (data[c.id] || []).slice().sort((a, b) => a.d - b.d).slice(0, c.id === "landmarks" ? 20 : 45);
      const btn = ui.dock.querySelector(`[data-c="${c.id}"] em`); if (btn) btn.textContent = data[c.id] ? (data[c.id].length > 99 ? "99+" : data[c.id].length) : "";
      if (!on.has(c.id)) return;
      const g = L.layerGroup();
      list.forEach(p => L.marker([p.lat, p.lon], { icon: svgIcon(c.id, c.id === "landmarks" ? 30 : 24) }).on("click", () => showRoute(p))
        .bindTooltip(esc(p.n), { direction: "top", offset: [0, -12], className: "nb-tt" }).addTo(g));
      g.addTo(map); layers[c.id] = g; all = all.concat(list);
    });
    all.sort((a, b) => a.d - b.d);
    ui.items.innerHTML = all.slice(0, 60).map((p, i) => { const c = CATS.find(x => x.id === p.cat);
      return `<button data-i="${i}" style="--c:${c.c}"><i><svg viewBox="0 0 24 24">${ICON[p.cat]}</svg></i><span><b>${esc(p.n)}</b><small>${esc(p.k || c.t)}</small></span><em>${fmt(p.d)}<small>${eta(p.d)} min</small></em></button>`; }).join("")
      || `<p class="nb-empty">Turn on a category below to see what's nearby.</p>`;
    ui.items.querySelectorAll("button").forEach(b => b.onclick = () => showRoute(all[+b.dataset.i]));
  }

  function kindOf(t) { return (t.amenity || t.shop || t.leisure || t.tourism || t.railway || (t.highway === "bus_stop" ? "bus stop" : "") || t.public_transport || "").replace(/_/g, " "); }

  async function loadLive() {
    const key = `nb:${SITE.lat.toFixed(4)},${SITE.lon.toFixed(4)}`;
    try { const c = JSON.parse(localStorage.getItem(key) || "null"); if (c && Date.now() - c.t < 7 * 864e5) { apply(c.d); return; } } catch (_) {}
    const parts = []; Object.entries(QUERY).forEach(([cat, f]) => [].concat(f).forEach(sel => parts.push(`nwr${sel}["name"](around:${RADIUS},${SITE.lat},${SITE.lon});`)));
    const body = "data=" + encodeURIComponent(`[out:json][timeout:25];(${parts.join("")});out center tags 900;`);
    for (const url of MIRRORS) {
      try {
        const ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 20000);
        const r = await fetch(url, { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" }, signal: ctl.signal });
        clearTimeout(to); if (!r.ok) continue;
        const j = await r.json(); const d = {};
        j.elements.forEach(e => { const t = e.tags || {}, lat = e.lat ?? e.center?.lat, lon = e.lon ?? e.center?.lon; if (lat == null || !t.name) return;
          for (const [cat, f] of Object.entries(QUERY)) {
            if ([].concat(f).some(sel => [...sel.matchAll(/\["(\w+)"(=|~)"([^"]+)"\]/g)].every(([, k, op, v]) => op === "=" ? t[k] === v : new RegExp(v).test(t[k] || "")))) {
              (d[cat] = d[cat] || []).push({ n: t["name:en"] || t.name, lat, lon, k: kindOf(t) }); break; } } });
        try { localStorage.setItem(key, JSON.stringify({ t: Date.now(), d })); } catch (_) {}
        apply(d); return;
      } catch (_) { /* try next mirror */ }
    }
    ui.stat.textContent = "Live places unavailable — showing key destinations";
  }
  function apply(d) {
    let n = 0;
    Object.entries(d).forEach(([cat, list]) => { const seen = new Set();
      data[cat] = list.filter(p => { const k = p.n.toLowerCase() + Math.round(p.lat * 2000) + Math.round(p.lon * 2000); if (seen.has(k)) return false; seen.add(k); return true; })
        .map(p => ({ ...p, cat, d: km(SITE, p) })); n += data[cat].length; });
    ui.stat.textContent = `${n} places within ${RADIUS / 1000} km`;
    refresh();
  }

  window.SkyTreeMap = { open(host) { if (map) { setTimeout(() => map.invalidateSize(), 60); return; } build(host); } };
})();
