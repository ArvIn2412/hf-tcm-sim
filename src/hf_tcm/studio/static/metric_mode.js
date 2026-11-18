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

  /* Pilot schedule of metric_isolation.build_pilot_schedule: preamble + bursts every period. */
  function payloadSymbols(frameSymbols, preamble = 4, period = 32, burst = 4) {
    const pilot = new Uint8Array(frameSymbols);
    pilot.fill(1, 0, Math.min(preamble, frameSymbols));
    for (let start = period; start < frameSymbols; start += period) pilot.fill(1, start, Math.min(frameSymbols, start + burst));
    return frameSymbols - pilot.reduce((a, b) => a + b, 0);
  }
  /* Eb/N0 (= gamma_b,d) of one frame: E_tx = 8 A^2 N over all elements, 2 bits per payload element. */
  function referenceEbN0Db(frameSymbols, amplitude, variance) {
    return 10 * Math.log10(8 * amplitude ** 2 * frameSymbols / (2 * payloadSymbols(frameSymbols) * variance));
  }

  function buildMetricConfig(input, channelBuilder) {
    const {comparisonMode, tract, metric, awgn, variance, fading, rays, rho, seed, frameSymbols,
      amplitude, delays, powers, factors, phases, grid, trials, target, budget, sweep, bootstrap, now,
      fadingModel = 'ar1', dopplerHz = 0, baud = 0} = input;
    if (!['known', 'pilot'].includes(tract)) throw new Error('Оберіть тракт приймача.');
    if (!['csi_weighted', 'unweighted'].includes(metric)) throw new Error('Оберіть евклідову метрику.');
    if (!Number.isSafeInteger(frameSymbols) || frameSymbols < 20 || frameSymbols > MAX_FRAME_SYMBOLS)
      throw new Error(`Для порівняння метрик N має бути цілим у межах 20…${MAX_FRAME_SYMBOLS.toLocaleString('uk-UA')}.`);
    const frontend = tract === 'known' ? 'known_channel' : 'pilot_equalized';
    const doppler = fadingModel === 'doppler' ? {spreadHz: dopplerHz, baud} : null;
    const channel = channelBuilder({awgn, fading, rays, variance, seed, rho, delays, powers, factors, phases, frontend, doppler});
    const series = comparisonMode === 'series';
    let energyGrid = [0];
    if (series) {
      const ebN0 = String(grid).split(',').map(v => Number(v.trim()));
      if (!ebN0.length || ebN0.some(v => !Number.isFinite(v)) || new Set(ebN0).size !== ebN0.length)
        throw new Error('Сітка Eb/N0: унікальні числа в дБ через кому.');
      if (!(channel.noise_complex_variance > 0))
        throw new Error('Сітка Eb/N0 потребує увімкненого шуму (σ² > 0).');
      // The study API sweeps offsets from the base level; convert absolute Eb/N0 to offsets.
      const reference = referenceEbN0Db(frameSymbols, amplitude, channel.noise_complex_variance);
      energyGrid = ebN0.map(v => Math.round((v - reference) * 1e9) / 1e9);
    }
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
      // Long frames: keep full arrays only for frame 0 of each energy point.
      ...(frameSymbols > 20000 ? {full_array_stride: Math.max(1, series ? trials : 1)} : {}),
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

  /* Wilson score interval of a binomial proportion (95 %). */
  function wilsonInterval(errors, trials, z = 1.959963984540054) {
    if (!(trials > 0)) return [NaN, NaN];
    const p = errors / trials, z2 = z * z, denom = 1 + z2 / trials;
    const centre = (p + z2 / (2 * trials)) / denom;
    const half = z * Math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denom;
    return [Math.max(0, centre - half), Math.min(1, centre + half)];
  }
  /* Default Eb/N0 grid: AWGN/static curves fall within ~10 dB, fading needs ~40 dB. */
  const GRID_AWGN = '0, 2, 4, 6, 8, 10';
  const GRID_FADING = '0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40';
  const defaultGrid = fading => (fading && fading !== 'none' ? GRID_FADING : GRID_AWGN);
  /* Clean-tail combiner: only the 8 - max(delay) samples free of the previous symbol are used. */
  function cleanSamples(delays, rays) {
    const used = delays.slice(0, Math.max(1, rays)).map(Number).filter(Number.isFinite);
    const maxDelay = used.length ? Math.max(0, ...used) : 0;
    const clean = 8 - maxDelay;
    return {maxDelay, clean, lossDb: clean > 0 ? 10 * Math.log10(8 / clean) : Infinity};
  }
  const MAX_FRAME_SYMBOLS = 100000;
  const api = {buildMetricConfig, scenarioFor, qFunction, qpskReferenceBer, dopplerSummary, ITU_PRESETS, payloadSymbols, referenceEbN0Db, wilsonInterval, defaultGrid, cleanSamples, GRID_AWGN, GRID_FADING, MAX_FRAME_SYMBOLS};
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
      // Metric isolation allows up to 100 000 elements; the Joint/B0 receivers keep 20 000.
      const frameInput = [...document.querySelectorAll('#run-form label')].find(l => /^N/.test(l.textContent.trim()))?.querySelector('input');
      if (frameInput) frameInput.max = String(isMetric ? MAX_FRAME_SYMBOLS : 20000);
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

    // Data line under the form: clean samples left to the combiner by the path delays.
    const cleanLine = document.createElement('p');
    cleanLine.className = 'clean-samples';
    cleanLine.setAttribute('role', 'status');
    primary.after(cleanLine);
    function syncClean() {
      const isMetric = contrast.input.value === 'metric';
      const delays = String($('exp-delays')?.value || '0').split(',');
      const {maxDelay, clean, lossDb} = cleanSamples(delays, Number($('exp-rays')?.value || 1));
      cleanLine.hidden = !isMetric || maxDelay === 0;
      cleanLine.classList.toggle('warn', clean <= 4);
      cleanLine.textContent = clean > 0
        ? `Чистих відліків на елемент: ${clean} з 8 (затримка ${maxDelay}); втрата енергії в комбайнері ${lossDb.toFixed(1).replace('.', ',')} дБ відносно осі Eb/N0`
        : `Затримка ${maxDelay} відліків не залишає чистих відліків: зменште затримки до 7 і менше`;
    }
    // Eb/N0 grid follows the channel type until the user edits it.
    const gridInput = $('es-grid');
    let gridEdited = gridInput && ![GRID_AWGN, GRID_FADING].includes(gridInput.value.trim());
    gridInput?.addEventListener('input', () => { gridEdited = ![GRID_AWGN, GRID_FADING].includes(gridInput.value.trim()); });
    function syncGrid() {
      if (!gridInput || gridEdited) return;
      gridInput.value = defaultGrid($('exp-fading').value);
    }
    for (const id of ['exp-delays', 'exp-rays']) for (const type of ['input', 'change']) $(id)?.addEventListener(type, syncClean);
    $('exp-fading').addEventListener('change', syncGrid);
    itu.input.addEventListener('change', () => { syncGrid(); syncClean(); });
    contrast.input.addEventListener('change', syncClean);

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
    syncClean();
    syncGrid();

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
    const db = v => Number.isFinite(v) ? ((Math.round(v * 10) / 10) || 0).toLocaleString('uk-UA', {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '—';
    const sci = v => !Number.isFinite(v) ? '—' : v === 0 ? '0' : v.toExponential(1).replace('e', '·10^').replace(/\^\+?(-?)0*(\d+)/, (_, s, d) => `<sup>${s ? '−' : ''}${d}</sup>`);
    const count = v => Number.isSafeInteger(v) ? v.toLocaleString('uk-UA') : '—';
    const arms = [['hamming', 'Хемінг', '#c2410c'], ['joint', 'Евклід', '#0a7f8c']];

    function renderResults(summary) {
      const c = summary.configuration || {};
      const rows = (summary.aggregates || []).map((r, point) => ({...r, point}))
        .filter(r => Number.isFinite(r.gamma_db)).sort((a, b) => a.gamma_db - b.gamma_db);
      panel.hidden = false;
      panel.replaceChildren();
      const h = document.createElement('h2');
      h.textContent = 'Хемінг і Евклід';
      const meta = document.createElement('p');
      meta.className = 'results-meta';
      const tractText = c.frontend_mode === 'known_channel' ? 'відомий тракт' : c.frontend_mode === 'pilot_equalized' ? 'тракт за пілотами' : c.frontend_mode;
      const ch = c.channel_config || {};
      const fadingText = ch.fading_mode === 'rician_doppler' ? `, Доплер ${fmt(ch.doppler_spread_hz)} Гц` : ch.fading_mode === 'rician_ar1' ? `, AR(1) ρ = ${fmt(ch.correlation)}` : '';
      meta.textContent = `${c.scenario}${fadingText}; ${tractText}; метрика ${c.euclidean_metric === 'csi_weighted' ? 'зважена' : 'незважена'}; N = ${count(c.frame_symbols)}; ${count(summary.completed_trials)} парних кадрів`;
      panel.append(h, meta);

      const table = document.createElement('table');
      table.className = 'metric-mode-table';
      table.innerHTML = '<thead><tr><th>Eb/N0, дБ</th><th>Кадрів</th><th>BER Хемінг, 95 % ДІ</th><th>BER Евклід, 95 % ДІ</th><th>Помилок Х / Е</th><th>Біт</th><th></th></tr></thead>';
      const body = document.createElement('tbody');
      for (const r of rows) {
        const tr = document.createElement('tr');
        const cell = key => {
          const errors = r.bit_errors?.[key], bits = r.bits;
          if (!Number.isSafeInteger(errors) || !(bits > 0)) return '—';
          const [lo, hi] = wilsonInterval(errors, bits);
          return `${sci(errors / bits)} <small>[${sci(lo)}; ${sci(hi)}]</small>`;
        };
        tr.innerHTML = `<td>${db(r.gamma_db)}</td><td>${count(r.trials)}</td><td>${cell('hamming')}</td><td>${cell('joint')}</td><td>${count(r.bit_errors?.hamming)} / ${count(r.bit_errors?.joint)}</td><td>${count(r.bits)}</td><td></td>`;
        if (window.metricContext) {
          const open = document.createElement('button');
          open.type = 'button';
          open.textContent = 'Етапи';
          open.title = 'Відкрити кадр 0 цього рівня у «Етапах обробки» на першій розбіжності';
          open.addEventListener('click', async () => {
            await window.metricContext.open({study: summary.experiment_id, point: r.point, trial: 0, jumpTo: 'disagree'});
            window.metricContext.showStages();
          });
          tr.lastElementChild.append(open);
        }
        body.append(tr);
      }
      table.append(body);
      panel.append(table);

      const g = summary.gain_analysis || {};
      const ci = g.bootstrap?.confidence_interval_db;
      const hasCi = Array.isArray(ci) && ci.length === 2 && ci.every(Number.isFinite);
      const anyErrors = rows.some(r => (r.bit_errors?.hamming || 0) + (r.bit_errors?.joint || 0) > 0);
      const gain = document.createElement('p');
      gain.className = 'results-gain';
      if (rows.length >= 2 && !anyErrors) {
        gain.classList.add('warn');
        gain.textContent = `Помилок немає на жодному рівні (${db(rows[0].gamma_db)}…${db(rows.at(-1).gamma_db)} дБ): сітка вища за робочу зону. Для AWGN задайте Eb/N0 0…10 дБ, для завмирань 0…40 дБ.`;
      } else if (Number.isFinite(g.gain_db)) {
        gain.textContent = `Виграш Евкліда при BER ${fmt(g.target_ber)}: ${db(g.gain_db)} дБ${hasCi ? `, 95 % ДІ [${db(ci[0])}; ${db(ci[1])}]` : ' (точності недостатньо: потрібно більше кадрів)'}.`;
      } else if (rows.length >= 2) {
        gain.textContent = `Виграш при BER ${fmt(g.target_ber ?? c.target_ber)} не оцінено: обидві криві мають перетнути цей рівень у межах сітки.`;
      }
      if (gain.textContent) panel.append(gain);
      if (rows.length >= 2 && anyErrors) panel.append(plot(rows, Number(g.target_ber ?? c.target_ber)));
    }

    function plot(rows, target) {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('viewBox', '0 0 1200 500');
      svg.setAttribute('aria-label', 'BER Хемінга та Евкліда від Eb/N0');
      svg.style.width = '100%';
      const el = (tag, attrs, text) => {
        const n = document.createElementNS(ns, tag);
        for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
        if (text !== undefined) n.textContent = text;
        svg.append(n); return n;
      };
      const ys = rows.flatMap(r => arms.map(([k]) => r.ber?.[k])).filter(v => Number.isFinite(v) && v > 0);
      const lo = Math.floor(Math.log10(Math.min(...ys, Number.isFinite(target) && target > 0 ? target : Infinity)));
      const hi = Math.max(lo + 1, Math.ceil(Math.log10(Math.max(...ys))));
      const x0 = rows[0].gamma_db, x1 = rows.at(-1).gamma_db;
      const x = v => 90 + (v - x0) / (x1 - x0) * 1030, y = v => 440 - (Math.log10(v) - lo) / (hi - lo) * 400;
      const sup = d => String(d).replace('-', '−').split('').map(ch => ({'−': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹'}[ch])).join('');
      for (let d = lo; d <= hi; d++) {
        el('line', {x1: 90, x2: 1120, y1: y(10 ** d), y2: y(10 ** d), stroke: '#e3e9ec'});
        el('text', {x: 80, y: y(10 ** d) + 5, 'font-size': 14, 'text-anchor': 'end', fill: '#3f5161'}, `10${sup(d)}`);
      }
      el('rect', {x: 90, y: 40, width: 1030, height: 400, fill: 'none', stroke: '#c9d5da'});
      for (const r of rows) el('text', {x: x(r.gamma_db), y: 462, 'font-size': 14, 'text-anchor': 'middle', fill: '#3f5161'}, db(r.gamma_db));
      el('text', {x: 605, y: 492, 'font-size': 15, 'text-anchor': 'middle', fill: '#3f5161'}, 'Eb/N0, дБ');
      const reference = [];
      for (let k = 0; k <= 60; k++) {
        const g = x0 + (x1 - x0) * k / 60, v = qpskReferenceBer(g);
        if (v >= 10 ** lo && v <= 10 ** hi) reference.push(`${reference.length ? 'L' : 'M'}${x(g)} ${y(v)}`);
      }
      if (reference.length > 1) el('path', {d: reference.join(' '), stroke: '#6b7785', fill: 'none', 'stroke-width': 1.5, 'stroke-dasharray': '6 5'});
      if (Number.isFinite(target) && target > 0 && target >= 10 ** lo) {
        el('line', {x1: 90, x2: 1120, y1: y(target), y2: y(target), stroke: '#9fb3bd', 'stroke-dasharray': '2 4'});
        el('text', {x: 1114, y: y(target) - 6, 'font-size': 13, 'text-anchor': 'end', fill: '#6a7a87'}, `ціль ${fmt(target)}`);
      }
      arms.forEach(([key, label, color], index) => {
        let path = '', connected = false;
        for (const r of rows) {
          const v = r.ber?.[key];
          if (!(v > 0)) { connected = false; continue; }
          path += `${connected ? ' L' : ' M'}${x(r.gamma_db)} ${y(v)}`; connected = true;
          const point = el('circle', {cx: x(r.gamma_db), cy: y(v), r: 5, fill: color});
          const title = document.createElementNS(ns, 'title');
          title.textContent = `${label}: Eb/N0 ${db(r.gamma_db)} дБ, BER ${fmt(v)} (${count(r.bit_errors?.[key])} з ${count(r.bits)})`;
          point.append(title);
        }
        el('path', {d: path.trim(), stroke: color, fill: 'none', 'stroke-width': 2.5});
        el('rect', {x: 100 + index * 130, y: 12, width: 22, height: 4, fill: color});
        el('text', {x: 128 + index * 130, y: 19, fill: '#142433', 'font-size': 14}, label);
      });
      el('path', {d: 'M360 14 L382 14', stroke: '#6b7785', 'stroke-dasharray': '6 5', 'stroke-width': 1.5});
      el('text', {x: 388, y: 19, fill: '#142433', 'font-size': 14}, 'QPSK без кодування');
      return svg;
    }
  });
})(typeof window === 'undefined' ? globalThis : window);
