// «Канал у часі» and «Декодування» over the same verified metric trial as «Етапи
// обробки», plus one secondary «Joint / B0» tab for the legacy full-receiver views.
// Selection (study, point, frame, symbol k) comes from window.metricContext.
(() => {
  'use strict';

  /** Pure helpers (exported for tests). */
  function windowAround(k, size, width) {
    const w = Math.min(size, width);
    const start = Math.max(0, Math.min(size - w, Math.round(k - w / 2)));
    return [start, start + w];
  }
  function summarizeEvents(events, pairErrors) {
    const lengths = events.map(e => e.stop - e.start);
    const symbols = pairErrors.filter(Boolean).length;
    return {
      count: events.length,
      symbols,
      meanLength: lengths.length ? lengths.reduce((a, b) => a + b, 0) / lengths.length : 0,
      maxLength: lengths.length ? Math.max(...lengths) : 0,
    };
  }
  function meanWhere(values, mask) {
    let sum = 0, n = 0;
    values.forEach((v, i) => { if (mask[i] && v !== null && Number.isFinite(v)) { sum += v; n += 1; } });
    return n ? sum / n : null;
  }
  const api = {windowAround, summarizeEvents, meanWhere};
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof document === 'undefined') return;

  const NS = 'http://www.w3.org/2000/svg';
  const C = {hamming: '#c2410c', euclid: '#0a7f8c', ink: '#142433', muted: '#6a7a87', line: '#dde4e9', grid: '#eef2f4', bad: '#dc2626', pilot: '#eef2f4', snr: '#7c3aed', gain: '#0369a1'};
  const $ = id => document.getElementById(id);
  const num = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('uk-UA', {minimumFractionDigits: d, maximumFractionDigits: d}));
  const esc = s => String(s).replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
  function add(parent, tag, attrs = {}, text) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    parent.append(node);
    return node;
  }
  function svg(w, h, label) {
    const node = document.createElementNS(NS, 'svg');
    node.setAttribute('viewBox', `0 0 ${w} ${h}`);
    node.setAttribute('role', 'img');
    node.setAttribute('aria-label', label);
    node.classList.add('mt-svg');
    return node;
  }

  const state = {frame: null, key: '', request: 0, zoomChannel: 512, zoomTrellis: 96};

  const css = document.createElement('style');
  css.textContent = `
  .mt-view .mt-tools{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 12px}
  .mt-view .mt-tools .seg{display:inline-flex;border:1px solid #cfd8de;border-radius:8px;overflow:hidden}
  .mt-view .mt-tools .seg button{border:0;border-radius:0;box-shadow:none;min-height:32px;padding:4px 12px;border-right:1px solid #cfd8de}
  .mt-view .mt-tools .seg button:last-child{border-right:0}
  .mt-view .mt-tools .seg button[aria-pressed=true]{background:#e5f3f4;color:#076b76}
  .mt-view .mt-tools .hint{font-size:12.5px;color:#6a7a87}
  .mt-view svg.mt-svg{width:100%;height:auto;display:block;cursor:crosshair}
  .mt-view svg.mt-svg text{font:11.5px Inter,"Segoe UI",sans-serif;fill:#3f5161}
  .mt-view .mt-split{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
  .mt-view .mt-split>.card{border-top:3px solid var(--ds-line)}
  .mt-view .mt-split>.hamming{border-top-color:${C.hamming}}
  .mt-view .mt-split>.euclid{border-top-color:${C.euclid}}
  .mt-view .mt-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:8px 0 10px}
  .mt-view .mt-kpis div{background:#f4f7f8;border-radius:10px;padding:9px 10px}
  .mt-view .mt-kpis small{display:block;font-size:11px;color:#6a7a87;font-weight:700}
  .mt-view .mt-kpis strong{font-size:19px;color:#142433;font-variant-numeric:tabular-nums}
  .mt-view .mt-note{font-size:13px;line-height:1.55;color:#3f5161;margin:8px 0 0}
  .mt-view .mt-legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#6a7a87;margin-top:8px}
  .mt-view .mt-legend i{display:inline-block;width:18px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}
  .mt-view .mt-legend b{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:5px}
  .mt-view table.mt-events{width:100%;font-size:12.5px}
  .mt-view table.mt-events td,.mt-view table.mt-events th{padding:6px 8px}
  .mt-view table.mt-events tr.cur td{background:#fff5d6}
  .mt-view table.mt-events button{min-height:28px;padding:2px 9px;font-size:12px}
  .mt-view .mt-scroll{max-height:320px;overflow:auto}
  .mt-view .mt-empty{padding:30px;text-align:center;color:#6a7a87}
  .mt-view .mt-trellis-label{display:flex;justify-content:space-between;align-items:baseline;margin:4px 0}
  .mt-view .mt-trellis-label strong{font-size:14px}
  .mt-view .mt-trellis-label.hamming strong{color:${C.hamming}}
  .mt-view .mt-trellis-label.euclid strong{color:${C.euclid}}`;
  document.head.append(css);

  let channelView, decodingView, tabs = {};

  function makeView(id, title) {
    const view = document.createElement('section');
    view.className = 'view mt-view';
    view.id = 'view-' + id;
    view.innerHTML = `<h1>${title}</h1><div class="mt-body"><div class="card mt-empty">Оберіть дослідження в рядку вгорі.</div></div>`;
    document.querySelector('main').append(view);
    return view;
  }
  function makeTab(view, label, after) {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'tab';
    tab.dataset.view = view;
    tab.textContent = label;
    after.after(tab);
    return tab;
  }
  function activate(sections, tab, hash) {
    document.querySelectorAll('main > .view').forEach(v => v.classList.toggle('active', sections.includes(v)));
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.toggle('active', t === tab));
    document.body.classList.remove('r4-on');
    if (location.hash !== hash) history.pushState(null, '', hash);
  }

  function build() {
    channelView = makeView('mchannel', 'Канал у часі: де виникають помилки');
    decodingView = makeView('mdecoding', 'Декодування всього кадру: Хемінг і Евклід');
    const stagesTab = document.querySelector('.tabs .tab[data-view="stages"]');
    tabs.mchannel = makeTab('mchannel', 'Канал у часі', stagesTab);
    tabs.mdecoding = makeTab('mdecoding', 'Декодування', tabs.mchannel);

    // Legacy full receivers: one secondary tab showing both of their views.
    const legacy = ['view-transmitter', 'view-viterbi'].map(id => $(id)).filter(Boolean);
    const savedTab = document.querySelector('.tabs .tab[data-view="saved"]');
    tabs.joint = makeTab('joint', 'Joint / B0', savedTab);
    tabs.joint.title = 'Повні приймачі Joint / B0: сигнал і решітка (не ізольоване порівняння метрик)';

    const show = {
      mchannel: () => activate([channelView], tabs.mchannel, '#mchannel'),
      mdecoding: () => activate([decodingView], tabs.mdecoding, '#mdecoding'),
      joint: () => { activate(legacy, tabs.joint, '#joint'); },
    };
    for (const [key, tab] of Object.entries(tabs)) tab.addEventListener('click', show[key]);
    const own = [channelView, decodingView];
    const hideOwn = () => { own.forEach(v => v.classList.remove('active')); Object.values(tabs).forEach(t => t.classList.remove('active')); };
    document.querySelectorAll('.tabs .tab').forEach(t => { if (!Object.values(tabs).includes(t)) t.addEventListener('click', hideOwn); });
    for (const name of ['hashchange', 'popstate', 'scientific-view', 'scientific-navigate'])
      window.addEventListener(name, () => {
        const key = location.hash.slice(1);
        if (show[key]) setTimeout(show[key], 0); else hideOwn();
      });
    window.addEventListener('metric-context', e => {
      if (e.detail.frameChanged || !state.frame) loadFrame(e.detail); else renderActive();
    });
    window.addEventListener('resize', () => renderActive());
    // Redraw whenever one of the views becomes visible (any navigation path).
    const visible = new MutationObserver(records => {
      for (const r of records) if (r.target.classList.contains('active') && !r.oldValue?.includes('active')) enter();
    });
    for (const view of own) visible.observe(view, {attributes: true, attributeFilter: ['class'], attributeOldValue: true});
    const key = location.hash.slice(1);
    if (show[key]) setTimeout(show[key], 0);
  }

  function enter() {
    const ctx = window.metricContext?.get();
    window.metricContext?.refresh();
    if (!ctx?.study) return;
    if (!state.frame || state.key !== `${ctx.study}|${ctx.point}|${ctx.trial}`) loadFrame(ctx);
    else renderActive();
  }

  async function loadFrame(ctx) {
    const key = `${ctx.study}|${ctx.point}|${ctx.trial}`;
    const version = ++state.request;
    try {
      const q = new URLSearchParams({study_id: ctx.study, point: ctx.point, trial: ctx.trial});
      const response = await fetch('/api/scientific/metric-frame?' + q);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      if (version !== state.request) return;
      state.frame = data;
      state.key = key;
      renderActive();
    } catch (error) {
      if (version !== state.request) return;
      state.frame = null;
      for (const view of [channelView, decodingView]) view.querySelector('.mt-body').innerHTML = `<div class="card mt-empty">${esc(error.message)}</div>`;
    }
  }

  function renderActive() {
    if (!state.frame) return;
    if (channelView.classList.contains('active')) renderChannel();
    if (decodingView.classList.contains('active')) renderDecoding();
  }
  const ctxK = () => window.metricContext?.get().k ?? 0;
  const goTo = k => window.metricContext?.goTo(k);

  function zoomControl(current, options, onPick) {
    const seg = document.createElement('div');
    seg.className = 'seg';
    seg.setAttribute('role', 'group');
    for (const [value, label] of options) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = label;
      b.setAttribute('aria-pressed', String(value === current));
      b.addEventListener('click', () => onPick(value));
      seg.append(b);
    }
    return seg;
  }

  // ------------------------------------------------------------------ Channel in time
  function renderChannel() {
    const f = state.frame, k = ctxK();
    const body = channelView.querySelector('.mt-body');
    body.replaceChildren();
    const card = document.createElement('article');
    card.className = 'card';
    body.append(card);
    const tools = document.createElement('div');
    tools.className = 'mt-tools';
    const options = [[64, '64'], [256, '256'], [1024, '1024'], [Infinity, 'Весь кадр']].filter(([v]) => v === Infinity || v < f.size);
    tools.append(zoomControl(state.zoomChannel, options, v => { state.zoomChannel = v; renderChannel(); }));
    tools.insertAdjacentHTML('beforeend', `<span class="hint">символів у вікні · клік по графіку — вибрати символ k · ${f.size} символів у кадрі, Eb/N0 ${num(f.gamma_b_discrete_db, 1)} дБ</span>`);
    card.append(tools);

    const [a, b] = windowAround(k, f.size, state.zoomChannel === Infinity ? f.size : state.zoomChannel);
    const W = 1200, left = 70, right = 16;
    const lanes = [['rx', 'RX I/Q', 110], ['snr', 'SNR z_k, дБ', 110], ['offset', '|z_k − s|', 90], ['hamming', 'Хемінг', 34], ['euclidean', 'Евклід', 34]];
    const H = lanes.reduce((s, l) => s + l[2] + 10, 0) + 26;
    const node = svg(W, H, 'Канал і помилки декодерів у часі');
    const X = s => left + (s - a) / (b - a) * (W - left - right);
    let y0 = 6;
    const laneY = {};
    for (const [key, label, h] of lanes) { laneY[key] = [y0, h]; y0 += h + 10; }
    // pilots and selected symbol across all lanes
    const pilotRuns = runs(f.payload_mask.map(p => !p), a, b);
    for (const [s0, s1] of pilotRuns) add(node, 'rect', {x: X(s0), y: 0, width: Math.max(1, X(s1) - X(s0)), height: H - 24, fill: C.pilot});
    for (const [key, label, h] of lanes) {
      const [y, hh] = laneY[key];
      add(node, 'rect', {x: left, y, width: W - left - right, height: hh, fill: 'none', stroke: C.line});
      add(node, 'text', {x: left - 8, y: y + hh / 2 + 4, 'text-anchor': 'end', style: `font-weight:700;${key === 'hamming' ? `fill:${C.hamming}` : key === 'euclidean' ? `fill:${C.euclid}` : ''}`}, label);
    }
    // RX envelope (min/max bins over samples)
    {
      const [y, hh] = laneY.rx;
      const all = [...f.rx_i, ...f.rx_q].filter(p => p[0] / 8 >= a && p[0] / 8 < b);
      const max = Math.max(1e-9, ...all.map(p => Math.max(Math.abs(p[1]), Math.abs(p[2]))));
      const Y = v => y + hh / 2 - v / max * (hh / 2 - 4);
      for (const [series, color] of [[f.rx_i, '#7c3aed'], [f.rx_q, '#db2777']]) {
        let d = '';
        for (const [i, lo, hi] of series) { const s = i / 8; if (s < a || s >= b) continue; d += `M${X(s)},${Y(lo)}L${X(s)},${Y(hi)}`; }
        add(node, 'path', {d, stroke: color, 'stroke-width': 1.2, opacity: 0.75, fill: 'none'});
      }
    }
    // effective SNR of z_k
    {
      const [y, hh] = laneY.snr;
      const vals = f.effective_snr_db.slice(a, b).filter(v => v !== null);
      const lo = Math.min(...vals, 0), hi = Math.max(...vals, 1);
      const Y = v => y + hh - 4 - (v - lo) / Math.max(1e-9, hi - lo) * (hh - 8);
      line(node, a, b, i => f.effective_snr_db[i], X, Y, C.snr, 1.6);
      add(node, 'text', {x: W - right - 4, y: y + 12, 'text-anchor': 'end', style: 'font-size:10.5px'}, `${num(hi, 1)} дБ`);
      add(node, 'text', {x: W - right - 4, y: y + hh - 6, 'text-anchor': 'end', style: 'font-size:10.5px'}, `${num(lo, 1)} дБ`);
    }
    // offset of z_k from the transmitted point, with the hard-decision margin
    {
      const [y, hh] = laneY.offset;
      const A = f.amplitude, margin = A * Math.sin(Math.PI / 8);
      const vals = f.offset.slice(a, b);
      const hi = Math.max(margin * 1.6, ...vals);
      const Y = v => y + hh - 3 - Math.min(v, hi) / hi * (hh - 6);
      add(node, 'line', {x1: left, x2: W - right, y1: Y(margin), y2: Y(margin), stroke: C.hamming, 'stroke-dasharray': '5 4'});
      add(node, 'text', {x: W - right - 4, y: Y(margin) - 4, 'text-anchor': 'end', style: `font-size:10.5px;fill:${C.hamming}`}, 'A·sin(π/8): мінімальна відстань до межі сектора');
      const step = Math.max(1, Math.floor((b - a) / 1500));
      for (let i = a; i < b; i += step) {
        const bad = !f.hard_correct[i];
        add(node, 'circle', {cx: X(i + 0.5), cy: Y(f.offset[i]), r: bad ? 2.4 : 1.4, fill: bad ? C.bad : '#5b6b77', opacity: bad ? 0.95 : 0.45});
      }
    }
    // error lanes: events shaded, symbol errors as ticks
    for (const arm of ['hamming', 'euclidean']) {
      const [y, hh] = laneY[arm];
      const color = arm === 'hamming' ? C.hamming : C.euclid;
      for (const e of f.arms[arm].events) if (e.stop > a && e.start < b) add(node, 'rect', {x: X(Math.max(a, e.start)), y: y + 3, width: Math.max(2, X(Math.min(b, e.stop)) - X(Math.max(a, e.start))), height: hh - 6, fill: color, opacity: 0.25});
      f.arms[arm].pair_errors.forEach((err, i) => { if (err && i >= a && i < b) add(node, 'rect', {x: X(i), y: y + 3, width: Math.max(2, X(i + 1) - X(i)), height: hh - 6, fill: C.bad}); });
    }
    // selected symbol and axis
    if (k >= a && k < b) add(node, 'rect', {x: X(k), y: 0, width: Math.max(2, X(k + 1) - X(k)), height: H - 24, fill: '#f59e0b', opacity: 0.35});
    const ticks = 8;
    for (let t = 0; t <= ticks; t++) {
      const s = Math.round(a + (b - a) * t / ticks);
      add(node, 'text', {x: X(s), y: H - 8, 'text-anchor': t === 0 ? 'start' : t === ticks ? 'end' : 'middle'}, String(s));
    }
    node.addEventListener('click', e => {
      const box = node.getBoundingClientRect();
      const s = a + ((e.clientX - box.left) / box.width * W - left) / (W - left - right) * (b - a);
      if (s >= a && s < b) goTo(Math.floor(s));
    });
    card.append(node);
    card.insertAdjacentHTML('beforeend', `<div class="mt-legend"><span><i style="border-color:#7c3aed"></i>RX I</span><span><i style="border-color:#db2777"></i>RX Q</span><span><i style="border-color:${C.snr}"></i>SNR z_k = A²/σ²_z</span><span><b style="background:${C.bad}"></b>помилка символу / хибне жорстке рішення</span><span><b style="background:${C.hamming};opacity:.3"></b><b style="background:${C.euclid};opacity:.3"></b>подія помилки (шлях відійшов від переданого)</span><span><b style="background:${C.pilot};border:1px solid #dde4e9"></b>пілоти</span><span><b style="background:#f59e0b;opacity:.4"></b>символ k</span></div>`);

    // split summary
    const split = document.createElement('div');
    split.className = 'mt-split';
    body.append(split);
    const hardWrong = f.hard_correct.filter((ok, i) => !ok && f.payload_mask[i]).length;
    for (const arm of ['hamming', 'euclidean']) {
      const a2 = f.arms[arm], ev = summarizeEvents(a2.events, a2.pair_errors);
      const snrAtErr = meanWhere(f.effective_snr_db, a2.pair_errors);
      const snrAll = meanWhere(f.effective_snr_db, f.payload_mask);
      const box = document.createElement('article');
      box.className = 'card ' + (arm === 'hamming' ? 'hamming' : 'euclid');
      box.innerHTML = `<h2>${arm === 'hamming' ? 'Хемінг · жорстке рішення' : 'Евклід · м’яке рішення'}</h2>
        <div class="mt-kpis"><div><small>Помилкових символів</small><strong>${ev.symbols}</strong></div><div><small>Подій помилок</small><strong>${ev.count}</strong></div><div><small>BER кадру</small><strong>${Number(a2.statistics.ber).toExponential(1)}</strong></div><div><small>SNR на помилках</small><strong>${snrAtErr === null ? '—' : num(snrAtErr, 1) + ' дБ'}</strong></div></div>
        <p class="mt-note">${arm === 'hamming'
          ? `Жорстке рішення хибне на <strong>${hardWrong}</strong> символах даних (z_k за межею сектора — червоні точки). Хемінг отримує лише 3 біти, тож кожне таке рішення для нього — повна помилка без міри надійності.`
          : `Евклід бачить ті самі z_k, але враховує, наскільки далеко кожне від усіх точок: близька до межі точка майже не «голосує».`} Середнє SNR z_k на символах даних — ${num(snrAll, 1)} дБ.</p>`;
      split.append(box);
    }
  }
  function runs(mask, a, b) {
    const out = [];
    for (let i = a; i < b; i++) if (mask[i]) { const s = i; while (i < b && mask[i]) i++; out.push([s, i]); }
    return out;
  }
  function line(node, a, b, value, X, Y, color, width) {
    let d = '', pen = false;
    const step = Math.max(1, Math.floor((b - a) / 2400));
    for (let i = a; i < b; i += step) {
      const v = value(i);
      if (v === null || !Number.isFinite(v)) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${X(i + 0.5)},${Y(v)}`;
      pen = true;
    }
    add(node, 'path', {d, fill: 'none', stroke: color, 'stroke-width': width});
  }

  // ------------------------------------------------------------------ Whole-frame decoding
  function renderDecoding() {
    const f = state.frame, k = ctxK();
    const body = decodingView.querySelector('.mt-body');
    body.replaceChildren();
    const card = document.createElement('article');
    card.className = 'card';
    body.append(card);
    const tools = document.createElement('div');
    tools.className = 'mt-tools';
    const options = [[48, '48'], [96, '96'], [192, '192']].filter(([v]) => v < f.size).concat(f.size <= 400 ? [[f.size, 'Весь кадр']] : []);
    tools.append(zoomControl(state.zoomTrellis, options, v => { state.zoomTrellis = v; renderDecoding(); }));
    tools.insertAdjacentHTML('beforeend', '<span class="hint">тактів у вікні · клік по решітці — вибрати такт k · деталі вибору на такті — у «Етапах обробки»</span>');
    card.append(tools);

    // event map over the whole frame
    card.append(eventMap(f, k));
    const [a, b] = windowAround(k, f.size, state.zoomTrellis);
    for (const arm of ['hamming', 'euclidean']) {
      const label = document.createElement('div');
      label.className = 'mt-trellis-label ' + (arm === 'hamming' ? 'hamming' : 'euclid');
      const ev = summarizeEvents(f.arms[arm].events, f.arms[arm].pair_errors);
      label.innerHTML = `<strong>${arm === 'hamming' ? 'Хемінг' : 'Евклід'}</strong><span class="hint" style="font-size:12px;color:#6a7a87">${ev.count} под. · ${ev.symbols} помилк. симв. у кадрі</span>`;
      card.append(label, wideTrellis(f, arm, a, b, k));
    }
    card.insertAdjacentHTML('beforeend', `<div class="mt-legend"><span><i style="border-color:${C.hamming}"></i><i style="border-color:${C.euclid}"></i>шлях декодера</span><span><i style="border-color:${C.ink};border-top-style:dashed"></i>переданий шлях</span><span><b style="background:${C.bad};opacity:.18"></b>подія помилки</span><span><b style="background:${C.pilot};border:1px solid #dde4e9"></b>пілоти</span><span><b style="background:#f59e0b;opacity:.4"></b>такт k</span></div>`);

    const split = document.createElement('div');
    split.className = 'mt-split';
    body.append(split);
    for (const arm of ['hamming', 'euclidean']) split.append(eventsCard(f, arm, k));
    const h = summarizeEvents(f.arms.hamming.events, f.arms.hamming.pair_errors), e = summarizeEvents(f.arms.euclidean.events, f.arms.euclidean.pair_errors);
    const note = document.createElement('p');
    note.className = 'mt-note';
    note.innerHTML = `Подія помилки — ділянка, де шлях Вітербі відходить від переданого шляху решітки і потім повертається на нього. У цьому кадрі: Хемінг — <strong>${h.count}</strong> подій (середня довжина ${num(h.meanLength, 1)}, найдовша ${h.maxLength}), Евклід — <strong>${e.count}</strong> (${num(e.meanLength, 1)}, ${e.maxLength}). Одна хибна гілка тягне за собою кілька тактів, доки шляхи не зійдуться.`;
    body.append(note);
  }

  function eventMap(f, k) {
    const W = 1200, H = 54, left = 70, right = 16;
    const node = svg(W, H, 'Карта подій помилок у кадрі');
    const X = s => left + s / f.size * (W - left - right);
    [['hamming', 6, C.hamming, 'Хемінг'], ['euclidean', 28, C.euclid, 'Евклід']].forEach(([arm, y, color, label]) => {
      add(node, 'rect', {x: left, y, width: W - left - right, height: 18, fill: '#f4f7f8'});
      add(node, 'text', {x: left - 8, y: y + 13, 'text-anchor': 'end', style: `font-weight:700;fill:${color}`}, label);
      for (const e of f.arms[arm].events) {
        const r = add(node, 'rect', {x: X(e.start), y, width: Math.max(2, X(e.stop) - X(e.start)), height: 18, fill: color, style: 'cursor:pointer'});
        add(r, 'title', {}, `Подія ${e.start}…${e.stop - 1}`);
        r.addEventListener('click', ev => { ev.stopPropagation(); goTo(e.start); });
      }
    });
    add(node, 'rect', {x: X(k) - 1, y: 2, width: 2, height: H - 4, fill: '#f59e0b'});
    node.addEventListener('click', e => {
      const box = node.getBoundingClientRect();
      const s = ((e.clientX - box.left) / box.width * W - left) / (W - left - right) * f.size;
      if (s >= 0 && s < f.size) goTo(Math.floor(s));
    });
    return node;
  }

  function wideTrellis(f, arm, a, b, k) {
    const W = 1200, H = 150, left = 70, right = 16, top = 12, bottom = 22;
    const node = svg(W, H, `Решітка ${arm === 'hamming' ? 'Хемінга' : 'Евкліда'}, такти ${a}…${b - 1}`);
    const n = b - a;
    const X = t => left + (t - a) / n * (W - left - right), Y = s => top + s * (H - top - bottom) / 3;
    const color = arm === 'hamming' ? C.hamming : C.euclid;
    for (const [s0, s1] of runs(f.payload_mask.map(p => !p), a, b)) add(node, 'rect', {x: X(s0), y: 0, width: X(s1) - X(s0), height: H - bottom + 4, fill: C.pilot});
    for (const e of f.arms[arm].events) if (e.stop > a && e.start < b) add(node, 'rect', {x: X(Math.max(a, e.start)), y: 0, width: X(Math.min(b, e.stop)) - X(Math.max(a, e.start)), height: H - bottom + 4, fill: C.bad, opacity: 0.12});
    if (k >= a && k < b) add(node, 'rect', {x: X(k), y: 0, width: X(k + 1) - X(k), height: H - bottom + 4, fill: '#f59e0b', opacity: 0.3});
    const dots = n <= 200;
    if (dots) for (let t = a; t <= b; t++) for (let s = 0; s < 4; s++) add(node, 'circle', {cx: X(t), cy: Y(s), r: 1.6, fill: '#b7c4cc'});
    const prev = t => (t === 0 ? 0 : f.true_states[t - 1]);
    const prevDecoded = t => (t === 0 ? 0 : f.arms[arm].decoded_states[t - 1]);
    let truth = '', path = '';
    for (let t = a; t < b; t++) {
      truth += `M${X(t)},${Y(prev(t))}L${X(t + 1)},${Y(f.true_states[t])}`;
      path += `M${X(t)},${Y(prevDecoded(t))}L${X(t + 1)},${Y(f.arms[arm].decoded_states[t])}`;
    }
    add(node, 'path', {d: path, stroke: color, 'stroke-width': 2.6, fill: 'none', 'stroke-linecap': 'round', opacity: 0.9});
    add(node, 'path', {d: truth, stroke: C.ink, 'stroke-width': 1.3, fill: 'none', 'stroke-dasharray': '4 3'});
    f.arms[arm].pair_errors.forEach((err, t) => { if (err && t >= a && t < b) add(node, 'path', {d: `M${X(t)},${Y(prevDecoded(t))}L${X(t + 1)},${Y(f.arms[arm].decoded_states[t])}`, stroke: C.bad, 'stroke-width': 3, fill: 'none'}); });
    for (let s = 0; s < 4; s++) add(node, 'text', {x: left - 8, y: Y(s) + 4, 'text-anchor': 'end', style: 'font-family:ui-monospace,Consolas,monospace'}, f.states[s].join(''));
    const every = Math.max(1, Math.ceil(n / 16));
    for (let t = a; t < b; t += every) add(node, 'text', {x: X(t + 0.5), y: H - 6, 'text-anchor': 'middle', style: `font-size:10.5px;${t === k ? 'font-weight:800;fill:#142433' : ''}`}, String(t));
    node.addEventListener('click', e => {
      const box = node.getBoundingClientRect();
      const t = a + ((e.clientX - box.left) / box.width * W - left) / (W - left - right) * n;
      if (t >= a && t < b) goTo(Math.floor(t));
    });
    return node;
  }

  function eventsCard(f, arm, k) {
    const box = document.createElement('article');
    box.className = 'card ' + (arm === 'hamming' ? 'hamming' : 'euclid');
    const events = f.arms[arm].events;
    const rows = events.map((e, i) => {
      const errs = f.arms[arm].pair_errors.slice(e.start, e.stop).filter(Boolean).length;
      const snr = f.effective_snr_db.slice(e.start, e.stop).filter(v => v !== null);
      const cur = k >= e.start && k < e.stop ? ' class="cur"' : '';
      return `<tr${cur}><td>${i + 1}</td><td>${e.start}…${e.stop - 1}</td><td>${e.stop - e.start}</td><td>${errs}</td><td>${snr.length ? num(Math.min(...snr), 1) : '—'}</td><td><button type="button" data-k="${e.start}">Етапи ›</button></td></tr>`;
    }).join('');
    box.innerHTML = `<h2>${arm === 'hamming' ? 'Події помилок · Хемінг' : 'Події помилок · Евклід'}</h2>${events.length
      ? `<div class="mt-scroll"><table class="mt-events"><thead><tr><th>#</th><th>Такти</th><th>Довжина</th><th>Помилк. симв.</th><th>Мін. SNR, дБ</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : '<p class="mt-note">Шлях декодера в цьому кадрі жодного разу не відійшов від переданого.</p>'}`;
    box.querySelectorAll('button[data-k]').forEach(b => b.addEventListener('click', () => window.metricContext?.openStages(Number(b.dataset.k))));
    return box;
  }

  if (document.readyState === 'complete') build(); else document.addEventListener('DOMContentLoaded', build);
})();
