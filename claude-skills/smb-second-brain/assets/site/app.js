/* Second Brain atlas — generic viewer for any atlas.json built by
   scripts/build_atlas.py. Nothing in here is corpus-specific: node types,
   colours, filters and the legend are all read from the data file. */

const $  = id => document.getElementById(id);
const nid = x => (typeof x === 'object' ? x.id : x);
const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; };

marked.use({ tokenizer: { del() { return undefined; } } }); // '~$1M to ~$2M' must not render as strikethrough
let A = null;              // the whole bundle
let COLORS = {};           // type -> colour
let GRAPH = null, adj = {}, hi = null, spin = 0;
let activeTypes = new Set();
let query = '';

const radius = n => 2.4 + Math.sqrt(n.val) * 1.1;
const DIMCOL = '#2c2620';

/* ------------------------------------------------------------------ boot */
fetch('data/atlas.json')
  .then(r => { if (!r.ok) throw new Error(`data/atlas.json → HTTP ${r.status}`); return r.json(); })
  .then(data => { A = data; init(); })
  .catch(err => {
    $('left-scroll').innerHTML =
      `<p class="disclaimer"><b>Could not load data/atlas.json.</b><br>${err.message}
       <br><br>Build it first:<br><code>python3 scripts/build_atlas.py --vault ./vault --out ./site/data/atlas.json</code>
       <br><br>Then serve the folder (file:// will not work):<br><code>python3 -m http.server 4351</code></p>`;
  });

function init() {
  A.types.forEach(t => { COLORS[t.key] = t.color; });
  const m = A.meta;
  document.title = m.title;
  $('brand').textContent = m.title;
  $('title').innerHTML = m.title.replace(/\s+(\S+)$/, ' <em>$1</em>');
  $('subtitle').textContent = m.subtitle || '';
  $('counts').innerHTML = A.types.map(t => `<b>${t.count}</b> ${t.label.toLowerCase()}`).join(' · ');
  $('graph-sub').textContent = `${m.notes} notes · ${m.links} links`;
  if (m.disclaimer) $('disclaimer').textContent = '⚠ ' + m.disclaimer;
  else $('disclaimer').hidden = true;

  buildTypeChips();
  buildIndex();
  bootGraph();
  wireChrome();
}

/* --------------------------------------------------------------- filters */
function buildTypeChips() {
  const box = $('type-chips');
  box.innerHTML = `<span class="chip chip-all is-active" data-type="">All</span>` +
    A.types.map(t => `<span class="chip" data-type="${t.key}"
      style="--dot:${t.color}">${t.label}</span>`).join('');
  box.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {
    const t = chip.dataset.type;
    if (!t) activeTypes.clear();
    else { activeTypes.has(t) ? activeTypes.delete(t) : activeTypes.add(t); }
    box.querySelectorAll('.chip').forEach(c =>
      c.classList.toggle('is-active', c.dataset.type
        ? activeTypes.has(c.dataset.type)
        : activeTypes.size === 0));
    buildIndex(); refresh();
  }));
}

const passes = n =>
  (activeTypes.size === 0 || activeTypes.has(n.type)) &&
  (!query || (n.label + ' ' + (n.one_liner || '')).toLowerCase().includes(query));

/* ----------------------------------------------------------------- index */
function buildIndex() {
  const list = A.nodes.filter(passes)
    .sort((a, b) => b.val - a.val || a.label.localeCompare(b.label));
  $('results-count').textContent =
    `${list.length} of ${A.nodes.length} notes` + (query ? ` matching “${query}”` : '');
  $('note-index').innerHTML = list.slice(0, 300).map(n => `
    <li class="ep" data-id="${n.id}">
      <span class="ep-dot" style="background:${COLORS[n.type] || '#999'}"></span>
      <div>
        <p class="ep-title">${esc(n.label)}</p>
        ${n.one_liner ? `<p class="ep-sub">${esc(n.one_liner)}</p>` : ''}
      </div>
    </li>`).join('');
  $('note-index').querySelectorAll('.ep').forEach(li =>
    li.addEventListener('click', () => openNote(li.dataset.id)));
}

const esc = s => String(s || '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

/* ------------------------------------------------------------ note reader */
function openNote(id) {
  const node = A.nodes.find(n => n.id === id);
  if (!node) return;
  const note = A.notes[id];
  const type = A.types.find(t => t.key === node.type);
  const neighbours = (adj[id] || []).map(x => A.nodes.find(n => n.id === x)).filter(Boolean);

  let body = '';
  if (note && note.body) {
    body = `<div class="wiki-md">${marked.parse(convertWiki(note.body))}</div>`;
  } else {
    body = `<p class="d-disclaimer">This node is a hub — it has no note of its own.
            It exists because other notes point at it.</p>`;
  }

  $('detail-view').innerHTML = `
    <button class="back" id="back">← index</button>
    <p class="eyebrow" style="color:${COLORS[node.type]}">— ${esc(type ? type.label : node.type)}</p>
    <h2 class="d-title">${esc(node.label)}</h2>
    ${node.one_liner ? `<p class="d-oneliner">${esc(node.one_liner)}</p>` : ''}
    ${note && note.path ? `<p class="d-meta"><code>${esc(note.path)}</code></p>` : ''}
    ${body}
    ${neighbours.length ? `<h3 class="d-h3">Linked notes (${neighbours.length})</h3>
      <ul class="d-links">${neighbours.slice(0, 40).map(n =>
        `<li data-id="${n.id}"><span class="ep-dot" style="background:${COLORS[n.type]}"></span>
         ${esc(n.label)}</li>`).join('')}</ul>` : ''}`;

  $('index-view').hidden = true;
  $('detail-view').hidden = false;
  $('left-scroll').scrollTop = 0;
  $('back').addEventListener('click', backToIndex);
  $('detail-view').querySelectorAll('.d-links li').forEach(li =>
    li.addEventListener('click', () => openNote(li.dataset.id)));
  wireWikiLinks($('detail-view'));
  focusNode(id);
  highlight(id);
}

function backToIndex() {
  $('detail-view').hidden = true;
  $('index-view').hidden = false;
  clearHi();
}

/* [[target|alias]] -> anchor the reader can resolve back to a node id */
function convertWiki(md) {
  return md.replace(/\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|([^\]]+))?\]\]/g, (_, tgt, alias) => {
    const slug = String(tgt).split('/').pop().replace(/\.md$/i, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `<a class="wl" data-slug="${slug}">${esc(alias || tgt)}</a>`;
  });
}

function wireWikiLinks(el) {
  el.querySelectorAll('a.wl').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    const hit = A.nodes.find(n => n.slug === a.dataset.slug);
    if (hit) openNote(hit.id); else a.classList.add('wl-dead');
  }));
}

/* ----------------------------------------------------------------- graph */
function bootGraph() {
  A.links.forEach(l => {
    (adj[nid(l.source)] ||= []).push(nid(l.target));
    (adj[nid(l.target)] ||= []).push(nid(l.source));
  });

  GRAPH = ForceGraph3D()($('graph'))
    .graphData({ nodes: A.nodes.map(n => ({ ...n })), links: A.links.map(l => ({ ...l })) })
    .backgroundColor('#141210')
    .nodeLabel(n => `<div style="font:13px system-ui;background:#1c1815;color:#f0e9dd;
        padding:6px 9px;border-radius:6px;border:1px solid #3a332c;max-width:280px">
        <b>${esc(n.label)}</b>${n.one_liner ? '<br><span style="color:#a89f92">'
        + esc(n.one_liner.slice(0, 110)) + '</span>' : ''}</div>`)
    .nodeVal(n => n.val)
    .nodeRelSize(2.2)
    .nodeColor(n => (hi && !hi.has(n.id)) ? DIMCOL : (COLORS[n.type] || '#999'))
    .nodeOpacity(0.95)
    .linkColor(l => (hi && (!hi.has(nid(l.source)) || !hi.has(nid(l.target))))
      ? 'rgba(44,38,32,.35)' : 'rgba(180,168,150,.30)')
    .linkWidth(l => (hi && hi.has(nid(l.source)) && hi.has(nid(l.target))) ? 1.4 : 0.4)
    .onNodeClick(n => openNote(n.id))
    .onBackgroundClick(clearHi)
    .cooldownTicks(220);

  GRAPH.d3Force('charge').strength(-95);
  buildLegend();
  window.addEventListener('resize', size); size();
  setTimeout(() => GRAPH.zoomToFit(900, 90), 1400);
}

function size() {
  const el = $('graph'), w = el.clientWidth, h = el.clientHeight;
  if (w > 0 && h > 0) GRAPH.width(w).height(h);
}
function refresh() {
  if (!GRAPH) return;
  GRAPH.nodeColor(GRAPH.nodeColor()).linkColor(GRAPH.linkColor()).linkWidth(GRAPH.linkWidth());
}
function highlight(id) { hi = new Set([id, ...(adj[id] || [])]); refresh(); }
function clearHi() { hi = null; refresh(); }

function focusNode(id) {
  const n = GRAPH.graphData().nodes.find(x => x.id === id);
  if (!n || n.x === undefined) return;
  const d = 300, r = 1 + d / Math.hypot(n.x, n.y, n.z || 1);
  GRAPH.cameraPosition({ x: n.x * r, y: n.y * r, z: (n.z || 1) * r }, n, 900);
}

function buildLegend() {
  $('glegend').innerHTML = A.types.map(t =>
    `<span class="lg"><i style="background:${t.color}"></i>${esc(t.label)}</span>`).join('');
}

/* ----------------------------------------------------------------- chrome */
function wireChrome() {
  $('nav-in').onclick    = () => zoom(0.75);
  $('nav-out').onclick   = () => zoom(1.35);
  $('nav-reset').onclick = () => { clearHi(); GRAPH.zoomToFit(700, 80); };
  $('nav-home').onclick  = () => { backToIndex(); GRAPH.zoomToFit(700, 80); };
  $('nav-spin').onclick  = toggleSpin;
  $('reset-all').onclick = () => {
    activeTypes.clear(); query = ''; $('search').value = '';
    $('search-clear').hidden = true;
    $('type-chips').querySelectorAll('.chip').forEach(c =>
      c.classList.toggle('is-active', !c.dataset.type));
    backToIndex(); buildIndex(); GRAPH.zoomToFit(700, 80);
  };

  const s = $('search');
  s.addEventListener('input', () => {
    query = s.value.trim().toLowerCase();
    $('search-clear').hidden = !query;
    if (!$('detail-view').hidden) backToIndex();
    buildIndex();
  });
  s.addEventListener('keydown', e => { if (e.key === 'Escape') { s.value = ''; s.dispatchEvent(new Event('input')); } });

  // draggable split
  const div = $('divider'); let dragging = false;
  div.addEventListener('mousedown', () => { dragging = true; div.classList.add('dragging');
    document.body.style.userSelect = 'none'; });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const pct = Math.min(72, Math.max(24, (e.clientX / window.innerWidth) * 100));
    $('left').style.flex = `0 0 ${pct}%`; size();
  });
  window.addEventListener('mouseup', () => { dragging = false; div.classList.remove('dragging');
    document.body.style.userSelect = ''; });
}

function zoom(f) {
  const p = GRAPH.cameraPosition();
  GRAPH.cameraPosition({ x: p.x * f, y: p.y * f, z: p.z * f }, undefined, 260);
}

function toggleSpin() {
  if (spin) { clearInterval(spin); spin = 0; $('nav-spin').classList.remove('on'); return; }
  $('nav-spin').classList.add('on');
  let a = Math.atan2(GRAPH.cameraPosition().x, GRAPH.cameraPosition().z);
  const p = GRAPH.cameraPosition(), d = Math.hypot(p.x, p.z);
  spin = setInterval(() => {
    a += 0.0022;
    GRAPH.cameraPosition({ x: d * Math.sin(a), z: d * Math.cos(a) });
  }, 30);
}
