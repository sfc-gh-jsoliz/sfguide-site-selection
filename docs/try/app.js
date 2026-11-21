/* Geographic Expansion & Site Selection: hosted no-account example (Sample mode only).
   Renders the same five screens as app/streamlit_app.py from data/*.json, which
   scripts/capture_sample.py captured from a Live run. No external scripts. */
(function () {
  "use strict";
  var C = { i950: "#1C1A4A", i800: "#2E2A78", i600: "#4F46C8", i300: "#B7B4F0", apr: "#F29A4A", aprInk: "#A44A12", line: "#DCDEEA", muted: "#565873", ink: "#16163A" };
  var REG = { Northeast: "#4F46C8", West: "#0E7C86", South: "#B34F12", Midwest: "#7A6A1F" };
  var CATS = { "Restaurants & Food Service": "Restaurants", "Clothing & Accessories": "Apparel", "Electronics & Appliances": "Electronics", "Food & Beverage Stores": "Grocery", "Furniture & Home Furnishings": "Furniture", "Health & Personal Care": "Health" };
  var CATC = { Grocery: "#2E2A78", Restaurants: "#4F46C8", Health: "#0E7C86", Apparel: "#B34F12", Electronics: "#7A6A1F", Furniture: "#8A8CA6" };
  var HEAT = [[238, 240, 251], [183, 180, 240], [106, 95, 216], [46, 42, 120]];
  var SCOPES = { national: "National shortlist: top 12 cells by opportunity score", sunbelt: "South and West: top 8 cells in the two leading regions" };
  var QUESTIONS = ["Which metro and category pairs have the highest white-space opportunity?", "Which metros have the most white-space dollars in total, and how covered are they?", "Compare average penetration and opportunity score by region."];
  var HEDGE = "Houston grocery will likely double its coverage next year and could add around $500M in processed volume.";
  var STATUS = { "Top target": "target", "Saturated": "sat", "No demand growth": "flat", "Watch": "watch" };
  var cache = {}, state = { note: null, rv: null, chat: [], f: null };
  var view = document.getElementById("view"), tip = document.getElementById("tip");
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function load(k) {
    if (!cache[k]) cache[k] = fetch("data/" + k + ".json").then(function (r) { if (!r.ok) throw new Error(k + ": HTTP " + r.status); return r.json(); });
    return cache[k];
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function usd(v) { v = +v || 0; return Math.abs(v) >= 1e9 ? "$" + (v / 1e9).toFixed(2) + "B" : Math.abs(v) >= 1e6 ? "$" + Math.round(v / 1e6) + "M" : "$" + Math.round(v).toLocaleString("en-US"); }
  function pct(v) { return v == null || isNaN(v) ? "n/d" : (v * 100).toFixed(1) + "%"; }
  function num(v) { return Math.round(v).toLocaleString("en-US"); }
  function sum(a, f) { return a.reduce(function (s, x) { return s + (+f(x) || 0); }, 0); }
  function group(a, f) { var m = {}; a.forEach(function (x) { var k = f(x); (m[k] = m[k] || []).push(x); }); return m; }
  function pill(t, k) { return '<span class="pill p-' + k + '">' + esc(t) + "</span>"; }
  function powered(t) { return '<div class="powered"><i></i>' + esc(t) + "</div>"; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function jitter(a, b) { return a + Math.random() * (b - a); }
  function mlong(d) { var p = d.split("-"); return MON[+p[1] - 1] + " " + p[0]; }
  function mlabel(d) { var p = d.split("-"); return MON[+p[1] - 1] + " " + p[0].slice(2); }
  function kpi(l, v, n) { return '<div class="kpi"><div class="kl">' + esc(l) + '</div><div class="kv" data-count="' + esc(v) + '">' + esc(v) + '</div><div class="kn">' + esc(n) + "</div></div>"; }
  function animateCounts() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    view.querySelectorAll("[data-count]").forEach(function (el) {
      var txt = el.getAttribute("data-count"), m = txt.match(/^(\D*)([\d,.]+)(\D*)$/);
      if (!m) return;
      var target = parseFloat(m[2].replace(/,/g, "")), dec = (m[2].split(".")[1] || "").length, t0 = performance.now();
      (function step(t) {
        var k = Math.min(1, (t - t0) / 900), e = 1 - Math.pow(1 - k, 3);
        el.textContent = m[1] + (target * e).toFixed(dec) + m[3];
        if (k < 1) requestAnimationFrame(step); else el.textContent = txt;
      })(t0);
    });
  }
  function showTip(e, h) { tip.innerHTML = h; tip.hidden = false; tip.style.left = Math.min(e.clientX + 12, innerWidth - 250) + "px"; tip.style.top = (e.clientY + 14) + "px"; }
  function hideTip() { tip.hidden = true; }
  function bindTips(root) {
    root.querySelectorAll("[data-tip]").forEach(function (el) {
      el.addEventListener("mousemove", function (e) { showTip(e, el.getAttribute("data-tip")); });
      el.addEventListener("mouseleave", hideTip);
      el.addEventListener("click", function (e) { showTip(e, el.getAttribute("data-tip")); });
    });
  }
  function md(s) {
    s = esc(s);
    var lines = s.split("\n"), out = [], i = 0;
    function inline(t) { return t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\[(F\d+(?:\s*,\s*F\d+)*)\]/g, function (_, ids) { return ids.split(/\s*,\s*/).map(function (x) { return '<span class="cite">' + x + "</span>"; }).join(""); }); }
    while (i < lines.length) {
      var l = lines[i];
      if (/^\|/.test(l)) {
        var rows = []; while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
        var cells = rows.filter(function (r) { return !/^\|[\s:|-]+\|?$/.test(r); }).map(function (r) { return r.replace(/^\||\|$/g, "").split("|"); });
        out.push('<div class="scroll"><table>' + cells.map(function (c, j) { return "<tr>" + c.map(function (x) { return (j ? "<td>" : "<th>") + inline(x.trim()) + (j ? "</td>" : "</th>"); }).join("") + "</tr>"; }).join("") + "</table></div>");
        continue;
      }
      if (/^[-*] /.test(l)) { var it = []; while (i < lines.length && /^[-*] /.test(lines[i])) { it.push("<li>" + inline(lines[i].slice(2)) + "</li>"); i++; } out.push("<ul>" + it.join("") + "</ul>"); continue; }
      var h = l.match(/^(#{1,3}) (.*)$/);
      if (h) out.push("<h" + h[1].length + ">" + inline(h[2]) + "</h" + h[1].length + ">");
      else if (l.trim()) out.push("<p>" + inline(l) + "</p>");
      i++;
    }
    return out.join("");
  }

  /* ---------- data shaping (mirrors the Streamlit app) ---------- */
  function cells(raw) {
    var rows = raw.map(function (r) {
      return { metro_id: r.metro_id, metro: r.metro_name, region: r.region, catName: r.category_name, cat: CATS[r.category_name], ws: r.total_white_space_usd, market: r.total_market_usd,
        processed: r.total_processed_usd, merchants: r.total_merchants, pen: r.weighted_penetration, score: r.max_opportunity_score, growth: r.avg_demand_growth_pct };
    }).sort(function (a, b) { return b.score - a.score || b.ws - a.ws; });
    rows.forEach(function (r, i) {
      r.rank = i + 1;
      r.status = r.growth <= 0 ? "No demand growth" : r.pen >= 0.30 ? "Saturated" : r.rank <= 5 ? "Top target" : "Watch";
      r._key = r.metro_id + "|" + r.cat;
    });
    return rows;
  }
  function heatColor(v, max) {
    var k = Math.max(0, Math.min(1, v / max)) * 3, i = Math.min(2, Math.floor(k)), f = k - i, a = HEAT[i], b = HEAT[i + 1];
    return "rgb(" + a.map(function (x, j) { return Math.round(x + (b[j] - x) * f); }).join(",") + ")";
  }

  /* ---------- SVG charts ---------- */
  function heatmap(cs) {
    var catOrder = ["Grocery", "Restaurants", "Apparel", "Health", "Electronics", "Furniture"];
    var mb = group(cs, function (r) { return r.metro; });
    var metros = Object.keys(mb).sort(function (a, b) { return Math.max.apply(null, mb[b].map(function (r) { return r.score; })) - Math.max.apply(null, mb[a].map(function (r) { return r.score; })); });
    var W = 760, L = 120, T = 26, cw = (W - L) / 6, ch = 30, H = T + metros.length * ch + 4, max = Math.max.apply(null, cs.map(function (r) { return r.score; }));
    var s = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Heat map of opportunity score by metro and merchant category">';
    catOrder.forEach(function (c, i) { s += '<text x="' + (L + i * cw + cw / 2) + '" y="16" text-anchor="middle">' + c + "</text>"; });
    metros.forEach(function (m, j) {
      s += '<text x="' + (L - 8) + '" y="' + (T + j * ch + 19) + '" text-anchor="end" style="fill:' + C.ink + '">' + esc(m) + "</text>";
      catOrder.forEach(function (c, i) {
        var r = mb[m].filter(function (x) { return x.cat === c; })[0]; if (!r) return;
        s += '<rect data-tip="' + esc("<b>" + r.metro + " · " + r.catName + "</b><br>Score " + r.score.toFixed(2) + " (rank " + r.rank + ")<br>Penetration " + pct(r.pen) + "<br>Growth " + r.growth.toFixed(2) + "%<br>White space " + usd(r.ws)) + '" x="' + (L + i * cw + 1.5) + '" y="' + (T + j * ch + 1.5) + '" width="' + (cw - 3) + '" height="' + (ch - 3) + '" rx="4" fill="' + heatColor(r.score, max) + '"/>';
        s += '<text x="' + (L + i * cw + cw / 2) + '" y="' + (T + j * ch + 19) + '" text-anchor="middle" style="pointer-events:none;font-weight:600;fill:' + (r.score > 6 ? "#fff" : C.ink) + '">' + r.score.toFixed(1) + "</text>";
      });
    });
    return s + "</svg>";
  }
  function demandChart(dm) {
    var by = group(dm, function (r) { return CATS[r.category_name]; }), cats = Object.keys(CATC);
    var months = by.Grocery.map(function (r) { return r.month_end; }), n = months.length;
    var W = 760, H = 250, L = 40, R = 12, T = 12, B = 28, idx = {}, lo = 1e9, hi = 0;
    cats.forEach(function (c) { var f = by[c][0].market_sales_usd; idx[c] = by[c].map(function (r) { var v = r.market_sales_usd / f * 100; lo = Math.min(lo, v); hi = Math.max(hi, v); return v; }); });
    lo = Math.floor(lo) - 1; hi = Math.ceil(hi) + 1;
    function x(i) { return L + (W - L - R) * i / (n - 1); } function y(v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); }
    var s = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Category demand index over 24 months, one line per category, November and December shaded">';
    months.forEach(function (m, i) { var mo = +m.split("-")[1]; if (mo === 11 || mo === 12) s += '<rect x="' + (x(i) - (W - L - R) / (n - 1) / 2) + '" y="' + T + '" width="' + (W - L - R) / (n - 1) + '" height="' + (H - T - B) + '" fill="#FDEBDD" opacity=".7"/>'; });
    [0, .25, .5, .75, 1].forEach(function (k) { var v = lo + (hi - lo) * k; s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="' + C.line + '"/><text x="' + (L - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + Math.round(v) + "</text>"; });
    cats.forEach(function (c) { s += '<path d="M' + idx[c].map(function (v, i) { return x(i) + "," + y(v); }).join("L") + '" fill="none" stroke="' + CATC[c] + '" stroke-width="2.2"/>'; });
    months.forEach(function (m, i) {
      var t = "<b>" + mlong(m) + "</b><br>" + cats.map(function (c) { return c + ": " + idx[c][i].toFixed(1); }).join("<br>");
      s += '<rect data-tip="' + esc(t) + '" x="' + (x(i) - (W - L - R) / (n - 1) / 2) + '" y="' + T + '" width="' + (W - L - R) / (n - 1) + '" height="' + (H - T - B) + '" fill="transparent"/>';
      if (i % 3 === 0) s += '<text x="' + x(i) + '" y="' + (H - 8) + '" text-anchor="middle">' + mlabel(m) + "</text>";
    });
    return '<div class="legend">' + cats.map(function (c) { return '<span><b style="background:' + CATC[c] + '"></b>' + c + "</span>"; }).join("") + "</div>" + s + "</svg>";
  }
  function mapChart(cs, metros, dots, only) {
    var W = 900, H = 470, x0 = -125, x1 = -66.5, y0 = 24.3, y1 = 49.5;
    function x(lon) { return 20 + (W - 40) * (lon - x0) / (x1 - x0); } function y(lat) { return 10 + (H - 20) * (1 - (lat - y0) / (y1 - y0)); }
    var bm = group(cs, function (r) { return r.metro_id; }), maxWs = 0;
    var ms = metros.map(function (m) { var rs = bm[m.metro_id], best = rs.slice().sort(function (a, b) { return a.rank - b.rank; })[0]; var ws = sum(rs, function (r) { return r.ws; }); maxWs = Math.max(maxWs, ws); return { m: m, ws: ws, best: best }; });
    var s = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Dot map of the contiguous US with ten metros sized by white-space dollars and colored by region; apricot rings mark metros holding a top-5 cell">';
    dots.forEach(function (d) { s += '<circle cx="' + x(d[0]).toFixed(1) + '" cy="' + y(d[1]).toFixed(1) + '" r="2.6" fill="#CFCDF3"/>'; });
    ms.sort(function (a, b) { return b.ws - a.ws; }).forEach(function (o) {
      var r = 7 + 26 * Math.sqrt(o.ws / maxWs), cx = x(o.m.longitude), cy = y(o.m.latitude), left = o.m.metro_name === "Philadelphia" || o.m.metro_name === "Miami";
      var ring = only ? o.m.metro_id === only : o.best.rank <= 5;
      var t = "<b>" + o.m.metro_name + "</b><br>" + o.m.region + "<br>White space " + usd(o.ws) + "<br>Best: " + o.best.cat + " (#" + o.best.rank + ", score " + o.best.score.toFixed(2) + ")";
      s += '<circle data-tip="' + esc(t) + '" data-metro="' + o.m.metro_id + '" cx="' + cx + '" cy="' + cy + '" r="' + r.toFixed(1) + '" fill="' + REG[o.m.region] + '" fill-opacity=".9" stroke="#fff" stroke-width="1.5" style="cursor:pointer"/>';
      if (ring) s += '<circle cx="' + cx + '" cy="' + cy + '" r="' + (r + 4).toFixed(1) + '" fill="none" stroke="' + C.apr + '" stroke-width="3.5" style="pointer-events:none"/>';
      s += '<text x="' + (cx + (left ? -r - 6 : r + 6)) + '" y="' + (cy + (left ? 14 : -6)) + '" text-anchor="' + (left ? "end" : "start") + '" style="fill:' + C.ink + ';font-weight:600;font-size:12px;pointer-events:none">' + esc(o.m.metro_name) + "</text>";
    });
    return '<div class="legend">' + Object.keys(REG).map(function (k) { return '<span><b style="background:' + REG[k] + '"></b>' + k + "</span>"; }).join("") + '<span><b style="background:none;border:2.5px solid ' + C.apr + '"></b>Holds a top-5 cell</span></div>' + s + "</svg>";
  }
  function scatter(rows) {
    var W = 760, H = 300, L = 46, R = 12, T = 12, B = 34, maxWs = Math.max.apply(null, rows.map(function (r) { return r.ws; }));
    function x(v) { return L + (W - L - R) * v / 0.5; } function y(v) { return T + (H - T - B) * (1 - (v + 0.5) / 11.5); }
    var s = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Scatter of penetration against category demand growth, bubble size is white space, shaded corner marks growing and under-covered cells">';
    s += '<rect x="' + x(0) + '" y="' + y(11) + '" width="' + (x(0.15) - x(0)) + '" height="' + (y(7.5) - y(11)) + '" fill="#FDEBDD" opacity=".7"/><text x="' + (x(0) + 4) + '" y="' + (y(7.5) - 5) + '" style="fill:' + C.aprInk + ';font-weight:700">Growing and under-covered</text>';
    [0, 2, 4, 6, 8, 10].forEach(function (v) { s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="' + C.line + '"/><text x="' + (L - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + v + "%</text>"; });
    [0, .1, .2, .3, .4, .5].forEach(function (v) { s += '<text x="' + x(v) + '" y="' + (H - 16) + '" text-anchor="middle">' + Math.round(v * 100) + "%</text>"; });
    s += '<text x="' + ((W + L) / 2) + '" y="' + (H - 2) + '" text-anchor="middle">Penetration</text>';
    rows.slice().sort(function (a, b) { return b.ws - a.ws; }).forEach(function (r) {
      var t = "<b>" + r.metro + " · " + r.cat + "</b><br>Penetration " + pct(r.pen) + "<br>Growth " + r.growth.toFixed(2) + "%<br>Score " + r.score.toFixed(2) + " (#" + r.rank + ")<br>White space " + usd(r.ws);
      s += '<circle data-tip="' + esc(t) + '" data-cell="' + esc(r._key) + '" cx="' + x(r.pen).toFixed(1) + '" cy="' + y(r.growth).toFixed(1) + '" r="' + (3 + 14 * Math.sqrt(r.ws / maxWs)).toFixed(1) + '" fill="' + REG[r.region] + '" fill-opacity=".82" stroke="#fff" stroke-width="1" style="cursor:pointer"/>';
    });
    return '<div class="legend">' + Object.keys(REG).map(function (k) { return '<span><b style="background:' + REG[k] + '"></b>' + k + "</span>"; }).join("") + "<span>Bubble = white space</span></div>" + s + "</svg>";
  }
  function hbars(rows, valF, labF, colorF, fmt, label) {
    var W = 700, rowH = 28, L = 150, H = rows.length * rowH + 8, max = Math.max.apply(null, rows.map(valF)) || 1;
    var s = '<svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(label) + '">';
    rows.forEach(function (r, i) {
      var w = (W - L - 70) * valF(r) / max, yy = i * rowH + 4;
      s += '<text x="' + (L - 8) + '" y="' + (yy + 15) + '" text-anchor="end" style="fill:' + C.ink + '">' + esc(labF(r)) + "</text>";
      s += '<rect x="' + L + '" y="' + yy + '" width="' + Math.max(w, 1) + '" height="18" rx="4" fill="' + colorF(r) + '"/><text x="' + (L + w + 6) + '" y="' + (yy + 14) + '">' + fmt(valF(r)) + "</text>";
    });
    return s + "</svg>";
  }

  /* ---------- sortable table ---------- */
  function table(cols, rows, onRow) {
    var id = "t" + Math.random().toString(36).slice(2, 8), sortK = null, dir = -1;
    function body() {
      var rs = rows.slice();
      if (sortK) rs.sort(function (a, b) { var p = a[sortK], q = b[sortK]; return (p > q ? 1 : p < q ? -1 : 0) * dir; });
      return rs.map(function (r) { return '<tr tabindex="0" data-k="' + esc(r._key) + '">' + cols.map(function (c) { return '<td class="' + (c.n ? "n" : "") + '">' + c.f(r) + "</td>"; }).join("") + "</tr>"; }).join("");
    }
    setTimeout(function () {
      var t = document.getElementById(id); if (!t) return;
      t.querySelectorAll("th").forEach(function (th, i) {
        th.addEventListener("click", function () {
          var k = cols[i].k; if (!k) return;
          dir = sortK === k ? -dir : (cols[i].asc ? 1 : -1); sortK = k;
          t.querySelectorAll("th").forEach(function (x) { x.removeAttribute("aria-sort"); });
          th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
          t.tBodies[0].innerHTML = body(); wire();
        });
      });
      function wire() {
        t.querySelectorAll("tbody tr").forEach(function (tr) {
          tr.addEventListener("click", function () { onRow(tr.getAttribute("data-k")); });
          tr.addEventListener("keydown", function (e) { if (e.key === "Enter") onRow(tr.getAttribute("data-k")); });
        });
      }
      wire();
    });
    return '<div class="scroll"><table class="t" id="' + id + '"><thead><tr>' + cols.map(function (c) { return '<th class="' + (c.n ? "n" : "") + '" scope="col">' + esc(c.h) + "</th>"; }).join("") + "</tr></thead><tbody>" + body() + "</tbody></table></div>";
  }

  /* ---------- drawer ---------- */
  var drawer = document.getElementById("drawer"), dbody = document.getElementById("dbody"), lastFocus = null;
  function openDrawer(h) { lastFocus = document.activeElement; dbody.innerHTML = h; drawer.hidden = false; bindTips(dbody); drawer.querySelector(".x").focus(); document.body.style.overflow = "hidden"; }
  function closeDrawer() { drawer.hidden = true; document.body.style.overflow = ""; hideTip(); if (lastFocus) lastFocus.focus(); }
  drawer.addEventListener("click", function (e) { if (e.target.hasAttribute("data-close")) closeDrawer(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !drawer.hidden) closeDrawer(); });

  function cellDrawer(cs, key) {
    var r = cs.filter(function (x) { return x._key === key; })[0]; if (!r) return;
    var peers = cs.filter(function (x) { return x.cat === r.cat; }).sort(function (a, b) { return a.pen - b.pen; });
    var avg = sum(peers, function (x) { return x.processed; }) / sum(peers, function (x) { return x.market; });
    openDrawer('<h2 id="dtitle">#' + r.rank + " · " + esc(r.metro) + " · " + esc(r.catName) + '</h2><div class="filters">' + pill(r.status, STATUS[r.status]) + pill(r.region, "watch") + "</div>" +
      '<div class="kpis k4">' + kpi("Opportunity", r.score.toFixed(2), "rank " + r.rank + " of " + cs.length) + kpi("Penetration", pct(r.pen), "category avg " + pct(avg)) + kpi("Demand growth", r.growth.toFixed(2) + "%", "category, 24 months") + kpi("White space", usd(r.ws), usd(r.market) + " est. market") + "</div>" +
      '<section class="card"><h2>' + esc(r.cat) + " penetration in every metro</h2>" + hbars(peers, function (x) { return x.pen; }, function (x) { return x.metro; }, function (x) { return x._key === key ? C.apr : C.i300; }, function (v) { return pct(v); }, r.cat + " penetration by metro") + "</section>" +
      '<div class="ins i-ai">Score check: ' + r.growth.toFixed(2) + "% growth × (1 − " + r.pen.toFixed(3) + ") = <b>" + (r.growth * (1 - r.pen)).toFixed(2) + "</b>. " + num(r.merchants) + " merchants processed " + usd(r.processed) + " of an estimated " + usd(r.market) + ".</div>" + powered("Semantic View SITE_SELECTION_SV"));
  }
  function metroDrawer(cs, metros, id) {
    var m = metros.filter(function (x) { return x.metro_id === id; })[0], rs = cs.filter(function (x) { return x.metro_id === id; }).sort(function (a, b) { return b.score - a.score; });
    var best = rs[0];
    openDrawer('<h2 id="dtitle">' + esc(m.metro_name) + ", " + esc(m.state) + '</h2><div class="filters">' + pill(m.region, "watch") + pill("Best: " + best.cat + " #" + best.rank, STATUS[best.status]) + "</div>" +
      '<div class="kpis k4">' + kpi("Population", num(m.population), "synthetic sizing") + kpi("Median income", "$" + num(m.median_hh_income), "household") + kpi("White space", usd(sum(rs, function (r) { return r.ws; })), "all 6 categories") + kpi("Penetration", pct(sum(rs, function (r) { return r.processed; }) / sum(rs, function (r) { return r.market; })), num(sum(rs, function (r) { return r.merchants; })) + " merchants today") + "</div>" +
      '<section class="card"><h2>Opportunity by category</h2>' + hbars(rs, function (r) { return r.score; }, function (r) { return r.cat; }, function (r) { return r.status === "Top target" ? C.apr : C.i600; }, function (v) { return v.toFixed(2); }, "Opportunity score by category for " + m.metro_name) + "</section>" +
      '<div class="scroll"><table class="t"><tr><th>Category</th><th class="n">Penetration</th><th class="n">Demand growth</th><th class="n">Score</th><th class="n">White space</th><th class="n">Merchants</th><th>Status</th></tr>' +
      rs.map(function (r) { return "<tr><td>" + esc(r.cat) + '</td><td class="n">' + pct(r.pen) + '</td><td class="n">' + r.growth.toFixed(2) + '%</td><td class="n">' + r.score.toFixed(2) + '</td><td class="n">' + usd(r.ws) + '</td><td class="n">' + num(r.merchants) + "</td><td>" + pill(r.status, STATUS[r.status]) + "</td></tr>"; }).join("") + "</table></div>" +
      powered("Semantic View SITE_SELECTION_SV · metro sizing from SITE_SELECTION_METRO"));
  }

  /* ---------- staged AI ---------- */
  function stagedRun(box, steps, totalMs) {
    box.innerHTML = '<ul class="steps">' + steps.map(function (s) { return '<li><span class="spin"></span>' + esc(s) + "</li>"; }).join("") + "</ul>";
    var lis = box.querySelectorAll("li"), per = totalMs / steps.length, p = Promise.resolve();
    steps.forEach(function (_, i) { p = p.then(function () { lis[i].className = "on"; return sleep(per * jitter(.85, 1.15)); }).then(function () { lis[i].className = "done"; }); });
    return p;
  }
  function streamInto(el, text, wps) {
    var toks = text.split(/(\s+)/), acc = "", i = 0;
    return new Promise(function (res) {
      (function tick() {
        for (var k = 0; k < 3 && i < toks.length; k++) acc += toks[i++];
        el.innerHTML = md(acc) + '<span class="caret"></span>';
        if (i < toks.length) setTimeout(tick, 1000 / wps * 3); else { el.innerHTML = md(text); res(); }
      })();
    });
  }
  var SAMPLE_LABEL = '<div class="ailabel">Sample AI response · captured from a Live run, replayed with a simulated delay</div>';
  function stamp(ok) { return '<span class="stamp ' + (ok ? "s-ok" : "s-bad") + '">' + (ok ? "Verified" : "Needs review") + "</span>"; }
  function verdictLine(v) { return '<div style="margin:.5rem 0 .7rem">' + stamp(v.status === "verified") + '<span style="margin-left:.8rem;font-size:.8rem;color:' + C.muted + '">residual hedges: ' + v.residual_hedges + " · flagged: " + v.edits.length + "</span></div>"; }
  function flags(v) { return v.edits && v.edits.length ? '<div class="ins i-flat"><b>Verifier flags</b><ul style="margin:.2rem 0 0 1rem;padding:0">' + v.edits.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("") + "</ul></div>" : ""; }
  function factPack(fp) {
    if (!fp || !fp.length) return "";
    var cols = Object.keys(fp[0]);
    return "<details><summary>Sources: fact pack (" + fp.length + " cells, cited as F1-F" + fp.length + ')</summary><div class="scroll"><table class="t"><tr>' + cols.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr>" + fp.map(function (r) { return "<tr>" + cols.map(function (c) { return "<td>" + esc(r[c]) + "</td>"; }).join("") + "</tr>"; }).join("") + "</table></div></details>";
  }
  function noteHtml(res) { return '<section class="card">' + SAMPLE_LABEL + '<div class="note">' + md(res.draft) + "</div>" + verdictLine(res.verdict) + flags(res.verdict) + factPack(res.fact_pack) + "</section>"; }
  function rvHtml(rv) { return SAMPLE_LABEL + '<div class="ins i-flat">Added: <i>' + esc(HEDGE) + "</i></div>" + verdictLine(rv.verdict) + flags(rv.verdict); }
  function msgU(q) { return '<div class="msg u"><div class="who">You</div><div class="body">' + esc(q) + "</div></div>"; }
  function msgA(h) { return '<div class="msg a"><div class="who">AI</div><div class="body">' + h + "</div></div>"; }
  function answerHtml(a) {
    return SAMPLE_LABEL + '<div class="note">' + md(a.text) + "</div>" + (a.tables || []).map(function (t) {
      return '<div class="scroll"><table class="t"><tr>' + t.columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr>" + t.rows.map(function (r) { return "<tr>" + r.map(function (x) { return "<td>" + esc(x) + "</td>"; }).join("") + "</tr>"; }).join("") + "</table></div>";
    }).join("") + (a.sql ? "<details><summary>Source: SQL generated by Cortex Analyst over SITE_SELECTION_SV</summary><pre>" + esc(a.sql) + "</pre></details>" : "");
  }

  /* ---------- screens ---------- */
  var screens = {
    overview: function () {
      return Promise.all([load("cells"), load("demand"), load("source")]).then(function (d) {
        var cs = cells(d[0]), top = cs[0], second = cs[1];
        var growth = {}; cs.forEach(function (r) { growth[r.cat] = r.growth; });
        var fast = Object.keys(growth).sort(function (a, b) { return growth[b] - growth[a]; })[0];
        var ranked = cs.filter(function (r) { return r.score > 0; }).length, big = cs.slice().sort(function (a, b) { return b.ws - a.ws; })[0];
        var sat = cs.filter(function (r) { return r.status === "Saturated"; }), furn = cs.filter(function (r) { return r.cat === "Furniture"; });
        var regs = group(cs.slice(0, 12), function (r) { return r.region; });
        return "<h1>Expansion overview</h1><p class=\"sub\">Corvane Payments coverage in 10 metros × 6 merchant categories, against 24 months of category demand to 30 Jun 2026. Opportunity score = demand growth % × (1 − penetration).</p>" +
          '<div class="kpis">' + kpi("White space", usd(sum(cs, function (r) { return r.ws; })), usd(sum(cs, function (r) { return r.market; })) + " est. market") +
          kpi("Penetration", pct(sum(cs, function (r) { return r.processed; }) / sum(cs, function (r) { return r.market; })), "volume-weighted, all cells") +
          kpi("Top target", top.metro, top.cat + " · score " + top.score.toFixed(2) + " · " + pct(top.pen) + " covered") +
          kpi("Fastest category", fast, "+" + growth[fast].toFixed(2) + "% demand in 24 months") +
          kpi("Cells ranked", ranked + " of " + cs.length, (cs.length - ranked) + " with no demand growth") + "</div>" +
          '<div class="grid"><section class="card"><h2>Opportunity score by metro and category</h2>' + powered("Semantic View SITE_SELECTION_SV · SEMANTIC_VIEW() query") + heatmap(cs) +
          '<p class="cap">Furniture scores 0 in every metro: its demand did not grow, so its white space is not a target. Click a cell in the ranking for detail.</p></section>' +
          '<section class="card"><h2>What stands out</h2>' +
          '<div class="ins i-target"><b>' + esc(top.metro) + " " + top.cat.toLowerCase() + " leads.</b> " + pct(top.pen) + " covered in the fastest-growing category (+" + top.growth.toFixed(2) + "%), " + usd(top.ws) + " of white space, score " + top.score.toFixed(2) + ".</div>" +
          '<div class="ins i-target"><b>Runner-up: ' + esc(second.metro) + " " + second.cat.toLowerCase() + "</b> at " + pct(second.pen) + " covered, score " + second.score.toFixed(2) + ".</div>" +
          '<div class="ins i-ai"><b>Biggest pool is not the top score.</b> ' + esc(big.metro) + " " + big.cat.toLowerCase() + " holds " + usd(big.ws) + " but ranks #" + big.rank + ".</div>" +
          (sat.length ? '<div class="ins i-sat"><b>' + esc(sat[0].metro) + " " + sat[0].cat.toLowerCase() + " is saturated</b> at " + pct(sat[0].pen) + " penetration.</div>" : "") +
          '<div class="ins i-flat"><b>Flat demand scores zero.</b> Furniture has ' + usd(sum(furn, function (r) { return r.ws; })) + " of white space and no growth.</div>" +
          '<div class="ins"><b>Top 12 by region:</b> ' + Object.keys(regs).sort(function (a, b) { return regs[b].length - regs[a].length; }).map(function (k) { return k + " " + regs[k].length; }).join(", ") + "</div>" +
          '<p class="cap"><a href="#/notes"><b>Write a verified expansion note</b></a></p></section></div>' +
          '<section class="card"><h2>Category demand, last 24 months</h2>' + demandChart(d[1]) + '<p class="cap">Index, first month = 100. Shaded: November–December. Data mode: ' + esc(d[2].mode) + ". " + esc(d[2].note) + "</p></section>";
      });
    },
    map: function () {
      return Promise.all([load("cells"), load("metros"), load("regions"), load("dotmap")]).then(function (d) {
        var cs = cells(d[0]), metros = d[1], bm = group(cs, function (r) { return r.metro_id; });
        var rows = metros.map(function (m) {
          var rs = bm[m.metro_id], best = rs.slice().sort(function (a, b) { return a.rank - b.rank; })[0];
          return { _key: m.metro_id, metro: m.metro_name, region: m.region, ws: sum(rs, function (r) { return r.ws; }), pen: sum(rs, function (r) { return r.processed; }) / sum(rs, function (r) { return r.market; }),
            merchants: sum(rs, function (r) { return r.merchants; }), best: best.cat, bestScore: best.score, top: best.rank };
        });
        var regions = d[2].slice().sort(function (a, b) { return b.total_white_space_usd - a.total_white_space_usd; });
        setTimeout(function () { view.querySelectorAll("[data-metro]").forEach(function (c) { c.addEventListener("click", function () { metroDrawer(cs, metros, c.getAttribute("data-metro")); }); }); });
        return '<h1>Market map</h1><p class="sub">Each metro sized by its white-space dollars across the six categories, colored by region. Apricot rings mark the metros that hold a top-5 cell. Click a metro, on the map or in the table, for its category breakdown.</p>' +
          '<section class="card">' + mapChart(cs, metros, d[3]) + '<p class="cap">Positions are city-centre longitude/latitude on a dot grid of the contiguous US. Metro sizing is synthetic.</p></section>' +
          '<section class="card"><h2>Regions</h2>' + powered("SEMANTIC_VIEW(SITE_SELECTION_SV) · metrics by region") + '<div class="scroll"><table class="t"><tr><th>Region</th><th class="n">White space</th><th class="n">Penetration</th><th class="n">Avg score</th><th class="n">Best score</th></tr>' +
          regions.map(function (r) { return '<tr><td><b style="display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:.4rem;background:' + REG[r.region] + '"></b>' + esc(r.region) + '</td><td class="n">' + usd(r.total_white_space_usd) + '</td><td class="n">' + pct(r.weighted_penetration) + '</td><td class="n">' + r.avg_opportunity_score.toFixed(2) + '</td><td class="n">' + r.max_opportunity_score.toFixed(2) + "</td></tr>"; }).join("") + "</table></div></section>" +
          '<section class="card"><h2>Metros</h2>' + table([
            { h: "Metro", k: "metro", asc: 1, f: function (r) { return "<b>" + esc(r.metro) + "</b>"; } },
            { h: "Region", k: "region", asc: 1, f: function (r) { return esc(r.region); } },
            { h: "White space", k: "ws", n: 1, f: function (r) { return usd(r.ws); } },
            { h: "Penetration", k: "pen", f: function (r) { return '<span class="bar"><i style="width:' + Math.min(100, r.pen * 200) + '%"></i></span>' + pct(r.pen); } },
            { h: "Merchants", k: "merchants", n: 1, f: function (r) { return num(r.merchants); } },
            { h: "Best category", k: "best", asc: 1, f: function (r) { return esc(r.best); } },
            { h: "Best score", k: "bestScore", n: 1, f: function (r) { return r.bestScore.toFixed(2); } },
            { h: "Best rank", k: "top", n: 1, asc: 1, f: function (r) { return "#" + r.top; } }
          ], rows.sort(function (a, b) { return a.top - b.top; }), function (id) { metroDrawer(cs, metros, id); }) + "</section>";
      });
    },
    ranking: function () {
      return load("cells").then(function (raw) {
        var cs = cells(raw), f = state.f || (state.f = { reg: { Northeast: 1, West: 1, South: 1, Midwest: 1 }, cat: { Grocery: 1, Restaurants: 1, Health: 1, Apparel: 1, Electronics: 1, Furniture: 1 }, q: "" });
        var rows = cs.filter(function (r) { return f.reg[r.region] && f.cat[r.cat] && (!f.q || (r.metro + " " + r.catName + " " + r.status + " " + r.region).toLowerCase().indexOf(f.q.toLowerCase()) >= 0); });
        function chip(g, k) { return '<button type="button" class="fchip" data-g="' + g + '" data-k="' + k + '" aria-pressed="' + (!!f[g][k]) + '">' + k + "</button>"; }
        var h = '<h1>Opportunity ranking</h1><p class="sub">All 60 metro × category cells. The shaded corner of the scatter is where demand is growing and coverage is thin. Filter, sort any column, and click a row or a bubble to open the cell.</p>' +
          '<div class="filters">' + Object.keys(f.reg).map(function (k) { return chip("reg", k); }).join("") + '<span style="width:.5rem"></span>' + Object.keys(f.cat).map(function (k) { return chip("cat", k); }).join("") +
          '<input class="search" type="search" placeholder="Search: Houston, saturated" aria-label="Search cells" value="' + esc(f.q) + '"></div>';
        if (!rows.length) return h + '<div class="empty">No cells match these filters. Clear a filter or the search box.</div>';
        setTimeout(function () { view.querySelectorAll("[data-cell]").forEach(function (c) { c.addEventListener("click", function () { cellDrawer(cs, c.getAttribute("data-cell")); }); }); });
        return h + '<section class="card"><h2>Penetration vs demand growth</h2>' + scatter(rows) + "</section>" +
          '<section class="card">' + powered(rows.length + " of " + cs.length + " cells · rows from SEMANTIC_VIEW(SITE_SELECTION_SV)") + table([
            { h: "Rank", k: "rank", n: 1, asc: 1, f: function (r) { return "#" + r.rank; } },
            { h: "Metro", k: "metro", asc: 1, f: function (r) { return "<b>" + esc(r.metro) + "</b>"; } },
            { h: "Region", k: "region", asc: 1, f: function (r) { return esc(r.region); } },
            { h: "Category", k: "cat", asc: 1, f: function (r) { return esc(r.cat); } },
            { h: "Penetration", k: "pen", f: function (r) { return '<span class="bar"><i style="width:' + Math.min(100, r.pen * 200) + '%"></i></span>' + pct(r.pen); } },
            { h: "Demand growth", k: "growth", n: 1, f: function (r) { return r.growth.toFixed(2) + "%"; } },
            { h: "Opportunity", k: "score", n: 1, f: function (r) { return "<b>" + r.score.toFixed(2) + "</b>"; } },
            { h: "White space", k: "ws", n: 1, f: function (r) { return usd(r.ws); } },
            { h: "Merchants", k: "merchants", n: 1, f: function (r) { return num(r.merchants); } },
            { h: "Status", k: "status", asc: 1, f: function (r) { return pill(r.status, STATUS[r.status]); } }
          ], rows, function (k) { cellDrawer(cs, k); }) + "</section>";
      });
    },
    notes: function () {
      return load("reports").then(function (reports) {
        var n = state.note;
        var h = '<h1>Expansion notes</h1><p class="sub">A one-page note for the expansion committee: drafted by Cortex AI_COMPLETE from the ranked fact pack, then fact-checked by a second AI_COMPLETE pass that refuses unsupported, forecast or hedged claims.</p>' +
          '<div class="two"><section class="card"><h2>Write a note</h2>' + Object.keys(SCOPES).map(function (k, i) { return '<label class="radio"><input type="radio" name="scope" value="' + k + '"' + ((n ? n.scope === k : i === 0) ? " checked" : "") + ">" + esc(SCOPES[k]) + "</label>"; }).join("") +
          powered("Cortex AI_COMPLETE · draft + verifier") + '<button class="btn" id="runNote" type="button">&#9654; Run site-selection analysis</button><p class="cap">Live runs took 9-12 s in testing and cost two AI_COMPLETE calls.</p></section>' +
          '<div><div id="noteOut">' + (n ? noteHtml(n.res) : '<div class="empty"><b>No note yet.</b><br>Pick a scope and run the analysis. The draft streams in, then the verifier stamps it Verified or Needs review.</div>') + "</div>" +
          '<section class="card" id="breakCard"' + (n ? "" : " hidden") + '><h2>Try to break it</h2><p class="cap" style="margin-top:0">Add a hedged forecast the facts do not support, and run only the verifier again.</p><button class="btn ghost" id="runRv" type="button">Insert a forecast and re-verify</button><div id="rvOut">' + (state.rv && n && state.rv.scope === n.scope ? rvHtml(state.rv.rv) : "") + "</div></section></div></div>" +
          '<h2 style="margin-top:.4rem">Note gallery</h2><div class="gallery">' + reports.map(function (r, i) {
            var ok = r.status === "verified", title = (r.report_md || "").split("\n")[0].replace(/^#+\s*/, "") || r.subject;
            return '<button type="button" class="docket' + (ok ? "" : " bad") + '" data-rep="' + i + '">' + pill(ok ? "Verified" : "Needs review", ok ? "good" : "bad") + '<div class="dt">' + esc(title.slice(0, 90)) + '</div><div class="ds">' + esc(r.subject) + " · " + esc(r.created_at) + " · " + r.edits_applied + " flagged</div></button>";
          }).join("") + "</div>";
        setTimeout(function () {
          view.querySelectorAll("[data-rep]").forEach(function (b) { b.addEventListener("click", function () { var r = reports[+b.getAttribute("data-rep")]; openDrawer('<h2 id="dtitle">Saved expansion note</h2><div style="margin:.4rem 0 .7rem">' + stamp(r.status === "verified") + '</div><div class="note">' + md(r.report_md) + "</div>" + flags({ edits: JSON.parse(r.edits || "[]") }) + factPack(JSON.parse(r.fact_pack || "[]"))); }); });
        });
        return h;
      });
    },
    ask: function () {
      return Promise.resolve('<h1>Ask the analyst</h1><p class="sub">Plain-English questions answered by a Cortex Agent that writes SQL with Cortex Analyst over the SITE_SELECTION_SV semantic view. Every figure comes from a query you can inspect.</p>' +
        powered("Cortex Agent SITE_SELECTION_AGENT · Cortex Analyst · Semantic View SITE_SELECTION_SV") +
        '<div class="qs">' + QUESTIONS.map(function (q, i) { return '<button type="button" class="q" data-q="' + i + '">' + esc(q) + "</button>"; }).join("") + "</div>" +
        '<div id="chat">' + state.chat.map(function (c) { return msgU(c.q) + msgA(answerHtml(c.a)); }).join("") + "</div>" +
        '<form class="ask" id="askForm"><input id="askIn" placeholder="Sample mode answers the three questions above" aria-label="Ask a question"><button class="btn" type="submit">Ask</button></form><div id="askNote"></div>');
    }
  };

  /* ---------- page wiring ---------- */
  function wire(route) {
    bindTips(view); animateCounts();
    view.querySelectorAll(".fchip").forEach(function (b) {
      b.addEventListener("click", function () { var g = state.f[b.getAttribute("data-g")], k = b.getAttribute("data-k"); if (g[k]) delete g[k]; else g[k] = 1; render(); });
    });
    var s = view.querySelector(".search");
    if (s) s.addEventListener("change", function () { state.f.q = s.value; render(); });
    if (route === "notes") {
      var btn = document.getElementById("runNote");
      btn.addEventListener("click", function () {
        var scope = view.querySelector("input[name=scope]:checked").value, out = document.getElementById("noteOut");
        btn.disabled = true; out.innerHTML = '<section class="card"><div id="stg"></div></section>';
        Promise.all([load("generate_" + scope), load("fact_pack_" + scope)]).then(function (d) {
          var res = d[0];
          return stagedRun(document.getElementById("stg"), ["Reading 60 metro × category cells through SITE_SELECTION_SV…", "Ranking by opportunity score and building the fact pack: " + d[1].length + " cells, the note's only allowed numbers…", "Drafting the expansion note with AI_COMPLETE (claude-sonnet-4-5)…", "Verifying every figure against the fact pack and checking for hedges…", "Saving the note and verdict to SITE_SELECTION_REPORTS…"], jitter(4000, 8000)).then(function () {
            out.innerHTML = '<section class="card">' + SAMPLE_LABEL + '<div class="note" id="noteBody"></div><div id="vd"></div></section>';
            return streamInto(document.getElementById("noteBody"), res.draft, 90);
          }).then(function () {
            document.getElementById("vd").innerHTML = verdictLine(res.verdict) + flags(res.verdict) + factPack(res.fact_pack);
            state.note = { scope: scope, res: res }; state.rv = null; btn.disabled = false;
            document.getElementById("breakCard").hidden = false; document.getElementById("rvOut").innerHTML = "";
          });
        }).catch(fail);
      });
      var rb = document.getElementById("runRv");
      rb.addEventListener("click", function () {
        if (!state.note) return;
        var out = document.getElementById("rvOut"), scope = state.note.scope; rb.disabled = true;
        out.innerHTML = '<div id="stg2"></div>';
        load("reverify_" + scope).then(function (rv) {
          return stagedRun(document.getElementById("stg2"), ["Re-reading the fact pack…", "Checking each figure in the edited draft…", "Scanning for hedges and forecasts…"], jitter(4000, 6000)).then(function () {
            state.rv = { scope: scope, rv: rv }; out.innerHTML = rvHtml(rv); rb.disabled = false;
          });
        }).catch(fail);
      });
    }
    if (route === "ask") {
      var ask = function (i) {
        var chat = document.getElementById("chat"), q = QUESTIONS[i], wrap = document.createElement("div");
        wrap.innerHTML = msgU(q) + msgA('<div class="stg3"></div><div class="ans"></div>'); chat.appendChild(wrap);
        var stg = wrap.querySelector(".stg3"), ans = wrap.querySelector(".ans");
        wrap.scrollIntoView({ behavior: "smooth", block: "start" });
        load("ask_" + i).then(function (a) {
          return stagedRun(stg, ["Planning with the Cortex Agent…", "Generating SQL with Cortex Analyst over SITE_SELECTION_SV…", "Running the query on SNOWPACK_SITE_SELECTION_WH…", "Writing the answer from the result set…"], jitter(5000, 8000)).then(function () {
            stg.innerHTML = ""; ans.innerHTML = SAMPLE_LABEL + '<div class="note"></div>';
            return streamInto(ans.querySelector(".note"), a.text, 90).then(function () { ans.innerHTML = answerHtml(a); state.chat.push({ q: q, a: a }); });
          });
        }).catch(fail);
      };
      view.querySelectorAll("[data-q]").forEach(function (b) { b.addEventListener("click", function () { ask(+b.getAttribute("data-q")); }); });
      document.getElementById("askForm").addEventListener("submit", function (e) {
        e.preventDefault(); var v = document.getElementById("askIn").value.trim(), i = QUESTIONS.indexOf(v);
        if (i >= 0) ask(i); else document.getElementById("askNote").innerHTML = '<div class="callout">Sample mode replays captured answers to the three sample questions. Run the app in Live mode to ask your own.</div>';
      });
    }
  }
  function fail(e) { view.innerHTML = '<div class="empty"><b>Could not load sample data.</b><br>' + esc(e.message) + "</div>"; }
  function render() {
    var route = (location.hash.replace(/^#\//, "") || "overview").split("?")[0];
    if (!screens[route]) route = "overview";
    document.querySelectorAll(".nav a").forEach(function (a) { if (a.getAttribute("data-r") === route) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    document.title = document.querySelector('.nav a[data-r="' + route + '"]').textContent + " · Geographic Expansion & Site Selection (sample)";
    view.innerHTML = '<div class="skel"></div>';
    screens[route]().then(function (h) { view.innerHTML = h; wire(route); }).catch(fail);
  }
  document.getElementById("goLive").addEventListener("click", function () {
    view.insertAdjacentHTML("afterbegin", '<div class="callout"><b>Live mode runs in your Snowflake account.</b> This hosted example is always Sample mode. To see live inference, run <code>sql/setup.sql</code>, then deploy the Streamlit app or run it locally with key-pair auth. See <a href="https://github.com/sfc-gh-jsoliz/sfguide-site-selection#run-it-live">the repository guide</a>.</div>');
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  addEventListener("hashchange", function () { hideTip(); closeDrawerIfOpen(); render(); });
  function closeDrawerIfOpen() { if (!drawer.hidden) closeDrawer(); }
  render();
})();
