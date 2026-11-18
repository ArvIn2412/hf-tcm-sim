/* «Експеримент»: режим ізольованого порівняння метрик Хемінга та Евкліда.
   Використовує наявний API /api/scientific/metric-studies; системний шлях Joint/B0
   лишається без змін і обирається тим самим перемикачем. */
((root) => {
  'use strict';

  /* Pure configuration builder (unit-tested in tests/test_metric_mode.js). */
  function scenarioFor(fading, rays) {
    if (fading !== 'none') return 'rician';
    return rays > 1 ? 'static' : 'awgn';
  }

  function buildMetricConfig(input, channelBuilder) {
    const {comparisonMode, tract, metric, awgn, variance, fading, rays, rho, seed, frameSymbols,
      amplitude, delays, powers, factors, phases, grid, trials, target, budget, sweep, bootstrap, now,
      fadingModel = 'ar1', dopplerHz = 0, baud = 0} = input;
    if (!['known', 'pilot'].includes(tract)) throw new Error('Оберіть тракт приймача.');
    if (!['csi_weighted', 'unweighted'].includes(metric)) throw new Error('Оберіть евклідову метрику.');
    if (!Number.isSafeInteger(frameSymbols) || frameSymbols < 20 || frameSymbols > 20000)
      throw new Error('Для порівняння метрик N має бути цілим у межах 20…20 000.');
    const frontend = tract === 'known' ? 'known_channel' : 'pilot_equalized';
    const doppler = fadingModel === 'doppler' ? {spreadHz: dopplerHz, baud} : null;
    const channel = channelBuilder({awgn, fading, rays, variance, seed, rho, delays, powers, factors, phases, frontend, doppler});
    const series = comparisonMode === 'series';
    let energyGrid = [0];
    if (series) {
      energyGrid = String(grid).split(',').map(v => Number(v.trim()));
      if (!energyGrid.length || energyGrid.some(v => !Number.isFinite(v)) || new Set(energyGrid).size !== energyGrid.length)
        throw new Error('Енергетична сітка: унікальні числа через кому.');
    }
    if (series && sweep === 'noise' && !(channel.noise_complex_variance > 0))
      throw new Error('Зміна енергії шумом потребує увімкненого AWGN.');
    return {
      experiment_id: `metric-${tract}-${now}`,
      scenario: scenarioFor(fading, rays),
      phase: 'range_finding',
      frame_symbols: frameSymbols,
      energy_grid_db: energyGrid,
      trials_per_point: series ? trials : 1,
      root_seed: seed,
      target_ber: target,
      time_budget_seconds: budget,
      sweep: series ? sweep : 'amplitude',
      amplitude,
      channel_config: channel,
      frontend_mode: frontend,
      bootstrap_replicates: Math.max(100, bootstrap),
      euclidean_metric: metric,
    };
  }

  /* Watterson / ITU-R F.1487: spread = 2 sigma_f, R(tau) = exp(-2 pi^2 sigma_f^2 tau^2). */
  function dopplerSummary(spreadHz, baud) {
    const sigma = spreadHz / 2, r = tau => Math.exp(-2 * Math.PI ** 2 * sigma ** 2 * tau ** 2);
    const coherenceSeconds = Math.sqrt(Math.LN2 / (2 * Math.PI ** 2 * sigma ** 2));
    return {rhoSample: r(1 / (8 * baud)), rhoSymbol: r(1 / baud), coherenceSeconds,
      coherenceSymbols: coherenceSeconds * baud};
  }
  const ITU_PRESETS = {good: 0.1, moderate: 0.5, poor: 1.0, flutter: 10.0};

  /* Gaussian tail Q(x); uncoded QPSK reference BER = Q(sqrt(2 Eb/N0)). */
  function qFunction(x) {
    if (x > 4) {
      const pdf = Math.exp(-x * x / 2) / Math.sqrt(2 * Math.PI);
      return pdf / x * (1 - 1 / x ** 2 + 3 / x ** 4);
    }
    const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
    const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
    const erfc = poly * Math.exp(-x * x / 2);
    return x >= 0 ? erfc / 2 : 1 - erfc / 2;
  }
  function qpskReferenceBer(ebN0Db) { return qFunction(Math.sqrt(2 * 10 ** (ebN0Db / 10))); }

  const api = {buildMetricConfig, scenarioFor, qFunction, qpskReferenceBer, dopplerSummary, ITU_PRESETS};
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof document === 'undefined') return;
  root.metricMode = api;

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('run-form');
    if (!form || !window.systemExperiment) return;
    const $ = id => document.getElementById(id);
    const primary = form.querySelector('.simulation-primary');
    const button = form.querySelector('#run-button') || window.systemNodes?.get('#run-button');
    const status = $('job-status');
    const progress = form.querySelector('progress');

    function select(id, title, options, value) {
      const label = document.createElement('label');
      label.textContent = title;
      const input = document.createElement('select');
      input.id = id;
      for (const [v, text] of options) {
        const o = document.createElement('option'); o.value = v; o.textContent = text; input.append(o);
      }
      input.value = value;
      label.append(input);
      return {label, input};
    }
    const contrast = select('exp-contrast', 'Що порівнюємо', [
      ['metric', 'Метрики: Хемінг (жорстке) vs Евклід (м’яке)'],
      ['system', 'Повні приймачі Joint / B0'],
    ], 'metric');
    const tract = select('exp-tract', 'Тракт приймача', [
      ['known', 'Відомий тракт (точні коефіцієнти)'],
      ['pilot', 'Оцінений за пілотами'],
    ], 'known');
    const metric = select('exp-euclid', 'Евклідова метрика', [
      ['csi_weighted', 'Зважена за станом каналу Σ|ĥ|²'],
      ['unweighted', 'Незважена |z−s|²'],
    ], 'csi_weighted');
    const fadingModel = select('exp-fading-model', 'Модель завмирань', [
      ['doppler', 'Доплер, гаусів спектр (Уоттерсон / ITU)'],
      ['ar1', 'AR(1) на відлік, ρ (як у EXP-03B)'],
    ], 'doppler');
    const itu = select('exp-itu', 'Профіль КХ-каналу ITU-R F.1487', [
      ['', 'Власні параметри'], ['good', 'Good — 0,1 Гц'], ['moderate', 'Moderate — 0,5 Гц'],
      ['poor', 'Poor — 1 Гц'], ['flutter', 'Flutter — 10 Гц'],
    ], '');
    function numberField(id, title, value) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input'); input.id = id; input.type = 'number';
      input.step = 'any'; input.min = '0'; input.value = value; label.append(input);
      return {label, input};
    }
    const doppler = numberField('exp-doppler', 'Доплерівське розширення 2σ_f, Гц', '0.5');
    const baud = numberField('exp-baud', 'Символьна швидкість, Бод', '2400');
    const dopplerInfo = document.createElement('p');
    dopplerInfo.className = 'metric-mode-hint';
    const hint = document.createElement('p');
    hint.className = 'metric-mode-hint';
    primary.prepend(contrast.label, tract.label, metric.label);
    const fadingLabel = document.getElementById('exp-fading').closest('label');
    fadingLabel.after(fadingModel.label, itu.label, doppler.label, baud.label);
    primary.after(hint, dopplerInfo);
    const setField = (id, v) => { const el = $(id); el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); };
    itu.input.addEventListener('change', () => {
      const spread = ITU_PRESETS[itu.input.value];
      if (spread === undefined) return;
      fadingModel.input.value = 'doppler';
      setField('exp-fading', 'rayleigh'); setField('exp-rays', '2');
      $('exp-delays').value = '0,3'; $('exp-powers').value = '0.5,0.5'; $('exp-k').value = '0,0';
      $('exp-phases').value = '0,0'; doppler.input.value = String(spread);
      syncFading();
    });
    doppler.input.addEventListener('input', () => { itu.input.value = ''; syncFading(); });
    baud.input.addEventListener('input', syncFading);
    fadingModel.input.addEventListener('change', syncFading);
    $('exp-fading').addEventListener('change', syncFading);
    function syncFading() {
      const isMetric = contrast.input.value === 'metric';
      const faded = $('exp-fading').value !== 'none';
      const useDoppler = isMetric && faded && fadingModel.input.value === 'doppler';
      fadingModel.label.hidden = !(isMetric && faded);
      itu.label.hidden = !isMetric;
      doppler.label.hidden = baud.label.hidden = !useDoppler;
      const rhoLabel = $('exp-rho')?.closest('label');
      if (rhoLabel) rhoLabel.hidden = useDoppler;
      dopplerInfo.hidden = !useDoppler;
      const spread = Number(doppler.input.value), rate = Number(baud.input.value);
      if (useDoppler && spread > 0 && rate > 0) {
        const d = dopplerSummary(spread, rate);
        dopplerInfo.textContent = `Еквівалентна кореляція: ρ на відлік = ${d.rhoSample.toFixed(9)}, на елемент = ${d.rhoSymbol.toFixed(7)}; час когерентності (R = 0,5) ≈ ${d.coherenceSeconds.toLocaleString('uk-UA', {maximumSignificantDigits: 3})} с ≈ ${Math.round(d.coherenceSymbols).toLocaleString('uk-UA')} елементів. Затримки ITU (0,5–2 мс) не відтворюються: комбайнер підтримує затримки до 7 відліків.`;
      }
    }

    function syncVisibility() {
      const isMetric = contrast.input.value === 'metric';
      tract.label.hidden = metric.label.hidden = !isMetric;
      if (typeof syncFading === 'function') syncFading();
      hint.textContent = isMetric
        ? 'Обидва декодери (жорстке рішення 8PSK → Хемінг та м’яка евклідова метрика) обробляють одне спостереження і той самий тракт; η = 20.'
        : 'Порівняння повних алгоритмів приймання (адаптивний Joint і роздільний B0) на одному спостереженні.';
    }
    contrast.input.addEventListener('change', syncVisibility);
    syncVisibility();

    const value = id => $(id)?.value;
    const numbers = id => String(value(id)).split(',').map(Number);
    const state = {jobId: null, timer: null};

    function currentConfig() {
      return buildMetricConfig({
        comparisonMode: window.systemExperiment.mode,
        tract: tract.input.value, metric: metric.input.value,
        awgn: value('exp-awgn') === 'on', variance: Number(value('exp-variance')),
        fading: value('exp-fading'), rays: Number(value('exp-rays')), rho: Number(value('exp-rho')),
        seed: Number(form.querySelector('[name="source_seed"]').value),
        frameSymbols: Number(form.querySelector('[name="frame_symbols"]').value),
        amplitude: Number(value('exp-amplitude')),
        delays: numbers('exp-delays'), powers: numbers('exp-powers'),
        factors: numbers('exp-k'), phases: numbers('exp-phases'),
        grid: value('es-grid'), trials: Number(value('es-trials')), target: Number(value('es-target')),
        budget: Number(value('es-budget')), sweep: value('es-sweep'), bootstrap: Number(value('es-bootstrap')),
        fadingModel: fadingModel.input.value, dopplerHz: Number(doppler.input.value), baud: Number(baud.input.value),
        now: Date.now(),
      }, window.channelControls.build);
    }

    async function request(url, options) {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    }

    function finish() {
      clearInterval(state.timer); state.timer = null; state.jobId = null;
      button.disabled = false; if (progress) progress.value = 1;
    }

    async function poll() {
      try {
        const job = await request(`/api/scientific/jobs/${encodeURIComponent(state.jobId)}`);
        if (progress) progress.value = job.progress || 0;
        status.textContent = job.status === 'queued' ? 'Порівняння метрик у черзі…'
          : job.status === 'running' ? `Порівняння метрик: ${job.completed_trials || 0}/${job.planned_trials || 0} парних кадрів…`
            : job.status === 'failed' ? `Помилка: ${job.error}`
              : `Порівняння метрик завершено (${job.completed_trials || 0}/${job.planned_trials || 0} кадрів).`;
        if (!['completed', 'incomplete', 'failed'].includes(job.status)) return;
        finish();
        if (job.status !== 'failed' && job.experiment_id) {
          const summary = await request(`/api/scientific/metric-studies/${encodeURIComponent(job.experiment_id)}`);
          renderResults(summary);
          window.dispatchEvent(new CustomEvent('scientific-view', {detail: 'metric'}));
        }
      } catch (error) {
        finish();
        status.textContent = `Не вдалося отримати стан: ${error.message}`;
      }
    }

    form.addEventListener('submit', async event => {
      if (contrast.input.value !== 'metric') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (state.jobId) return;
      let config;
      try { config = currentConfig(); } catch (error) { status.textContent = `Конфігурацію не прийнято: ${error.message}`; return; }
      button.disabled = true;
      if (progress) progress.removeAttribute('value');
      status.textContent = 'Перевірка конфігурації…';
      try {
        const queued = await request('/api/scientific/metric-studies', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config),
        });
        state.jobId = queued.job_id;
        state.timer = setInterval(poll, 500);
      } catch (error) {
        button.disabled = false;
        status.textContent = `Конфігурацію не прийнято: ${error.message}`;
      }
    }, true);

    /* Results: «Результати та ефективність». */
    const view = $('view-metric');
    const panel = document.createElement('section');
    panel.id = 'metric-mode-results';
    panel.hidden = true;
    view.querySelector('h1')?.after(panel);
    const fmt = v => typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('uk-UA', {maximumSignificantDigits: 5}) : '—';
    const count = v => Number.isSafeInteger(v) ? v.toLocaleString('uk-UA') : '—';
    const arms = [['hamming', 'Роздільне — жорстке рішення, Хемінг', '#bb6518'], ['joint', 'Спільне — м’яка метрика, Евклід', '#087f8c']];

    function renderResults(summary) {
      const c = summary.configuration || {};
      const rows = (summary.aggregates || []).filter(r => Number.isFinite(r.gamma_db)).slice().sort((a, b) => a.gamma_db - b.gamma_db);
      panel.hidden = false;
      panel.replaceChildren();
      const h = document.createElement('h2');
      h.textContent = 'Порівняння метрик Хемінга та Евкліда';
      const meta = document.createElement('p');
      const tractText = c.frontend_mode === 'known_channel' ? 'відомий тракт' : c.frontend_mode === 'pilot_equalized' ? 'оцінений за пілотами' : c.frontend_mode;
      const ch = c.channel_config || {};
      const fadingText = ch.fading_mode === 'rician_doppler' ? ` · Доплер ${fmt(ch.doppler_spread_hz)} Гц при ${fmt(ch.symbol_rate_baud)} Бод` : ch.fading_mode === 'rician_ar1' ? ` · AR(1) ρ=${fmt(ch.correlation)}` : '';
      meta.textContent = `Канал: ${c.scenario}${fadingText} · тракт: ${tractText} · евклідова метрика: ${c.euclidean_metric === 'csi_weighted' ? 'зважена Σ|ĥ|²' : 'незважена'} · N=${count(c.frame_symbols)} · ${count(summary.completed_trials)} парних кадрів · серія ${summary.experiment_id}`;
      panel.append(h, meta);

      const table = document.createElement('table');
      table.className = 'metric-mode-table';
      table.innerHTML = '<thead><tr><th>Eb/N0, дБ</th><th>Кадрів</th><th>BER Хемінг</th><th>BER Евклід</th><th>Помилки H / E</th><th>Біт</th></tr></thead>';
      const body = document.createElement('tbody');
      for (const r of rows) {
        const tr = document.createElement('tr');
        for (const text of [fmt(r.gamma_db), count(r.trials), fmt(r.ber?.hamming), fmt(r.ber?.joint),
          `${count(r.bit_errors?.hamming)} / ${count(r.bit_errors?.joint)}`, count(r.bits)]) {
          const td = document.createElement('td'); td.textContent = text; tr.append(td);
        }
        body.append(tr);
      }
      table.append(body);
      panel.append(table);

      const gain = document.createElement('p');
      gain.className = 'results-gain';
      const g = summary.gain_analysis || {};
      const ci = g.bootstrap?.confidence_interval_db;
      const hasCi = Array.isArray(ci) && ci.length === 2 && ci.every(Number.isFinite);
      const valid = g.bootstrap?.valid_fraction;
      gain.textContent = Number.isFinite(g.gain_db) && hasCi
        ? `Енергетичний виграш Евкліда над Хемінгом при BER ${fmt(g.target_ber)}: ${fmt(g.gain_db)} дБ · 95% ДІ [${ci.map(fmt).join('; ')}] (розвідувальна серія).`
        : Number.isFinite(g.gain_db)
          ? `Точкова оцінка виграшу при BER ${fmt(g.target_ber)}: ${fmt(g.gain_db)} дБ — недостатня точність: валідних bootstrap-перетинів ${Number.isFinite(valid) ? fmt(100 * valid) + '%' : '—'} (потрібно ≥ 95%). Збільште кількість кадрів на точку.`
        : rows.length < 2
          ? 'Один енергетичний рівень: для оцінки виграшу оберіть «Статистична серія» з кількома рівнями енергії.'
          : `Виграш не оцінено (${g.status || 'немає перетину цільового BER'}): криві мають перетнути ціль BER ${fmt(g.target_ber ?? c.target_ber)}.`;
      panel.append(gain);
      if (rows.length >= 2) panel.append(plot(rows, Number(g.target_ber ?? c.target_ber)));
    }

    function plot(rows, target) {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('viewBox', '0 0 1200 500');
      svg.setAttribute('aria-label', 'BER Хемінг / Евклід');
      svg.style.width = '100%';
      const el = (tag, attrs, text) => {
        const n = document.createElementNS(ns, tag);
        for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
        if (text !== undefined) n.textContent = text;
        svg.append(n); return n;
      };
      const ys = rows.flatMap(r => arms.map(([k]) => r.ber?.[k])).filter(v => Number.isFinite(v) && v > 0);
      if (Number.isFinite(target) && target > 0) ys.push(target);
      if (!ys.length) { el('text', {x: 400, y: 250, 'font-size': 18}, 'Помилок не спостережено на жодному рівні.'); return svg; }
      const lo = Math.floor(Math.log10(Math.min(...ys))), hi = Math.max(lo + 1, Math.ceil(Math.log10(Math.max(...ys))));
      const x0 = rows[0].gamma_db, x1 = rows.at(-1).gamma_db;
      const x = v => 80 + (v - x0) / (x1 - x0) * 1040, y = v => 430 - (Math.log10(v) - lo) / (hi - lo) * 380;
      for (let d = lo; d <= hi; d++) {
        el('line', {x1: 80, x2: 1120, y1: y(10 ** d), y2: y(10 ** d), stroke: '#ddd'});
        el('text', {x: 10, y: y(10 ** d) + 5, 'font-size': 14}, `1e${d}`);
      }
      for (const r of rows) el('text', {x: x(r.gamma_db) - 12, y: 458, 'font-size': 14}, fmt(r.gamma_db));
      el('text', {x: 330, y: 490, 'font-size': 16}, 'Eb/N0, дБ (дискретна модель, N0 = σ²; валідовано за теорією 8PSK)');
      const reference = [];
      for (let k = 0; k <= 60; k++) {
        const g = x0 + (x1 - x0) * k / 60, v = qpskReferenceBer(g);
        if (v >= 10 ** lo && v <= 10 ** hi) reference.push(`${reference.length ? 'L' : 'M'}${x(g)} ${y(v)}`);
      }
      if (reference.length > 1) {
        el('path', {d: reference.join(' '), stroke: '#222', fill: 'none', 'stroke-width': 1.5, 'stroke-dasharray': '8 6'});
        el('text', {x: 900, y: 25, fill: '#222', 'font-size': 16}, '- - некодована QPSK');
      }
      if (Number.isFinite(target) && target > 0) {
        el('line', {x1: 80, x2: 1120, y1: y(target), y2: y(target), stroke: '#555', 'stroke-dasharray': '5 5'});
        el('text', {x: 86, y: y(target) - 8, 'font-size': 14}, `Ціль BER ${fmt(target)}`);
      }
      arms.forEach(([key, label, color], index) => {
        let path = '', connected = false;
        for (const r of rows) {
          const v = r.ber?.[key];
          if (!(v > 0)) { connected = false; continue; }
          path += `${connected ? ' L' : ' M'}${x(r.gamma_db)} ${y(v)}`; connected = true;
          const point = el('circle', {cx: x(r.gamma_db), cy: y(v), r: 5, fill: color});
          const title = document.createElementNS(ns, 'title');
          title.textContent = `${label} · Eb/N0 ${fmt(r.gamma_db)} дБ · BER ${fmt(v)} · ${count(r.bit_errors?.[key])} із ${count(r.bits)}`;
          point.append(title);
        }
        el('path', {d: path.trim(), stroke: color, fill: 'none', 'stroke-width': 2.5});
        el('text', {x: 90 + index * 400, y: 25, fill: color, 'font-size': 16}, label);
      });
      return svg;
    }
  });
})(typeof window === 'undefined' ? globalThis : window);
