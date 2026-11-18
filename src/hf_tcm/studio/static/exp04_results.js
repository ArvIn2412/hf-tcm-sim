// «Головний результат»: confirmed SCIENTIFIC-EXP-04 (Hamming vs Euclidean, known tract).
// Read-only view of docs/research/SCIENTIFIC_EXP_04_RESULTS.json served by
// /api/scientific/exp04-results. No trials are run from this tab.
(() => {
  'use strict';

  const CELL_TITLES = {
    'A1-awgn': ['AWGN', 'прямий тракт, без завмирань'],
    'A2-static': ['Статичний 2-променевий', 'відомий тракт, [1; 0,3 − 0,2j]'],
    'A3-itu-moderate': ['ITU moderate · 0,5 Гц', 'відомий тракт, рейліївські завмирання'],
    'A4-itu-poor': ['ITU poor · 1 Гц', 'відомий тракт, рейліївські завмирання'],
    'S1-itu-moderate-unweighted': ['ITU moderate · без ваги', 'як A3, евклідова метрика без CSI-ваги'],
    'S2-itu-moderate-pilot': ['ITU moderate · пілоти', 'як A3, канал оцінюється за пілотами'],
  };
  const VERDICTS = {
    PRECISION_CRITERIA_MET: 'точність достатня',
    INSUFFICIENT_PRECISION: 'недостатня точність',
    ENERGY_GAIN_NOT_ESTIMABLE: 'не оцінюється',
  };

  const dec = (value, digits = 2) => Number(value).toFixed(digits).replace('.', ',');
  const targetKey = target => String(target);

  function qFunction(x) {
    // Abramowitz–Stegun 7.1.26 erfc approximation (|err| < 1.5e-7).
    const z = x / Math.SQRT2;
    const t = 1 / (1 + 0.3275911 * Math.abs(z));
    const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
    const erfc = poly * Math.exp(-z * z);
    return 0.5 * (z >= 0 ? erfc : 2 - erfc);
  }
  const qpskBer = ebN0Db => qFunction(Math.sqrt(2 * 10 ** (ebN0Db / 10)));
  function qpskRequiredDb(target) {
    let lo = -10, hi = 40;
    for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (qpskBer(mid) > target) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }

  function cellRows(cell) {
    return cell.points.map(p => ({
      ebN0: p.eb_n0_db,
      bits: p.bits,
      hamming: p.hamming_errors / p.bits,
      euclidean: p.euclidean_errors / p.bits,
      hammingErrors: p.hamming_errors,
      euclideanErrors: p.euclidean_errors,
    }));
  }

  function superscript(n) {
    const map = {'-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹'};
    return String(n).split('').map(c => map[c]).join('');
  }
  function berLabel(target) {
    const exponent = Math.floor(Math.log10(target) + 1e-9);
    const mantissa = target / 10 ** exponent;
    const power = '10' + superscript(exponent);
    return Math.abs(mantissa - 1) < 1e-9 ? power : `${dec(mantissa, 0)}·${power}`;
  }

  function gainSummary(cell, target) {
    const t = cell.targets[targetKey(target)];
    if (!t || t.gain_db === null || t.verdict === 'ENERGY_GAIN_NOT_ESTIMABLE')
      return {text: 'не оцінюється', ci: '', verdict: 'ENERGY_GAIN_NOT_ESTIMABLE', primary: false, positive: false};
    const ci = Array.isArray(t.ci95_db) ? `[${dec(t.ci95_db[0])}; ${dec(t.ci95_db[1])}]` : '';
    return {
      text: `${dec(t.gain_db)} дБ`,
      ci,
      verdict: t.verdict,
      primary: Number(cell.primary_target_ber) === Number(target),
      positive: Array.isArray(t.ci95_db) && t.ci95_db[0] > 0,
    };
  }

  function hypotheses(bundle) {
    const byId = Object.fromEntries(bundle.cells.map(c => [c.id, c]));
    const primary = bundle.cells.filter(c => c.role === 'primary');
    const h1 = primary.every(c => {
      const g = gainSummary(c, c.primary_target_ber);
      return g.positive && g.verdict === 'PRECISION_CRITERIA_MET';
    });
    const a3 = byId['A3-itu-moderate'], s1 = byId['S1-itu-moderate-unweighted'], s2 = byId['S2-itu-moderate-pilot'];
    let h2 = null, h3 = null;
    if (a3 && s1) {
      const t = targetKey(a3.primary_target_ber);
      h2 = Math.abs(a3.targets[t].required_eb_n0_db.joint - s1.targets[t].required_eb_n0_db.joint);
    }
    if (s2) h3 = gainSummary(s2, s2.primary_target_ber);
    return {h1, h2DifferenceDb: h2, h3};
  }

  function logPlotModel(rows, {width = 760, height = 420, yMin = 1e-6, yMax = 0.5} = {}) {
    const pad = {left: 62, right: 16, top: 16, bottom: 48};
    const xs = rows.map(r => r.ebN0);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const lx = v => pad.left + (v - x0) / (x1 - x0) * (width - pad.left - pad.right);
    const ly = v => pad.top + (Math.log10(yMax) - Math.log10(Math.min(yMax, Math.max(yMin, v)))) /
      (Math.log10(yMax) - Math.log10(yMin)) * (height - pad.top - pad.bottom);
    return {width, height, pad, x0, x1, lx, ly, yMin, yMax};
  }

  const api = {qFunction, qpskBer, qpskRequiredDb, cellRows, gainSummary, berLabel, hypotheses, logPlotModel, CELL_TITLES, VERDICTS};
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof document === 'undefined') return;

  // ---------------------------------------------------------------- DOM part
  const NS = 'http://www.w3.org/2000/svg';
  const COLORS = {hamming: '#c2410c', euclidean: '#087f8c', qpsk: '#6b7785'};
  const state = {bundle: null, cell: 'A1-awgn'};

  // The active shell (system_workspace.js) rebuilds .tabs and stashes unknown views on
  // DOMContentLoaded; this listener is registered later, so it runs after that rebuild.
  let section, tab, mobile;
  function init() {
    const css = document.createElement('style');
    css.textContent = `
    #view-result .r4-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,1fr);gap:16px;align-items:start}
    #view-result .r4-cells{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 14px}
    #view-result .r4-cells button{border:1px solid var(--line);background:#fff;border-radius:99px;padding:8px 13px;font:700 12px inherit;color:#40515c;cursor:pointer}
    #view-result .r4-cells button[aria-pressed=true]{background:var(--teal);border-color:var(--teal);color:#fff}
    #view-result svg.r4-plot{width:100%;height:auto;display:block}
    #view-result svg.r4-plot text{font:12px Inter,"Segoe UI",Arial,sans-serif;fill:#40515c}
    #view-result .r4-kpi{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}
    #view-result .r4-kpi div{background:#f1f6f7;border-radius:12px;padding:12px}
    #view-result .r4-kpi small{display:block;font-size:11px;color:var(--muted);font-weight:700;margin-bottom:4px}
    #view-result .r4-kpi strong{font-size:22px;color:var(--navy);font-variant-numeric:tabular-nums}
    #view-result .r4-kpi span{display:block;font-size:11px;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
    #view-result table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
    #view-result th,#view-result td{padding:9px 8px;border-bottom:1px solid #edf1f2;text-align:right;vertical-align:top}
    #view-result th:first-child,#view-result td:first-child{text-align:left}
    #view-result th{font-size:11px;color:var(--muted);font-weight:800}
    #view-result td small{display:block;color:var(--muted);font-size:11px}
    #view-result td.primary{background:#e9f4f3;font-weight:800;color:#086d78}
    #view-result tr[data-cell]{cursor:pointer}#view-result tr[data-cell]:hover td{background:#f6fafa}
    #view-result .r4-flag{color:#91631a}
    #view-result .r4-h{display:grid;gap:10px}
    #view-result .r4-h article{border-left:4px solid var(--teal)}
    #view-result .r4-h article.r4-desc{border-left-color:#9fb3bd}
    #view-result .r4-h h3{margin:0 0 6px;font-size:14px;color:var(--navy)}
    #view-result .r4-h p{margin:0;font-size:13px;line-height:1.5;color:#40515c}
    #view-result .r4-legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#40515c;margin-top:6px}
    #view-result .r4-legend i{display:inline-block;width:22px;height:3px;vertical-align:middle;margin-right:6px}
    #view-result .r4-meta{font-size:11px;color:var(--muted);line-height:1.6;overflow-wrap:anywhere}
    body.r4-on .sync-toolbar{display:none}
  @media(max-width:1000px){#view-result .r4-grid{grid-template-columns:1fr}}
    @media(max-width:560px){#view-result .r4-kpi{grid-template-columns:1fr}#view-result th,#view-result td{padding:7px 4px}}`;
    document.head.append(css);

    section = document.createElement('section');
    section.className = 'view';
    section.id = 'view-result';
    section.innerHTML = `
      <div class="page-heading"><div><p class="eyebrow">ПІДТВЕРДЖУВАЛЬНА СЕРІЯ · SCIENTIFIC-EXP-04</p>
        <h1>Хемінг проти Евкліда у відомому тракті</h1>
        <p>Роздільні демодуляція (жорстке рішення 8PSK) і декодування з метрикою Хемінга проти спільних демодуляції й декодування з м'якою евклідовою метрикою. Обидва декодери обробляють те саме спостереження в кожному кадрі.</p></div>
        <span class="status-pill" id="r4-status">Завантаження…</span></div>
      <div class="r4-grid">
        <article class="card"><h2 id="r4-plot-title">BER від Eb/N0</h2><p id="r4-plot-sub"></p>
          <div class="r4-cells" id="r4-cells" role="group" aria-label="Канал"></div>
          <div id="r4-plot"></div>
          <div class="r4-legend"><span><i style="background:${COLORS.hamming}"></i>Хемінг · жорстке рішення</span><span><i style="background:${COLORS.euclidean}"></i>Евклід · м'яке, спільне</span><span><i style="border-top:2px dashed ${COLORS.qpsk};height:0"></i>QPSK без кодування (AWGN)</span></div>
          <div class="r4-kpi" id="r4-kpi"></div></article>
        <div class="r4-h" id="r4-hyp"></div>
      </div>
      <article class="card" style="margin-top:16px"><h2>Енергетичний виграш Евкліда над Хемінгом</h2>
        <p>Δ = Eb/N0(Хемінг) − Eb/N0(Евклід) при цільовому BER; 95 % ДІ — парний bootstrap за кадрами. Виділено первинну ціль комірки. Клацніть рядок, щоб показати криві.</p>
        <div class="table-wrap" style="max-height:none;font-family:inherit"><table id="r4-table"></table></div></article>
      <div class="card caveat"><strong>Як читати цей результат</strong>
        <p id="r4-article"></p><p id="r4-limits"></p><p class="r4-meta" id="r4-meta"></p></div>`;
    document.querySelector('main').prepend(section);

    // Navigation: own tab first; other tabs' handlers deactivate this view themselves.
    const tabs = document.querySelector('.tabs');
    tab = document.createElement('button');
    tab.className = 'tab';
    tab.dataset.view = 'result';
    tab.type = 'button';
    tab.textContent = 'Головний результат';
    tabs.prepend(tab);
    mobile = document.querySelector('.mobile-view-menu');
    if (mobile) {
      const option = new Option('Головний результат', 'result');
      mobile.prepend(option);
    }
    function show() {
      document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v === section));
      document.querySelectorAll('.tabs .tab').forEach(t => {
        t.classList.toggle('active', t === tab);
        t.setAttribute('aria-selected', String(t === tab));
      });
      document.body.classList.add('r4-on');
      if (mobile) mobile.value = 'result';
      if (location.hash !== '#result') history.replaceState(null, '', '#result');
      if (!state.bundle) load();
    }
    tab.addEventListener('click', () => { if (location.hash !== '#result') history.pushState(null, '', '#result'); show(); });
    if (mobile) mobile.addEventListener('change', () => { if (mobile.value === 'result') show(); });
    document.querySelectorAll('.tabs .tab').forEach(t => {
      if (t !== tab) t.addEventListener('click', () => hide());
    });
    // Other routes (system_workspace go()) only toggle their own views.
    const hide = () => { document.body.classList.remove('r4-on'); section.classList.remove('active'); tab.classList.remove('active'); tab.setAttribute('aria-selected', 'false'); };
    for (const name of ['scientific-view', 'scientific-navigate', 'hashchange', 'popstate']) window.addEventListener(name, () => { if (location.hash === '#result') setTimeout(show, 0); else hide(); });
    if (!location.hash || location.hash === '#result') show();

  }
  // Deferred scripts run while readyState is 'interactive', before DOMContentLoaded.
  if (document.readyState === 'complete') init(); else document.addEventListener('DOMContentLoaded', init);

  // ------------------------------------------------------------- rendering
  const $ = id => document.getElementById(id);
  function svgEl(parent, name, attrs, text) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    parent.append(node);
    return node;
  }

  function drawPlot(cell) {
    const rows = cellRows(cell);
    const m = logPlotModel(rows);
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${m.width} ${m.height}`);
    svg.setAttribute('class', 'r4-plot');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', `BER Хемінг і Евклід, ${CELL_TITLES[cell.id]?.[0] || cell.id}`);
    const bottom = m.height - m.pad.bottom, right = m.width - m.pad.right;
    for (let e = -6; e <= -1; e++) {
      const y = m.ly(10 ** e);
      svgEl(svg, 'line', {x1: m.pad.left, x2: right, y1: y, y2: y, stroke: '#e3eaed'});
      svgEl(svg, 'text', {x: m.pad.left - 8, y: y + 4, 'text-anchor': 'end'}, '10' + superscript(e));
    }
    const step = m.x1 - m.x0 > 20 ? 5 : 2;
    for (let x = Math.ceil(m.x0 / step) * step; x <= m.x1 + 1e-9; x += step) {
      svgEl(svg, 'line', {x1: m.lx(x), x2: m.lx(x), y1: m.pad.top, y2: bottom, stroke: '#eef3f4'});
      svgEl(svg, 'text', {x: m.lx(x), y: bottom + 18, 'text-anchor': 'middle'}, String(x));
    }
    svgEl(svg, 'text', {x: (m.pad.left + right) / 2, y: m.height - 8, 'text-anchor': 'middle'}, 'Eb/N0, дБ (дискретна модель, N0 = σ²)');
    svgEl(svg, 'text', {x: 14, y: (m.pad.top + bottom) / 2, transform: `rotate(-90 14 ${(m.pad.top + bottom) / 2})`, 'text-anchor': 'middle'}, 'BER');
    svgEl(svg, 'rect', {x: m.pad.left, y: m.pad.top, width: right - m.pad.left, height: bottom - m.pad.top, fill: 'none', stroke: '#c9d5da'});
    for (const target of state.bundle.all_target_ber) {
      const y = m.ly(target);
      svgEl(svg, 'line', {x1: m.pad.left, x2: right, y1: y, y2: y, stroke: '#9fb3bd', 'stroke-dasharray': '2 4'});
      svgEl(svg, 'text', {x: right - 4, y: y - 4, 'text-anchor': 'end', style: 'font-size:10px;fill:#7b8b94'}, berLabel(target));
    }
    const qpsk = [];
    for (let x = m.x0; x <= m.x1 + 1e-9; x += (m.x1 - m.x0) / 200) {
      const v = qpskBer(x);
      if (v < m.yMin) break;
      qpsk.push(`${m.lx(x).toFixed(1)},${m.ly(v).toFixed(1)}`);
    }
    svgEl(svg, 'polyline', {points: qpsk.join(' '), fill: 'none', stroke: COLORS.qpsk, 'stroke-width': 1.5, 'stroke-dasharray': '6 5'});
    for (const arm of ['hamming', 'euclidean']) {
      const pts = rows.filter(r => r[arm] > 0);
      svgEl(svg, 'polyline', {points: pts.map(r => `${m.lx(r.ebN0).toFixed(1)},${m.ly(r[arm]).toFixed(1)}`).join(' '), fill: 'none', stroke: COLORS[arm], 'stroke-width': 2.5, 'stroke-linejoin': 'round'});
      for (const r of pts) {
        const dot = svgEl(svg, 'circle', {cx: m.lx(r.ebN0), cy: m.ly(r[arm]), r: 3.5, fill: COLORS[arm], stroke: '#fff', 'stroke-width': 1});
        svgEl(dot, 'title', {}, `${arm === 'hamming' ? 'Хемінг' : 'Евклід'}: Eb/N0 ${dec(r.ebN0, 1)} дБ, BER ${r[arm].toExponential(2)} (${r[arm + 'Errors']} помилок із ${r.bits} біт)`);
      }
    }
    // Primary-target gain arrow.
    const t = cell.targets[targetKey(cell.primary_target_ber)];
    if (t && t.gain_db !== null) {
      const y = m.ly(cell.primary_target_ber), xe = m.lx(t.required_eb_n0_db.joint), xh = m.lx(t.required_eb_n0_db.separate);
      svgEl(svg, 'line', {x1: xe, x2: xh, y1: y, y2: y, stroke: '#123045', 'stroke-width': 2});
      svgEl(svg, 'path', {d: `M${xh - 7},${y - 5} L${xh},${y} L${xh - 7},${y + 5}`, fill: 'none', stroke: '#123045', 'stroke-width': 2});
      svgEl(svg, 'text', {x: (xe + xh) / 2, y: y - 9, 'text-anchor': 'middle', style: 'font-weight:800;fill:#123045;paint-order:stroke;stroke:#fff;stroke-width:5px'}, `${dec(t.gain_db)} дБ`);
    }
    $('r4-plot').replaceChildren(svg);
  }

  function renderCell() {
    const cell = state.bundle.cells.find(c => c.id === state.cell);
    const [title, sub] = CELL_TITLES[cell.id] || [cell.id, ''];
    $('r4-plot-title').textContent = `${title}: BER від Eb/N0`;
    $('r4-plot-sub').textContent = `${sub} · ${cell.points.length} рівнів × ${cell.points[0].trials} кадрів = ${cell.trials.toLocaleString('uk-UA')} парних кадрів`;
    document.querySelectorAll('#r4-cells button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.cell === cell.id)));
    document.querySelectorAll('#r4-table tr[data-cell]').forEach(r => r.style.outline = r.dataset.cell === cell.id ? '2px solid #087f8c55' : '');
    drawPlot(cell);
    $('r4-kpi').replaceChildren(...state.bundle.all_target_ber.map(target => {
      const g = gainSummary(cell, target);
      const box = document.createElement('div');
      box.innerHTML = `<small>BER ${berLabel(target)}${g.primary ? ' · первинна' : ''}</small><strong>${g.text}</strong><span>${g.ci || '—'}</span><span class="${g.verdict === 'PRECISION_CRITERIA_MET' ? '' : 'r4-flag'}">${VERDICTS[g.verdict]}</span>`;
      return box;
    }));
  }

  function renderTable() {
    const b = state.bundle;
    const head = `<tr><th>Канал і тракт</th>${b.all_target_ber.map(t => `<th>BER ${berLabel(t)}</th>`).join('')}</tr>`;
    const body = b.cells.map(cell => {
      const [title, sub] = CELL_TITLES[cell.id] || [cell.id, ''];
      const cells = b.all_target_ber.map(target => {
        const g = gainSummary(cell, target);
        const flag = g.verdict === 'PRECISION_CRITERIA_MET' ? '' : `<small class="r4-flag">${VERDICTS[g.verdict]}</small>`;
        return `<td class="${g.primary ? 'primary' : ''}">${g.text}<small>${g.ci}</small>${flag}</td>`;
      }).join('');
      return `<tr data-cell="${cell.id}"><td><strong>${cell.id.split('-')[0]}</strong> ${title}<small>${sub}${cell.role === 'secondary' ? ' · вторинна' : ''}</small></td>${cells}</tr>`;
    }).join('');
    $('r4-table').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
    $('r4-table').querySelectorAll('tr[data-cell]').forEach(row => row.addEventListener('click', () => { state.cell = row.dataset.cell; renderCell(); }));
  }

  function renderHypotheses() {
    const b = state.bundle, h = hypotheses(b);
    const byId = Object.fromEntries(b.cells.map(c => [c.id, c]));
    const gain = (id, t) => gainSummary(byId[id], t ?? byId[id].primary_target_ber);
    const a1 = byId['A1-awgn'];
    const qpsk3 = qpskRequiredDb(1e-3), euclid3 = a1?.targets['0.001']?.required_eb_n0_db?.joint, hamming3 = a1?.targets['0.001']?.required_eb_n0_db?.separate;
    const items = [
      ['H1 · первинна', h1Text(h.h1, b, gain), ''],
      ['Чому без м\'якого рішення кодування не окупається', Number.isFinite(euclid3)
        ? `В AWGN при BER 10⁻³ Хемінгу потрібно ${dec(hamming3)} дБ — на ${dec(hamming3 - qpsk3)} дБ більше, ніж QPSK без кодування (${dec(qpsk3)} дБ). Евклід потребує ${dec(euclid3)} дБ і виграє в QPSK ${dec(qpsk3 - euclid3)} дБ. Код TCM дає енергетичний виграш лише разом зі спільним м'яким декодуванням.` : '', ''],
      ['H2 · CSI-вага (описова)', h.h2DifferenceDb === null ? 'Немає даних.' : `Зважена й незважена евклідові метрики в ITU moderate відрізняються на ${dec(h.h2DifferenceDb, 3)} дБ при первинній цілі: за повільних завмирань вага майже стала в межах вікна Вітербі (η = 20).`, 'r4-desc'],
      ['H3 · практичний тракт (описова)', h.h3 ? `З причинною оцінкою каналу за пілотами виграш Евкліда зберігається: ${h.h3.text} ${h.h3.ci} при BER 10⁻². Неточність оцінки коштує обом декодерам приблизно однаково.` : 'Немає даних.', 'r4-desc'],
    ];
    $('r4-hyp').replaceChildren(...items.map(([title, text, cls]) => {
      const card = document.createElement('article');
      card.className = 'card ' + cls;
      card.innerHTML = `<h3>${title}</h3><p>${text}</p>`;
      return card;
    }));
  }
  function h1Text(ok, b, gain) {
    const list = b.cells.filter(c => c.role === 'primary').map(c => `${c.id.split('-')[0]} ${gain(c.id).text}`).join(', ');
    return ok
      ? `Підтверджено: в усіх первинних комірках Евклід потребує меншого Eb/N0, нижня межа 95 % ДІ > 0 і точність достатня (${list}).`
      : `Не підтверджено в усіх первинних комірках (${list}).`;
  }

  function renderNotes() {
    const b = state.bundle;
    const byId = Object.fromEntries(b.cells.map(c => [c.id, c]));
    const at = id => gainSummary(byId[id], b.article_reference_target_ber).text;
    $('r4-article').textContent = `У статті повідомлено виграш близько 1,5 дБ при частоті помилок ≈ 5·10⁻²; умови моделювання (канал, сенс p′ₙ, опорний приймач) у ній не наведено, а уточнити їх немає змоги, тому порівняння лише описове (paper_exact = false). Тут при 5·10⁻²: AWGN ${at('A1-awgn')}, ITU moderate ${at('A3-itu-moderate')}, тракт за пілотами ${at('S2-itu-moderate-pilot')} — того самого знака й порядку.`;
    $('r4-limits').textContent = 'Обмеження: дискретна модель (8 відліків на елемент, без фільтрів і синхронізації); другий промінь ITU — 3 відліки замість 0,5–2 мс; без перемежування; кодер і маркування 8PSK — реконструкція проєкту. «Відомий тракт» = точні коефіцієнти каналу.';
    $('r4-meta').textContent = `Протокол ${b.protocol_id}, SHA-256 ${b.protocol_sha256} (заморожено до запуску) · ${b.cells.reduce((s, c) => s + c.trials, 0).toLocaleString('uk-UA')} парних кадрів · незалежний перерахунок помилок без розбіжностей · ${b.bootstrap_replicates} bootstrap-повторів · звіт ${b.report}`;
  }

  async function load() {
    $('r4-status').textContent = 'Завантаження…';
    try {
      const response = await fetch('/api/scientific/exp04-results');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      state.bundle = data;
      $('r4-cells').replaceChildren(...data.cells.map(cell => {
        const button = document.createElement('button');
        button.type = 'button';
        button.dataset.cell = cell.id;
        button.textContent = CELL_TITLES[cell.id]?.[0] || cell.id;
        button.addEventListener('click', () => { state.cell = cell.id; renderCell(); });
        return button;
      }));
      renderTable();
      renderHypotheses();
      renderNotes();
      renderCell();
      $('r4-status').textContent = 'Перевірено · протокол ' + data.protocol_sha256.slice(0, 12);
    } catch (error) {
      $('r4-status').textContent = 'Результати недоступні';
      $('r4-plot').textContent = 'Не вдалося завантажити підтверджені результати: ' + error.message;
    }
  }
})();
