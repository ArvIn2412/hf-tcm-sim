// «Етапи обробки»: one paired metric-isolation trial, stage by stage.
// Shared stages (transmitter, channel, frontend z_k) span the page; the decision
// stages are split: Hamming (hard decision) on the left, Euclid (soft) on the right.
// Read-only: data come from /api/scientific/metric-trace, whose decoder replay and
// per-symbol metric recomputation are verified on the server.
(() => {
  'use strict';

  const bits3 = m => [(m >> 2) & 1, (m >> 1) & 1, m & 1].join('');
  const popcount3 = x => (x & 1) + ((x >> 1) & 1) + ((x >> 2) & 1);
  /** Branch metric per output label 0..7 (natural labeling: label = phase index). */
  const hammingLabelMetrics = hard => Array.from({length: 8}, (_, m) => popcount3(m ^ hard));
  const euclidLabelMetrics = (distances, weight) => distances.map(d => d * (weight ?? 1));
  function nextIndex(mask, from, direction = 1) {
    for (let i = from + direction; i >= 0 && i < mask.length; i += direction) if (mask[i]) return i;
    return -1;
  }
  function ties(values) {
    const counts = new Map();
    for (const v of values) counts.set(v, (counts.get(v) || 0) + 1);
    return [...counts.entries()].filter(([, n]) => n > 1).sort((a, b) => a[0] - b[0]);
  }
  /**
   * Add-compare-select of one Viterbi step, exactly as run_metric_viterbi does it:
   * candidate = path metric of the source state + branch metric; disallowed inputs
   * (pilot constraint) and unreachable sources are skipped; strict '<' keeps the
   * first edge in table order on ties.
   */
  function acsCandidates(edges, states, prev, branch, allowedPair) {
    const key = st => st.join('');
    const index = new Map(states.map((st, i) => [key(st), i]));
    return states.map((dst, di) => {
      const candidates = [];
      for (const [id, src, pair, out, to] of edges) {
        if (index.get(key(to)) !== di) continue;
        if (allowedPair && key(pair) !== key(allowedPair)) continue;
        const before = prev[index.get(key(src))];
        if (before === null || before === undefined || !Number.isFinite(before)) continue;
        candidates.push({edge: id, from: index.get(key(src)), pair, out, before, branch: branch[id], total: before + branch[id]});
      }
      let winner = null;
      for (const c of candidates) if (!winner || c.total < winner.total) winner = c;
      const tolerance = winner ? 1e-12 * Math.max(1, Math.abs(winner.total)) : 0;
      for (const c of candidates) {
        c.winner = c === winner;
        c.tied = !c.winner && Math.abs(c.total - winner.total) <= tolerance;
      }
      return {state: di, candidates, winner: winner ? winner.edge : null};
    });
  }
  const api = {bits3, hammingLabelMetrics, euclidLabelMetrics, nextIndex, ties, acsCandidates};
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ helpers
  const NS = 'http://www.w3.org/2000/svg';
  const C = {hamming: '#c2410c', euclid: '#0a7f8c', ink: '#142433', muted: '#6a7a87', line: '#dde4e9', grid: '#eef2f4', ok: '#16a34a', bad: '#dc2626', truth: '#142433'};
  const $ = id => document.getElementById(id);
  const num = (v, d = 3) => ((Math.round(Number(v) * 10 ** d) / 10 ** d) || 0).toLocaleString('uk-UA', {minimumFractionDigits: d, maximumFractionDigits: d});
  const esc = s => String(s).replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
  function svg(w, h, label) {
    const node = document.createElementNS(NS, 'svg');
    node.setAttribute('viewBox', `0 0 ${w} ${h}`);
    node.setAttribute('role', 'img');
    node.setAttribute('aria-label', label);
    node.classList.add('st-svg');
    return node;
  }
  function add(parent, tag, attrs = {}, text) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    parent.append(node);
    return node;
  }

  const state = {studies: [], study: '', point: 0, trial: 0, k: 0, data: null, cloud: null, frame: null, config: null, request: 0};

  // ------------------------------------------------------------------ layout
  const css = document.createElement('style');
  css.textContent = `
  .st-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
  .st-controls label{flex-direction:row;align-items:center;gap:6px}
  .st-source{position:relative}
  .st-source>summary{list-style:none;cursor:pointer;min-height:36px;display:flex;align-items:center;padding:0 12px;border:1px solid #cfd8de;background:#fff;font:600 13px Inter,"Segoe UI",sans-serif;color:#142433;white-space:nowrap}
  .st-source>summary::-webkit-details-marker{display:none}
  .st-source>summary::after{content:"▾";margin-left:8px;color:#6a7a87}
  .st-source[open]>summary{border-color:#22364d}
  .st-source-panel{position:absolute;z-index:60;top:calc(100% + 4px);left:0;display:grid;gap:10px;padding:14px;background:#fff;border:1px solid #22364d;box-shadow:0 8px 24px #14243326;min-width:360px}
  .st-source-panel label{flex-direction:column;align-items:stretch}
  .st-source-panel #st-study,.st-source-panel #st-point{width:100%}
  .st-summary{display:flex;gap:8px;align-items:center;font:600 12.5px Inter,"Segoe UI",sans-serif;color:#3f5161;padding-bottom:9px}
  .st-summary .ok{color:#16a34a}.st-summary .bad{color:#dc2626}
  #view-stages .st-acs{margin-top:12px}
  #view-stages .st-acs-head{font:700 12.5px Inter,"Segoe UI",sans-serif;color:#142433;margin-bottom:6px}
  #view-stages .st-acs table{width:100%;border-collapse:collapse;font-size:12px}
  #view-stages .st-acs th{padding:5px 8px;font-size:11px;text-align:left}
  #view-stages .st-acs td{padding:5px 8px;border-bottom:1px solid #eef2f4;vertical-align:top}
  #view-stages .st-acs tr.on-path td{background:#fff9e6}
  #view-stages .st-acs tr.on-path td:first-child{box-shadow:inset 3px 0 0 #142433}
  #view-stages .st-acs-c{display:inline-block;margin:2px 6px 2px 0;padding:2px 7px;border-radius:6px;background:#f4f7f8;color:#6a7a87;font:11.5px ui-monospace,Consolas,monospace;text-decoration:line-through;text-decoration-color:#c5d0d6}
  #view-stages .st-acs-c.win{background:#e5f3f4;color:#142433;text-decoration:none;outline:1.5px solid currentColor}
  #view-stages .st-col.hamming .st-acs-c.win{background:#fbe9df}
  #view-stages .st-acs-c.tie{background:#fdf1dc;color:#92400e;text-decoration:none}
  .st-controls label{min-width:0}
  .st-controls #st-study{width:300px}
  .st-controls #st-point{width:190px}
  .st-controls input{width:96px}
  .st-controls .st-nav{display:flex;gap:6px;align-items:flex-end}
  .st-controls .st-nav button{min-width:38px}
  .st-flags{display:flex;flex-wrap:wrap;gap:6px;margin-left:auto}
  .st-flag{font:600 11.5px Inter,"Segoe UI",sans-serif;padding:5px 10px;border-radius:99px;background:#ecf7ef;color:#1d6b37;border:1px solid #cde8d4}
  .st-flag.warn{background:#fdf6e7;color:#6d5a2c;border-color:#f0dfb6}
  #view-stages .st-shared{display:grid;grid-template-columns:1fr 1.25fr 1fr;gap:14px;margin-bottom:14px}
  #view-stages .st-stage{position:relative;padding:16px 18px}
  #view-stages .st-num{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#e5f3f4;color:#076b76;font:800 11px Inter,sans-serif;margin-right:8px;vertical-align:1px}
  #view-stages .st-stage h3{margin:0 0 10px;font-size:14px}
  #view-stages .st-kv{display:grid;grid-template-columns:auto 1fr;gap:5px 14px;font-size:13px;margin:0}
  #view-stages .st-kv dt{color:#6a7a87}
  #view-stages .st-kv dd{margin:0;font-variant-numeric:tabular-nums;color:#142433;font-weight:600}
  #view-stages .st-mono{font-family:ui-monospace,Consolas,monospace;letter-spacing:.04em}
  #view-stages .st-split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  #view-stages .st-col{display:grid;gap:14px;align-content:start}
  #view-stages .st-colhead{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 18px;border-radius:12px;color:#fff;font-weight:700}
  #view-stages .st-colhead small{font-weight:500;opacity:.9}
  #view-stages .st-col.hamming .st-colhead{background:${C.hamming}}
  #view-stages .st-col.euclid .st-colhead{background:${C.euclid}}
  #view-stages .st-col.hamming .st-stage{border-top:3px solid ${C.hamming}}
  #view-stages .st-col.euclid .st-stage{border-top:3px solid ${C.euclid}}
  #view-stages .st-col.hamming .st-num{background:#fbe9df;color:${C.hamming}}
  #view-stages svg.st-svg{width:100%;height:auto;display:block}
  #view-stages svg.st-svg text{font:12px Inter,"Segoe UI",sans-serif;fill:#3f5161}
  #view-stages .st-note:empty{display:none}
  #view-stages .st-note{margin:10px 0 0;font-size:13px;line-height:1.5;color:#3f5161}
  #view-stages .st-note strong{color:#142433}
  #view-stages .st-bars{display:grid;gap:4px;font-size:12.5px;font-variant-numeric:tabular-nums}
  #view-stages .st-bar{display:grid;grid-template-columns:44px 1fr 74px;align-items:center;gap:8px}
  #view-stages .st-bar .lbl{font-family:ui-monospace,Consolas,monospace}
  #view-stages .st-bar .track{height:14px;background:#f1f5f7;border-radius:4px;overflow:hidden}
  #view-stages .st-bar .fill{height:100%;border-radius:4px}
  #view-stages .st-bar .val{text-align:right;color:#142433;font-weight:600}
  #view-stages .st-bar.truth .lbl::after{content:" ★";color:#142433}
  #view-stages .st-bar.best .val{text-decoration:underline}
  #view-stages .st-strip{display:grid;gap:3px;font:12px ui-monospace,Consolas,monospace;overflow-x:auto}
  #view-stages .st-strip .row{display:flex;gap:3px;align-items:center}
  #view-stages .st-strip .row>span:first-child{width:84px;flex:none;font:600 11.5px Inter,sans-serif;color:#6a7a87}
  #view-stages .st-strip .cell{width:25px;font-size:11px;flex:none;text-align:center;padding:3px 0;border-radius:4px;background:#f4f7f8}
  #view-stages .st-strip .cell.bad{background:#fde8e8;color:${C.bad};font-weight:700}
  #view-stages .st-strip .cell.cur{outline:2px solid #142433}
  #view-stages .st-strip .cell.pilot{background:#eef2f4;color:#9aa9b4}
  #view-stages .st-legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#6a7a87;margin-top:8px}
  #view-stages .st-legend i{display:inline-block;width:18px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}
  #view-stages .st-empty-msg{padding:30px;text-align:center;color:#6a7a87}
  @media(max-width:1180px){#view-stages .st-shared{grid-template-columns:1fr 1fr}#view-stages .st-shared>:last-child{grid-column:1/-1}}`;
  document.head.append(css);

  let section, tab;
  function build() {
    section = document.createElement('section');
    section.className = 'view';
    section.id = 'view-stages';
    section.innerHTML = `
      <h1>Хемінг і Евклід: етап за етапом</h1>
      <div class="st-controls" role="toolbar" aria-label="Кадр і символ для вкладок порівняння метрик">
        <label>Дослідження<select id="st-study"></select></label>
        <label>Рівень енергії<select id="st-point"></select></label>
        <label>Кадр<input id="st-trial" type="number" min="0" value="0"></label>
        <label>Символ k<input id="st-k" type="number" min="0" value="0"></label>
        <div class="st-nav">
          <button type="button" id="st-prev" aria-label="Попередній символ">‹</button>
          <button type="button" id="st-next" aria-label="Наступний символ">›</button>
          <button type="button" id="st-next-h" title="Наступний символ, де помиляється Хемінг">Помилка Хемінга ›</button>
          <button type="button" id="st-next-e" title="Наступний символ, де помиляється Евклід">Помилка Евкліда ›</button>
          <button type="button" id="st-next-d" title="Наступний символ, де рішення двох декодерів різні">Розбіжність ›</button>
        </div>
        <div class="st-summary" id="st-summary" aria-live="polite"></div>
        <div class="st-flags" id="st-flags"></div>
      </div>
      <div id="st-body"><div class="card st-empty-msg">Оберіть дослідження з режиму «Метрики». Якщо їх ще немає — запустіть експеримент.</div></div>`;
    document.querySelector('main').append(section);
    const header = document.querySelector('header.topbar');
    const bar = section.querySelector('.st-controls');
    header.insertBefore(bar, header.querySelector('.sync-toolbar'));
    // Study / energy level / frame rarely change: keep them behind one compact source button.
    const source = document.createElement('details');
    source.className = 'st-source';
    source.innerHTML = '<summary id="st-source-label">Джерело</summary><div class="st-source-panel"></div>';
    const panel = source.querySelector('.st-source-panel');
    for (const id of ['st-study', 'st-point', 'st-trial']) panel.append($(id).closest('label'));
    bar.prepend(source);
    document.addEventListener('click', e => { if (source.open && !source.contains(e.target)) source.open = false; });

    tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'tab';
    tab.dataset.view = 'stages';
    tab.textContent = 'Етапи обробки';
    const after = document.querySelector('.tabs .tab[data-view="parameters"]');
    after ? after.after(tab) : document.querySelector('.tabs').append(tab);

    const hide = () => { section.classList.remove('active'); tab.classList.remove('active'); };
    tab.addEventListener('click', () => { if (location.hash !== '#stages') history.pushState(null, '', '#stages'); show(); });
    document.querySelectorAll('.tabs .tab').forEach(t => { if (t !== tab) t.addEventListener('click', hide); });
    for (const name of ['scientific-view', 'scientific-navigate', 'hashchange', 'popstate'])
      window.addEventListener(name, () => { if (location.hash === '#stages') setTimeout(show, 0); else hide(); });

    $('st-study').addEventListener('change', () => { state.study = $('st-study').value; state.point = 0; state.trial = 0; state.k = 0; state.frame = null; load(); });
    $('st-point').addEventListener('change', () => { state.point = Number($('st-point').value); state.frame = null; load(); });
    $('st-trial').addEventListener('change', () => { state.trial = snapTrial($('st-trial').value); $('st-trial').value = state.trial; state.frame = null; load(); });
    $('st-k').addEventListener('change', () => goTo(Number($('st-k').value)));
    $('st-prev').addEventListener('click', () => goTo(state.k - 1));
    $('st-next').addEventListener('click', () => goTo(state.k + 1));
    const jump = mask => { if (!mask) return; const i = nextIndex(mask, state.k); if (i >= 0) goTo(i); else flash('Далі таких символів у кадрі немає.'); };
    $('st-next-h').addEventListener('click', () => jump(state.frame?.hammingErrors));
    $('st-next-e').addEventListener('click', () => jump(state.frame?.euclidErrors));
    $('st-next-d').addEventListener('click', () => jump(state.frame?.disagree));
    document.addEventListener('keydown', e => {
      if (!METRIC_VIEWS.includes(document.body.dataset.view) || (e.target instanceof Element && e.target.matches('input,select,textarea'))) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); goTo(state.k + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(state.k - 1); }
    });
    if (location.hash === '#stages') show();
  }

  function show() {
    document.querySelectorAll('main > .view').forEach(v => v.classList.toggle('active', v === section));
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.toggle('active', t === tab));
    document.body.classList.remove('r4-on');
    refreshStudies();
  }

  function flash(text) {
    const flags = $('st-flags');
    const note = document.createElement('span');
    note.className = 'st-flag warn';
    note.textContent = text;
    flags.prepend(note);
    setTimeout(() => note.remove(), 2500);
  }

  async function refreshStudies() {
    try {
      const [mine, exp04] = await Promise.all([
        fetch('/api/scientific/metric-studies').then(r => r.json()),
        fetch('/api/scientific/exp04-frames').then(r => (r.ok ? r.json() : {cells: []})).catch(() => ({cells: []})),
      ]);
      const studies = (mine.studies || []).filter(s => s.contrast_id === 'metric_isolation' && s.completed_trials > 0);
      const cells = exp04.cells || [];
      const signature = studies.map(s => s.experiment_id).join() + '|' + cells.map(c => c.experiment_id).join();
      const changed = signature !== state.signature;
      const known = new Set(state.studies.map(s => s.experiment_id));
      const fresh = state.studies.length > 0 && studies.length > 0 && !known.has(studies[0].experiment_id);
      state.studies = studies;
      state.exp04 = Object.fromEntries(cells.map(c => [c.experiment_id, c]));
      state.signature = signature;
      if (changed) {
        const groups = [];
        if (studies.length) {
          const g = document.createElement('optgroup');
          g.label = 'Мої запуски';
          g.append(...studies.map(s => new Option(`${s.experiment_id} · ${s.completed_trials} кадр.`, s.experiment_id)));
          groups.push(g);
        }
        if (cells.length) {
          const g = document.createElement('optgroup');
          g.label = 'EXP-04 · підтверджувальна серія';
          g.append(...cells.map(c => new Option(`${c.cell} · ${c.trials_per_point} кадр./рівень`, c.experiment_id)));
          groups.push(g);
        }
        $('st-study').replaceChildren(...groups);
      }
      const all = [...studies.map(s => s.experiment_id), ...cells.map(c => c.experiment_id)];
      if (!all.length) return;
      if (!state.study || !all.includes(state.study) || fresh || (changed && !state.data && studies.length && studies[0].experiment_id !== state.study)) {
        const next = studies[0]?.experiment_id ?? all[0];
        if (state.study !== next) { state.point = 0; state.trial = 0; state.k = 0; state.frame = null; }
        state.study = next;
      }
      $('st-study').value = state.study;
      if (!state.data || state.data.study_id !== state.study) load();
    } catch (error) {
      $('st-body').innerHTML = `<div class="card st-empty-msg">Не вдалося отримати список досліджень: ${esc(error.message)}</div>`;
    }
  }

  /** Frame stride of a study: EXP-04 keeps full arrays only for every 100th frame. */
  const strideOf = study => state.exp04?.[study]?.full_array_stride ?? 1;
  function snapTrial(value) {
    const stride = strideOf(state.study);
    return Math.max(0, Math.round((Number(value) || 0) / stride) * stride);
  }

  /** Open a given study/point/frame and optionally jump to the first disagreement. */
  async function open({study, point = 0, trial = 0, k = 0, jumpTo = null}) {
    if (!state.signature) await refreshStudies();
    state.study = study;
    state.point = point;
    state.trial = trial;
    state.k = k;
    state.frame = null;
    state.pendingJump = jumpTo;
    $('st-study').value = study;
    $('st-trial').value = trial;
    await load();
  }

  function goTo(k) {
    if (!state.frame) return;
    state.k = Math.max(0, Math.min(state.frame.size - 1, Math.floor(k)));
    $('st-k').value = state.k;
    load();
  }

  async function load() {
    if (!state.study) return;
    const version = ++state.request;
    const start = Math.max(0, state.k - 8);
    const q = new URLSearchParams({study_id: state.study, point: state.point, trial: state.trial, start, count: 17, limit: 2000});
    try {
      const response = await fetch('/api/scientific/metric-trace?' + q);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      if (version !== state.request) return;
      state.data = data;
      state.config = data.configuration;
      const size = data.total_symbols;
      const hm = data.arms.hamming, em = data.arms.euclidean;
      state.frame = {
        size,
        hammingErrors: hm.pair_error_mask,
        euclidErrors: em.pair_error_mask,
        disagree: hm.decoded_phases.map((p, i) => p !== em.decoded_phases[i] || hm.pair_error_mask[i] !== em.pair_error_mask[i]),
      };
      if (state.k >= size) { state.k = size - 1; return load(); }
      state.cloud = data.processed;
      fillPoints();
      $('st-k').max = size - 1;
      $('st-k').value = state.k;
      const stride = strideOf(state.study);
      $('st-trial').step = stride;
      $('st-trial').max = Math.max(0, Math.floor(((state.config.trials_per_point || 1) - 1) / stride) * stride);
      $('st-trial').value = state.trial;
      if (state.pendingJump) {
        const jumpTo = state.pendingJump;
        state.pendingJump = null;
        const mask = {disagree: state.frame.disagree, hamming: state.frame.hammingErrors, euclidean: state.frame.euclidErrors}[jumpTo];
        const first = mask ? mask.indexOf(true) : -1;
        if (first >= 0 && first !== state.k) { state.k = first; return load(); }
      }
      render();
      const key = `${state.study}|${state.point}|${state.trial}`;
      window.dispatchEvent(new CustomEvent('metric-context', {detail: {study: state.study, point: state.point, trial: state.trial, k: state.k, size, frameChanged: key !== state.contextKey}}));
      state.contextKey = key;
    } catch (error) {
      if (version !== state.request) return;
      state.data = null;
      $('st-body').innerHTML = `<div class="card st-empty-msg">${esc(error.message)}</div>`;
    }
  }

  function fillPoints() {
    const grid = state.config.energy_grid_db || [0];
    const gamma = state.data.record.gamma_b_discrete_db;
    const select = $('st-point');
    const known = state.exp04?.[state.study]?.eb_n0_grid_db;
    const options = grid.map((_, i) => new Option(known ? `Eb/N0 ${num(known[i], 1)} дБ` : i === state.point ? `#${i + 1} · Eb/N0 ${num(gamma, 1)} дБ` : `#${i + 1} з ${grid.length}`, i));
    select.replaceChildren(...options);
    select.value = state.point;
  }

  // ------------------------------------------------------------------ render
  function render() {
    const d = state.data;
    const i = state.k - d.start;
    const fw = d.frontend_window[i];
    const A = d.amplitude;
    const tx = d.transmitter;
    const truth = d.tx_phases[i];
    const hard = fw.hard_phase;
    const weight = fw.csi_weight;
    const hmMetrics = hammingLabelMetrics(hard);
    const euMetrics = euclidLabelMetrics(fw.distances, weight);
    const hmDecided = d.arms.hamming.decoded_phases[state.k];
    const euDecided = d.arms.euclidean.decoded_phases[state.k];
    const hmErr = state.frame.hammingErrors[state.k], euErr = state.frame.euclidErrors[state.k];

    const verified = d.pairing_verified && d.replay_verified;
    const chip = document.createElement('span');
    chip.className = 'st-flag' + (verified ? '' : ' warn');
    chip.textContent = verified ? '✓ перевірено' : '! не перевірено';
    chip.title = 'Обидва декодери отримали той самий z_k; рішення Вітербі відтворено; метрики перераховано з z_k';
    $('st-flags').replaceChildren(chip);
    const cellName = state.exp04?.[state.study]?.cell;
    const level = state.exp04?.[state.study]?.eb_n0_grid_db?.[state.point] ?? d.record.gamma_b_discrete_db;
    $('st-source-label').textContent = `${cellName ? 'EXP-04 ' + cellName : state.study} · ${num(level, 1)} дБ · кадр ${state.trial}`;

    const mark = (decided, wrong) => fw.pilot ? 'пілот' : `${bits3(decided)} <span class="${wrong ? 'bad' : 'ok'}">${wrong ? '✗' : '✓'}</span>`;
    $('st-summary').innerHTML = `<span class="st-mono">${bits3(truth)}</span> → Хемінг ${mark(hmDecided, hmErr)}, Евклід ${mark(euDecided, euErr)}`;
    $('st-summary').title = `Символ ${state.k} з ${state.frame.size - 1}; передано ${bits3(truth)}`;
    const body = $('st-body');
    body.replaceChildren();
    const shared = document.createElement('div');
    shared.className = 'st-shared';
    body.append(shared);

    // 1 transmitter
    const pre = tx.pre_states[i], post = tx.post_states[i];
    const s1 = card(shared, 1, 'Передавач: кодер TCM і 8PSK');
    s1.insertAdjacentHTML('beforeend', `<dl class="st-kv">
      <dt>Елемент</dt><dd>k = ${state.k}${fw.pilot ? ' · пілот (відомий)' : ' · дані'}</dd>
      <dt>Інформаційні біти u</dt><dd class="st-mono">${tx.input_pairs[i].join('')}</dd>
      <dt>Стан кодера</dt><dd class="st-mono">${pre.join('')} → ${post.join('')}</dd>
      <dt>Кодові біти c</dt><dd class="st-mono">${tx.coded_triples[i].join('')}</dd>
      <dt>Точка 8PSK</dt><dd>m = ${truth} · s = ${num(A * Math.cos(truth * Math.PI / 4))} ${A * Math.sin(truth * Math.PI / 4) < 0 ? '−' : '+'} j${num(Math.abs(A * Math.sin(truth * Math.PI / 4)))}</dd></dl>
`);

    // 2 channel
    const s2 = card(shared, 2, 'Канал: 8 відліків елемента');
    s2.append(samplesPlot(tx, i));
    s2.insertAdjacentHTML('beforeend', `<div class="st-legend"><span><i style="border-color:#7c8b96"></i>TX (передано)</span><span><i style="border-color:#7c3aed"></i>RX I</span><span><i style="border-color:#db2777"></i>RX Q</span></div>
      <p class="st-note">${esc(channelText())}</p>`);

    // 3 frontend
    const z = fw.z, zAbs = Math.hypot(z[0], z[1]);
    const sTrue = [A * Math.cos(truth * Math.PI / 4), A * Math.sin(truth * Math.PI / 4)];
    const shift = Math.hypot(z[0] - sTrue[0], z[1] - sTrue[1]);
    const s3 = card(shared, 3, 'Фронтенд: спільний вихід z_k');
    s3.insertAdjacentHTML('beforeend', `<dl class="st-kv">
      <dt>Тракт</dt><dd>${esc(tractText())}</dd>
      <dt>z_k</dt><dd>${num(z[0])} ${z[1] < 0 ? '−' : '+'} j${num(Math.abs(z[1]))}</dd>
      <dt>|z_k|, arg z_k</dt><dd>${num(zAbs)} · ${num(Math.atan2(z[1], z[0]) * 180 / Math.PI, 1)}°</dd>
      <dt>Зміщення від s</dt><dd>|z_k − s| = ${num(shift)} (${num(shift / A * 100, 0)} % амплітуди)</dd>
      <dt>Вага тракту P_k</dt><dd>${weight === undefined ? '— (пілот)' : num(weight, 2)}</dd></dl>
`);

    // split columns
    const split = document.createElement('div');
    split.className = 'st-split';
    body.append(split);
    const verdict = (decided, wrong) => `k = ${state.k}: ${bits3(decided)} ${wrong ? '✗ помилка' : '✓'}`;
    const left = column(split, 'hamming', 'Хемінг · роздільне приймання', fw.pilot ? 'пілот — вхід відомий' : verdict(hmDecided, hmErr));
    const right = column(split, 'euclid', 'Евклід · спільне приймання', fw.pilot ? 'пілот — вхід відомий' : verdict(euDecided, euErr));

    // 4 decision
    const h4 = card(left, 4, 'Жорстке рішення на сузір’ї');
    h4.append(constellation('hamming', fw, A, truth));
    h4.insertAdjacentHTML('beforeend', `<p class="st-note">Сектор <strong class="st-mono">${bits3(hard)}</strong>${hard === truth ? ' = передано' : ` ≠ передано <strong style="color:${C.bad}" class="st-mono">${bits3(truth)}</strong>`}; відстань ${num(Math.sqrt(fw.distances[hard]))} відкинуто</p>`);
    const e4 = card(right, 4, 'М’яке рішення: відстані до всіх точок');
    e4.append(constellation('euclid', fw, A, truth));
    const order = [...fw.distances.keys()].sort((a, b) => fw.distances[a] - fw.distances[b]);
    e4.insertAdjacentHTML('beforeend', `<p class="st-note">Найближча <strong class="st-mono">${bits3(order[0])}</strong> d² = ${num(fw.distances[order[0]])}; друга <strong class="st-mono">${bits3(order[1])}</strong> d² = ${num(fw.distances[order[1]])}</p>`);

    // 5 branch metrics
    const h5 = card(left, 5, 'Метрики гілок за мітками (0…3)');
    h5.append(bars(hmMetrics, truth, 'hamming', v => String(v)));
    const hTies = ties(hmMetrics);
    h5.insertAdjacentHTML('beforeend', `<p class="st-note">Рівні метрики: ${hTies.map(([v, n]) => `<strong>${n}</strong> × ${v}`).join(', ')}</p>`);
    const e5 = card(right, 5, `Метрики гілок за мітками${weight !== undefined ? ' (P_k·d²)' : ''}`);
    e5.append(bars(euMetrics, truth, 'euclid', v => num(v, 2)));
    const ratio = fw.distances[order[1]] / Math.max(fw.distances[order[0]], 1e-12);
    e5.insertAdjacentHTML('beforeend', `<p class="st-note">Друга / перша: <strong>${num(ratio, 1)}</strong>; P_k = ${weight === undefined ? '—' : num(weight, 2)}</p>`);

    // 6 trellis
    const h6 = card(left, 6, 'Вітербі: кандидати, вибір і шлях');
    h6.append(trellis('hamming'));
    h6.insertAdjacentHTML('beforeend', trellisLegend('hamming'));
    h6.append(acsTable('hamming'));
    const e6 = card(right, 6, 'Вітербі: кандидати, вибір і шлях');
    e6.append(trellis('euclidean'));
    e6.insertAdjacentHTML('beforeend', trellisLegend('euclid'));
    e6.append(acsTable('euclidean'));

    // 7 result
    const h7 = card(left, 7, 'Результат декодування');
    h7.append(strip('hamming'));
    h7.insertAdjacentHTML('beforeend', resultNote('hamming', hmDecided, truth, hmErr));
    const e7 = card(right, 7, 'Результат декодування');
    e7.append(strip('euclidean'));
    e7.insertAdjacentHTML('beforeend', resultNote('euclidean', euDecided, truth, euErr));
  }

  function card(parent, n, title) {
    const node = document.createElement('article');
    node.className = 'card st-stage';
    node.innerHTML = `<h3><span class="st-num">${n}</span>${title}</h3>`;
    parent.append(node);
    return node;
  }
  function column(parent, cls, title, sub) {
    const col = document.createElement('div');
    col.className = 'st-col ' + cls;
    col.innerHTML = `<div class="st-colhead"><span>${title}</span><small>${sub}</small></div>`;
    parent.append(col);
    return col;
  }
  function channelText() {
    const c = state.config.channel_config || {};
    const paths = c.paths || [];
    const fading = {constant: 'без завмирань', rician_ar1: 'Райс AR(1)', rician_doppler: `Доплер ${c.doppler_spread_hz ?? ''} Гц`}[c.fading_mode] || c.fading_mode || '';
    return `${paths.length} пром. (затримки ${paths.map(p => p.delay_samples).join(', ')} відл.), ${fading}, σ² = ${c.noise_complex_variance ?? '—'}`;
  }
  function tractText() {
    const mode = {known_channel: 'відомий тракт (точні коефіцієнти)', pilot_equalized: 'оцінка за пілотами', awgn_direct_control: 'прямий (AWGN)', oracle_csi: 'діагностичний oracle'}[state.config.frontend_mode] || state.config.frontend_mode;
    return mode + (state.config.euclidean_metric === 'csi_weighted' ? ', метрика зважена' : '');
  }

  function samplesPlot(tx, i) {
    const w = 420, h = 170, pad = 28;
    const node = svg(w, h, 'Передані й прийняті відліки елемента');
    const slice = arr => arr.slice(i * 8, i * 8 + 8);
    const series = [[slice(tx.tx_i), '#7c8b96', 'TX I', '4 3'], [slice(tx.tx_q), '#7c8b96', 'TX Q', '1 3'], [slice(tx.rx_i), '#7c3aed', 'RX I'], [slice(tx.rx_q), '#db2777', 'RX Q']];
    const max = Math.max(1e-9, ...series.flatMap(s => s[0].map(Math.abs))) * 1.1;
    const x = j => pad + j * (w - pad - 8) / 8, y = v => h / 2 - v / max * (h / 2 - 14);
    add(node, 'line', {x1: pad, x2: w - 8, y1: y(0), y2: y(0), stroke: C.line});
    for (let j = 0; j <= 8; j++) add(node, 'line', {x1: x(j), x2: x(j), y1: 8, y2: h - 18, stroke: C.grid});
    add(node, 'text', {x: 2, y: y(0) + 4}, '0');
    const A = state.data.amplitude;
    for (const v of [A * Math.SQRT1_2, -A * Math.SQRT1_2, A, -A]) if (Math.abs(v) < max) {
      add(node, 'line', {x1: pad, x2: w - 8, y1: y(v), y2: y(v), stroke: C.grid, 'stroke-dasharray': '2 3'});
      add(node, 'text', {x: 2, y: y(v) + 4, style: 'font-size:10px'}, (v < 0 ? '−' : '') + (Math.abs(Math.abs(v) - A) < 1e-9 ? 'A' : 'A/√2'));
    }
    add(node, 'text', {x: w / 2, y: h - 3, 'text-anchor': 'middle'}, 'відлік 0…7 елемента k');
    for (const [values, color, , dash] of series) {
      let d = '';
      values.forEach((v, j) => { d += `${j ? 'L' : 'M'}${x(j)},${y(v)} L${x(j + 1)},${y(v)} `; });
      add(node, 'path', {d, fill: 'none', stroke: color, 'stroke-width': dash ? 1.5 : 2, 'stroke-dasharray': dash || 'none'});
    }
    return node;
  }

  function constellation(arm, fw, A, truth) {
    const size = 380, c = size / 2, padX = 50;
    const z = fw.z;
    const range = Math.max(1.55 * A, Math.hypot(z[0], z[1]) * 1.15);
    const sc = (size / 2 - 34) / range;
    const X = v => c + v * sc, Y = v => c - v * sc;
    const node = svg(size, size, arm === 'hamming' ? 'Жорстке рішення на сузір’ї 8PSK' : 'Евклідові відстані на сузір’ї 8PSK');
    node.setAttribute('viewBox', `${-padX} 0 ${size + 2 * padX} ${size}`);
    add(node, 'line', {x1: 10, x2: size - 10, y1: c, y2: c, stroke: C.line});
    add(node, 'line', {x1: c, x2: c, y1: 10, y2: size - 10, stroke: C.line});
    add(node, 'circle', {cx: c, cy: c, r: A * sc, fill: 'none', stroke: C.grid, 'stroke-width': 1.5});
    add(node, 'text', {x: size - 14, y: c - 6}, 'I');
    add(node, 'text', {x: c + 6, y: 18}, 'Q');
    const color = arm === 'hamming' ? C.hamming : C.euclid;
    // decision sectors (Hamming) — boundaries halfway between neighbouring phases
    if (arm === 'hamming') {
      for (let m = 0; m < 8; m++) {
        const a = (m + 0.5) * Math.PI / 4;
        add(node, 'line', {x1: c, y1: c, x2: X(range * 1.4 * Math.cos(a)), y2: Y(range * 1.4 * Math.sin(a)), stroke: '#e7d3c6', 'stroke-dasharray': '4 4'});
      }
      const a0 = (fw.hard_phase - 0.5) * Math.PI / 4, a1 = (fw.hard_phase + 0.5) * Math.PI / 4, R = range * 1.4 * sc;
      add(node, 'path', {d: `M${c},${c} L${c + R * Math.cos(a0)},${c - R * Math.sin(a0)} A${R},${R} 0 0 0 ${c + R * Math.cos(a1)},${c - R * Math.sin(a1)} Z`, fill: '#c2410c14'});
    }
    // faint cloud of the whole frame
    for (const p of state.cloud || []) {
      const hardP = nearestPhase(p.i, p.q);
      const wrong = hardP !== p.tx_phase;
      add(node, 'circle', {cx: X(p.i), cy: Y(p.q), r: 1.8, fill: arm === 'hamming' && wrong ? '#dc262666' : '#5b6b7733'});
    }
    // Euclid: lines to all candidate points with squared distances
    const pts = Array.from({length: 8}, (_, m) => [A * Math.cos(m * Math.PI / 4), A * Math.sin(m * Math.PI / 4)]);
    if (arm === 'euclid') {
      const order = [...fw.distances.keys()].sort((a, b) => fw.distances[a] - fw.distances[b]);
      order.slice().reverse().forEach((m, rank) => {
        const best = m === order[0];
        add(node, 'line', {x1: X(z[0]), y1: Y(z[1]), x2: X(pts[m][0]), y2: Y(pts[m][1]), stroke: best ? C.euclid : '#9fb3bd', 'stroke-width': best ? 2.5 : 1, opacity: best ? 1 : 0.35 + 0.08 * rank});
      });
    } else {
      const p = pts[fw.hard_phase];
      add(node, 'defs', {}).innerHTML = `<marker id="st-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${C.hamming}"/></marker>`;
      const dx = X(p[0]) - X(z[0]), dy = Y(p[1]) - Y(z[1]), len = Math.hypot(dx, dy);
      if (len > 14) add(node, 'line', {x1: X(z[0]), y1: Y(z[1]), x2: X(p[0]) - dx / len * 10, y2: Y(p[1]) - dy / len * 10, stroke: C.hamming, 'stroke-width': 2.5, 'marker-end': 'url(#st-arrow)'});
    }
    // constellation points with labels
    pts.forEach(([pi, pq], m) => {
      const decided = arm === 'hamming' && m === fw.hard_phase;
      add(node, 'circle', {cx: X(pi), cy: Y(pq), r: decided ? 8 : 6, fill: decided ? C.hamming : '#fff', stroke: decided ? C.hamming : '#5b6b77', 'stroke-width': 1.6});
      if (m === truth) add(node, 'circle', {cx: X(pi), cy: Y(pq), r: 12, fill: 'none', stroke: C.truth, 'stroke-width': 1.5, 'stroke-dasharray': '3 2'});
      const a = m * Math.PI / 4, lr = A * sc + 24;
      const tx = c + lr * Math.cos(a), ty = c - lr * Math.sin(a);
      const label = arm === 'euclid' ? `${bits3(m)} · ${num(fw.distances[m], 2)}` : bits3(m);
      add(node, 'text', {x: tx, y: ty + 4, 'text-anchor': Math.abs(Math.cos(a)) < 0.3 ? 'middle' : Math.cos(a) > 0 ? 'start' : 'end', style: `font-family:ui-monospace,Consolas,monospace;font-weight:${decided ? 800 : 500};fill:${decided ? C.hamming : '#3f5161'}`}, label);
    });
    // the received decision variable z_k
    const zx = X(z[0]), zy = Y(z[1]), r = 7;
    add(node, 'path', {d: `M${zx},${zy - r} L${zx + r},${zy} L${zx},${zy + r} L${zx - r},${zy} Z`, fill: '#142433', stroke: '#fff', 'stroke-width': 1.5});
    const away = Math.atan2(-(z[1]), z[0]);
    add(node, 'text', {x: zx + 12 * Math.cos(away) + (Math.cos(away) >= 0 ? 4 : -4), y: zy + 12 * Math.sin(away) + 4, 'text-anchor': Math.cos(away) >= 0 ? 'start' : 'end', style: 'font-weight:800;fill:#142433;paint-order:stroke;stroke:#fff;stroke-width:3px'}, 'z_k');
    return node;
  }
  function nearestPhase(i, q) {
    const A = state.data.amplitude;
    let best = 0, bestD = Infinity;
    for (let m = 0; m < 8; m++) { const d = (i - A * Math.cos(m * Math.PI / 4)) ** 2 + (q - A * Math.sin(m * Math.PI / 4)) ** 2; if (d < bestD - 1e-15) { bestD = d; best = m; } }
    return best;
  }

  function bars(values, truth, arm, fmt) {
    const box = document.createElement('div');
    box.className = 'st-bars';
    const max = Math.max(...values, 1e-12);
    const min = Math.min(...values);
    values.forEach((v, m) => {
      const row = document.createElement('div');
      row.className = 'st-bar' + (m === truth ? ' truth' : '') + (v === min ? ' best' : '');
      row.innerHTML = `<span class="lbl">${bits3(m)}</span><span class="track"><span class="fill" style="display:block;width:${Math.max(1.5, v / max * 100)}%;background:${arm === 'hamming' ? C.hamming : C.euclid};opacity:${v === min ? 1 : 0.55}"></span></span><span class="val">${fmt(v)}</span>`;
      box.append(row);
    });
    return box;
  }

  function trellis(arm) {
    const d = state.data, a = d.arms[arm];
    const n = d.stop - d.start;
    const w = 560, h = 236, left = 40, right = 14, top = 18, bottom = 34;
    const node = svg(w, h, 'Фрагмент решітки Вітербі з кандидатами вибору');
    const X = t => left + t * (w - left - right) / n, Y = s => top + s * (h - top - bottom) / 3;
    const color = arm === 'hamming' ? C.hamming : C.euclid;
    const stateIndex = st => d.states.findIndex(s => s.join('') === st.join(''));
    const edgeById = new Map(d.edges.map(e => [e[0], e]));
    const kx = state.k - d.start;
    const allowed = t => (d.payload_mask[t] ? null : d.transmitter.input_pairs[t]);
    add(node, 'rect', {x: X(kx), y: top - 10, width: X(kx + 1) - X(kx), height: h - top - bottom + 20, fill: '#fff5d6'});
    // every possible transition (pilot steps: only the known input); parallel edges share a line
    for (let t = 0; t < n; t++) {
      const drawn = new Set();
      for (const e of d.edges) {
        const pair = allowed(t);
        if (pair && e[2].join('') !== pair.join('')) continue;
        const key = `${stateIndex(e[1])}:${stateIndex(e[4])}`;
        if (drawn.has(key)) continue;
        drawn.add(key);
        add(node, 'line', {x1: X(t), y1: Y(stateIndex(e[1])), x2: X(t + 1), y2: Y(stateIndex(e[4])), stroke: '#e9eef1', 'stroke-width': 1});
      }
    }
    // survivors chosen at every step (one per destination state)
    a.survivors.forEach((row, t) => row.forEach(id => {
      if (id < 0) return;
      const e = edgeById.get(id);
      add(node, 'line', {x1: X(t), y1: Y(stateIndex(e[1])), x2: X(t + 1), y2: Y(stateIndex(e[4])), stroke: '#9fb0ba', 'stroke-width': 1.3});
    }));
    // competing candidates at step k: losers dashed, winners solid; parallel edges as arcs
    const acs = acsCandidates(d.edges, d.states, a.state_metrics[kx], a.branch_metrics[kx], allowed(kx));
    for (const group of acs) for (const c of group.candidates) {
      const e = edgeById.get(c.edge);
      const x1 = X(kx), y1 = Y(c.from), x2 = X(kx + 1), y2 = Y(group.state);
      const twin = group.candidates.filter(o => o.from === c.from);
      const bend = twin.length > 1 ? (twin.indexOf(c) === 0 ? -9 : 9) : 0;
      const mx = (x1 + x2) / 2 - (y2 - y1) / Math.hypot(x2 - x1, y2 - y1 || 1) * bend, my = (y1 + y2) / 2 + (x2 - x1) / Math.hypot(x2 - x1, y2 - y1 || 1) * bend;
      const path = add(node, 'path', {d: `M${x1},${y1} Q${mx},${my} ${x2},${y2}`, fill: 'none', stroke: c.winner ? color : c.tied ? '#b45309' : color, 'stroke-width': c.winner ? 2.2 : 1.4, 'stroke-dasharray': c.winner ? 'none' : '5 3', opacity: c.winner ? 0.95 : 0.6});
      add(path, 'title', {}, `${d.states[c.from].join('')} → ${d.states[group.state].join('')}, u=${e[2].join('')}, c=${e[3].join('')}: ${fmtMetric(c.before, arm)} + ${fmtMetric(c.branch, arm)} = ${fmtMetric(c.total, arm)}${c.winner ? ' (вибрано)' : c.tied ? ' (рівний, відкинуто правилом)' : ' (відкинуто)'}`);
    }
    // true path
    const tx = d.transmitter;
    for (let t = 0; t < n; t++) add(node, 'line', {x1: X(t), y1: Y(stateIndex(tx.pre_states[t])), x2: X(t + 1), y2: Y(stateIndex(tx.post_states[t])), stroke: C.truth, 'stroke-width': 1.5, 'stroke-dasharray': '4 3'});
    // decoded path (delayed decisions)
    a.decoded_edges.forEach((id, t) => {
      const e = edgeById.get(id);
      const wrong = (arm === 'hamming' ? state.frame.hammingErrors : state.frame.euclidErrors)[d.start + t];
      add(node, 'line', {x1: X(t), y1: Y(stateIndex(e[1])), x2: X(t + 1), y2: Y(stateIndex(e[4])), stroke: wrong ? C.bad : color, 'stroke-width': 3.2, 'stroke-linecap': 'round', opacity: 0.9});
    });
    for (let t = 0; t <= n; t++) for (let s = 0; s < 4; s++) {
      const reachable = a.state_metrics[t]?.[s] !== null;
      add(node, 'circle', {cx: X(t), cy: Y(s), r: 2.7, fill: reachable ? '#5b6b77' : '#fff', stroke: '#5b6b77', 'stroke-width': reachable ? 0 : 1});
    }
    // path metrics entering step k
    for (let s = 0; s < 4; s++) {
      const v = a.state_metrics[kx][s];
      if (v !== null) add(node, 'text', {x: X(kx) - 4, y: Y(s) - 5, 'text-anchor': 'end', style: 'font-size:9.5px;font-weight:700;fill:#142433;paint-order:stroke;stroke:#fff5d6;stroke-width:3px'}, fmtMetric(v, arm));
    }
    for (let s = 0; s < 4; s++) add(node, 'text', {x: 4, y: Y(s) + 4, style: 'font-family:ui-monospace,Consolas,monospace'}, d.states[s].join(''));
    for (let t = 0; t < n; t += 2) add(node, 'text', {x: (X(t) + X(t + 1)) / 2, y: h - 16, 'text-anchor': 'middle', style: `font-size:10.5px;${d.start + t === state.k ? 'font-weight:800;fill:#142433' : ''}`}, String(d.start + t));
    add(node, 'text', {x: w / 2, y: h - 2, 'text-anchor': 'middle', style: 'font-size:11px'}, `такти k = ${d.start}…${d.stop - 1}`);
    return node;
  }
  function fmtMetric(v, arm) {
    return arm === 'hamming' ? String(Math.round(v)) : num(v, 2);
  }
  function trellisLegend(arm) {
    const color = arm === 'hamming' ? C.hamming : C.euclid;
    return `<div class="st-legend"><span><i style="border-color:${color}"></i>рішення декодера</span><span><i style="border-color:${C.bad}"></i>помилковий перехід</span><span><i style="border-color:#9fb0ba"></i>вижили на кожному такті</span><span><i style="border-color:${color};border-top-style:dashed"></i>відкинутий кандидат на такті k</span><span><i style="border-color:${C.truth};border-top-style:dashed"></i>переданий шлях</span></div>`;
  }
  function acsTable(arm) {
    const d = state.data, a = d.arms[arm], kx = state.k - d.start;
    const pilot = !d.payload_mask[kx];
    const groups = acsCandidates(d.edges, d.states, a.state_metrics[kx], a.branch_metrics[kx], pilot ? d.transmitter.input_pairs[kx] : null);
    const onPath = d.edges.find(e => e[0] === a.decoded_edges[kx]);
    const pathState = onPath ? d.states.findIndex(s => s.join('') === onPath[4].join('')) : -1;
    const rows = groups.map(g => {
      const cells = g.candidates.map(c => `<span class="st-acs-c${c.winner ? ' win' : ''}${c.tied ? ' tie' : ''}" title="ребро ${c.edge}, u=${c.pair.join('')}, c=${c.out.join('')}">${d.states[c.from].join('')}·${c.pair.join('')}: ${fmtMetric(c.before, arm)} + ${fmtMetric(c.branch, arm)} = <b>${fmtMetric(c.total, arm)}</b></span>`).join('');
      return `<tr class="${g.state === pathState ? 'on-path' : ''}"><td class="st-mono">${d.states[g.state].join('')}</td><td>${cells || '<span class="st-acs-c">недосяжний</span>'}</td></tr>`;
    }).join('');
    const tieCount = groups.reduce((n, g) => n + g.candidates.filter(c => c.tied).length, 0);
    const box = document.createElement('div');
    box.className = 'st-acs';
    box.innerHTML = `<div class="st-acs-head">Вибір на такті k = ${state.k}: метрика стану + метрика гілки</div>
      <table><thead><tr><th>У стан</th><th>Кандидати (переможець виділено)</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="st-note">${pilot ? 'Пілот: лише відомий u. ' : ''}${tieCount ? `<strong style="color:#b45309">Рівних кандидатів: ${tieCount}</strong> — вибрано перше ребро таблиці.` : ''}</p>`;
    return box;
  }

  function strip(arm) {
    const d = state.data, a = d.arms[arm];
    const box = document.createElement('div');
    box.className = 'st-strip';
    const sent = document.createElement('div'), got = document.createElement('div'), idx = document.createElement('div');
    sent.className = got.className = idx.className = 'row';
    idx.innerHTML = '<span>k</span>';
    sent.innerHTML = '<span>Передано u</span>';
    got.innerHTML = '<span>Декодовано û</span>';
    for (let t = 0; t < d.stop - d.start; t++) {
      const k = d.start + t, pilot = !d.payload_mask[t];
      const u = d.transmitter.input_pairs[t].join(''), v = a.bits[t].join('');
      const cur = k === state.k ? ' cur' : '';
      idx.insertAdjacentHTML('beforeend', `<span class="cell${cur}" style="background:none">${k}</span>`);
      sent.insertAdjacentHTML('beforeend', `<span class="cell${pilot ? ' pilot' : ''}${cur}">${u}</span>`);
      got.insertAdjacentHTML('beforeend', `<span class="cell${u !== v ? ' bad' : pilot ? ' pilot' : ''}${cur}">${v}</span>`);
    }
    box.append(idx, sent, got);
    return box;
  }
  function resultNote(arm, decided, truth, wrong) {
    const s = state.data.arms[arm].statistics;
    const errors = (arm === 'hamming' ? state.frame.hammingErrors : state.frame.euclidErrors).filter(Boolean).length;
    return `<p class="st-note">k: <strong class="st-mono">${bits3(decided)}</strong> ${wrong ? `<strong style="color:${C.bad}">помилка</strong>` : '<strong style="color:#16a34a">вірно</strong>'}; кадр: BER ${Number(s.ber) === 0 ? '0' : Number(s.ber).toExponential(2)} (${s.bit_errors} з ${s.bits} біт), помилкових символів ${errors}</p>`;
  }

  const METRIC_VIEWS = ['stages', 'mchannel', 'mdecoding'];
  /** Shared selection for the metric tabs (study · energy point · frame · symbol k). */
  window.metricContext = {
    get: () => ({study: state.study, point: state.point, trial: state.trial, k: state.k, size: state.frame?.size ?? 0}),
    goTo: k => goTo(k),
    refresh: () => refreshStudies(),
    openStages: k => { goTo(k); tab.click(); },
    open: options => open(options),
    showStages: () => tab.click(),
  };

  // Build after system_workspace.js has rebuilt the navigation.
  if (document.readyState === 'complete') build(); else document.addEventListener('DOMContentLoaded', build);
})();
