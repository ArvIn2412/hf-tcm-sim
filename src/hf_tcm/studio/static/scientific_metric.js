(() => {
  "use strict";

  const $ = selector => document.querySelector(selector);
  const state = {jobId: null, timer: null, summary: null, pendingSweep: null, sampleTrials: 0, stage: 'sample', started: 0};
  const palette = {joint: "#087f8c", hamming: "#e8833f", target: "#7464a5", grid: "#dfe7e9"};
  const arms = [
    {key: "hamming", label: "Хемінг", result: "hamming", color: palette.hamming},
    {key: "joint", label: "Евклід", result: "joint", color: palette.joint},
  ];
  const scenarioLabels = {
    awgn: "AWGN без пілотів",
    static: "Статичний multipath [0,3]",
    rician: "Rician AR(1) multipath [0,3]",
  };
  const phaseLabels = {validation: "контрольна перевірка", range_finding: "розвідувальна серія"};
  const studyLabels = {
    "exp03a-pilot-awgn-direct-v1": "AWGN без вирівнювача · початковий контроль",
    "exp03a-pilot-awgn-pilot-v1": "AWGN · пілотне вирівнювання, період 32",
    "exp03a-pilot-static-d3-v1": "Статичний multipath · початковий пілотний контроль",
    "exp03a-pilot-rician-ar1-v1": "Rician AR(1) · початковий пілотний контроль",
    "exp03a-range2-awgn-direct-v1": "AWGN без вирівнювача · уточнення діапазону",
    "exp03a-range2-awgn-pilot-v1": "AWGN · пілотне вирівнювання, період 32",
    "exp03a-range2-static-d3-v1": "Статичний multipath · уточнення діапазону",
    "exp03a-range2-rician-ar1-v1": "Rician AR(1) · пілотне вирівнювання, період 32",
    "exp03a-range2-rician-pilot8-v1": "Rician AR(1) · пілотне вирівнювання, період 8",
  };

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    })[character]);
  }

  function number(id) {
    const value = Number($(id).value);
    if (!Number.isFinite(value)) throw new Error(`Перевірте числове поле ${id}.`);
    return value;
  }

  function channelConfiguration(scenario, variance, seed, rho) {
    const constant = (delay, coefficient) => ({
      delay_samples: delay,
      average_power: coefficient[0] ** 2 + coefficient[1] ** 2,
      k_factor: 0,
      los_phase_rad: 0,
      constant_coefficient: coefficient,
    });
    const common = {
      noise_model: variance > 0 ? "complex_awgn_sample_domain" : "none",
      noise_complex_variance: variance,
      fading_seed: seed + 17,
      noise_seed: seed + 18,
      reveal_noise_variance: true,
      boundary_policy: "zero_extension",
      output_length_policy: "tx_plus_max_delay",
      rng_algorithm: "numpy.PCG64",
    };
    if (scenario === "awgn" || scenario === "awgn-pilot") return {
      ...common, profile_id: "awgn", paths: [constant(0, [1, 0])],
      fading_mode: "constant", correlation: 0, schema_version: "repro03-channel-v1",
    };
    if (scenario === "rician") return {
      ...common,
      profile_id: "rician_ar1_multipath",
      paths: (document.querySelector('#model-delays')?.value || '0,3').split(',').map((d,i)=>({
        delay_samples:Number(d), average_power:Number((document.querySelector('#model-powers')?.value || '1,0.25').split(',')[i]),
        k_factor:Number((document.querySelector('#model-k')?.value || '4,1').split(',')[i]),
        los_phase_rad:Number((document.querySelector('#model-los')?.value || '0,0.7').split(',')[i]),constant_coefficient:null,
      })),
      fading_mode: "rician_ar1", correlation: rho, schema_version: "repro03-channel-v1",
    };
    return {
      ...common,
      profile_id: "static_multipath",
      paths: [constant(0, [1, 0]), constant(3, [0.3, -0.2])],
      fading_mode: "constant", correlation: 0, schema_version: "repro03-channel-v1",
    };
  }

  function updatePilotOverhead() {
    const frame = Math.max(0, Number($("#mx-frame").value));
    const preamble = Math.max(0, Number($("#mx-preamble").value));
    const period = Math.max(1, Number($("#mx-period").value));
    const burst = Math.max(0, Number($("#mx-burst").value));
    const pilotUsed = $("#mx-scenario").value !== "awgn";
    const mask = new Array(frame).fill(false);
    if (pilotUsed) {
      for (let i = 0; i < Math.min(frame, preamble); i++) mask[i] = true;
      for (let start = period; start < frame; start += period) {
        for (let i = start; i < Math.min(frame, start + burst); i++) mask[i] = true;
      }
    }
    const pilotCount = mask.filter(Boolean).length;
    const payloadCount = frame - pilotCount;
    const amplitude = Number($("#mx-amplitude").value) || 0;
    const energyPerPayloadBit = payloadCount ? 4 * frame * amplitude ** 2 / payloadCount : NaN;
    let knownPhases = 0;
    if (pilotUsed) {
      const pattern = [[0, 0], [0, 1], [1, 1], [1, 0]];
      let state = [0, 0], runPosition = 0, inRun = false;
      for (let i = 0; i < frame; i++) {
        if (mask[i]) {
          if (!inRun) { runPosition = 0; inRun = true; }
          const [u0, u1] = pattern[runPosition++ % pattern.length];
          if (state[0] !== null && state[1] !== null) knownPhases++;
          state = [u1, state[0]];
        } else {
          inRun = false;
          state = [null, state[0]];
        }
      }
    }
    const fraction = frame ? 100 * pilotCount / frame : 0;
    const rate = frame ? 2 * payloadCount / frame : 0;
    $("#mx-overhead").textContent = pilotUsed
      ? `Пілоти: ${pilotCount}/${frame} елементів (${fraction.toFixed(1)}% кадру); фаз, відомих після промивання стану: ${knownPhases}; швидкість payload: ${rate.toFixed(3)} біт/елемент; Eᵦ,ᵈ ≈ ${energyPerPayloadBit.toFixed(4)} для A=${amplitude}.`
      : `AWGN контроль без equalizer і пілотів: 0/${frame} накладних елементів; швидкість 2 біт/елемент; Eᵦ,ᵈ=4A²=${energyPerPayloadBit.toFixed(4)} для A=${amplitude}.`;
  }

  function buildConfiguration() {
    const selected = $("#mx-scenario").value;
    const oracle = selected === "oracle";
    const scenario = oracle ? "static" : selected === "awgn-pilot" ? "awgn" : selected;
    const frontendMode = oracle ? "oracle_csi" : selected === "awgn"
      ? "awgn_direct_control" : "pilot_equalized";
    const grid = $("#mx-grid").value.split(",").map(value => Number(value.trim()));
    if (!grid.length || grid.some(value => !Number.isFinite(value)) || new Set(grid).size !== grid.length) {
      throw new Error("Введіть унікальні скінченні рівні енергії через кому.");
    }
    return {
      experiment_id: $("#mx-id").value.trim(), scenario, phase: "range_finding",
      frame_symbols: number("#mx-frame"), energy_grid_db: grid,
      trials_per_point: number("#mx-trials"), root_seed: number("#mx-seed"),
      target_ber: number("#mx-target"), time_budget_seconds: number("#mx-budget"),
      sweep: $("#mx-sweep").value, amplitude: number("#mx-amplitude"),
      channel_config: channelConfiguration(selected, number("#mx-noise"), number("#mx-seed"), number("#mx-rho")),
      frontend_mode: frontendMode, preamble_symbols: number("#mx-preamble"), pilot_period: number("#mx-period"),
      pilot_burst_symbols: number("#mx-burst"), bootstrap_replicates: 5000,
    };
  }

  function getRows() {
    return (state.summary?.aggregates || []).filter(row => Number.isFinite(Number(row.gamma_db)));
  }

  function visibleArms(canvas) {
    const controls = canvas.parentElement.querySelector(`[data-metric-series="${canvas.id}"]`);
    return arms.filter(arm => controls?.querySelector(`[data-arm="${arm.key}"]`)?.checked);
  }

  function ensureSeriesControls(canvas) {
    let controls = canvas.parentElement.querySelector(`[data-metric-series="${canvas.id}"]`);
    if (controls) return controls;
    controls = document.createElement("div");
    controls.className = "series-controls metric-series-controls";
    controls.dataset.metricSeries = canvas.id;
    for (const arm of arms) {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" checked data-arm="${arm.key}"><span class="series-swatch" style="--series-color:${arm.color}"></span><span>${arm.label}</span>`;
      controls.append(label);
      label.querySelector("input").addEventListener("change", () => {
        renderMetricPlot(canvas.id);
        updateExportButtons(canvas);
      });
    }
    canvas.before(controls);
    return controls;
  }

  function updateExportButtons(canvas) {
    const enabled = Boolean(state.summary && visibleArms(canvas).length);
    const kind = canvas.id === "metric-ber" ? "ber" : "ser";
    for (const extension of ["png", "svg"]) {
      const button = $(`#metric-${kind}-${extension}`);
      if (button) button.disabled = !enabled;
    }
  }

  function renderMetricPlot(canvasId) {
    const canvas = $(`#${canvasId}`);
    if (!canvas) return;
    const rows = getRows();
    const selectedArms = ensureSeriesControls(canvas) && visibleArms(canvas);
    const kind = canvasId === "metric-ber" ? "ber" : "ser";
    const target = Number(state.summary?.configuration?.target_ber);
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 700;
    const height = canvas.clientHeight || 300;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
    const left = 66, right = width - 18, top = 20, bottom = height - 48;
    context.font = "12px Segoe UI, sans-serif";
    context.textAlign = "center";
    context.fillStyle = "#52646d";
    if (!rows.length || !selectedArms.length) {
      context.textAlign = "left";
      context.fillText(rows.length ? "Усі криві вимкнено." : "Немає завершених вимірювань.", left, top + 20);
      canvas.dataset.exportRendered = "true";
      updateExportButtons(canvas);
      return;
    }
    const xValues = rows.map(row => Number(row.gamma_db));
    const min = Math.min(...xValues), max = Math.max(...xValues);
    const x0 = min === max ? min - 0.5 : min;
    const x1 = min === max ? max + 0.5 : max;
    const px = x => left + (right - left) * (x - x0) / (x1 - x0);
    const py = y => bottom - (bottom - top) * Math.min(1, Math.max(0, y));
    context.strokeStyle = palette.grid;
    context.fillStyle = "#52646d";
    for (let i = 0; i <= 4; i++) {
      const fraction = i / 4;
      const y = top + (bottom - top) * fraction;
      context.beginPath(); context.moveTo(left, y); context.lineTo(right, y); context.stroke();
      context.textAlign = "right"; context.fillText((1 - fraction).toFixed(2), left - 8, y + 4);
      const x = x0 + (x1 - x0) * fraction;
      context.textAlign = "center"; context.fillText(x.toFixed(2), px(x), height - 25);
    }
    context.strokeStyle = "#47616b"; context.lineWidth = 1;
    context.beginPath(); context.moveTo(left, top); context.lineTo(left, bottom); context.lineTo(right, bottom); context.stroke();
    context.save();
    context.translate(15, (top + bottom) / 2); context.rotate(-Math.PI / 2);
    context.textAlign = "center"; context.fillStyle = "#123045";
    context.fillText(`${kind.toUpperCase()} (частка помилок, 0–1)`, 0, 0);
    context.restore();
    context.textAlign = "center"; context.fillStyle = "#123045";
    context.fillText("Нормована дискретна енергетична шкала γᵦ,ᵈ (дБ)", (left + right) / 2, height - 4);
    if (kind === "ber" && Number.isFinite(target) && target >= 0 && target <= 1) {
      const y = py(target);
      context.save(); context.setLineDash([6, 4]); context.strokeStyle = palette.target;
      context.beginPath(); context.moveTo(left, y); context.lineTo(right, y); context.stroke(); context.restore();
      context.fillStyle = palette.target; context.textAlign = "right";
      context.fillText(`Ціль BER ${target}`, right, Math.max(top + 12, y - 5));
    }
    for (const arm of selectedArms) {
      const points = rows.map(row => ({x: Number(row.gamma_db), y: Number(row[kind]?.[arm.result])}));
      context.strokeStyle = arm.color; context.fillStyle = arm.color; context.lineWidth = 2.4;
      context.beginPath();
      points.forEach((point, index) => index ? context.lineTo(px(point.x), py(point.y)) : context.moveTo(px(point.x), py(point.y)));
      context.stroke();
      points.forEach(point => { context.beginPath(); context.arc(px(point.x), py(point.y), 4, 0, 2 * Math.PI); context.fill(); });
    }
    const analysis = state.summary?.gain_analysis || {};
    if (kind === "ber" && analysis.observed_crossing && Number.isFinite(target)) {
      const jointX = analysis.required_gamma_db?.joint;
      const hammingX = analysis.required_gamma_db?.separate;
      const jointVisible = selectedArms.some(arm => arm.key === "joint");
      const hammingVisible = selectedArms.some(arm => arm.key === "hamming");
      for (const [x, arm, isVisible] of [[jointX, arms.find(a=>a.key==='joint'), jointVisible], [hammingX, arms.find(a=>a.key==='hamming'), hammingVisible]]) {
        if (!isVisible || !Number.isFinite(x)) continue;
        context.save(); context.setLineDash([3, 4]); context.strokeStyle = arm.color;
        context.beginPath(); context.moveTo(px(x), top); context.lineTo(px(x), bottom); context.stroke();
        context.fillStyle = arm.color; context.beginPath(); context.arc(px(x), py(target), 5, 0, 2 * Math.PI); context.fill();
        context.restore();
      }
      if (jointVisible && hammingVisible && Number.isFinite(jointX) && Number.isFinite(hammingX)) {
        const arrowY = Math.min(bottom - 10, py(target) + 19);
        context.strokeStyle = "#384d57"; context.fillStyle = "#384d57"; context.lineWidth = 1.5;
        context.beginPath(); context.moveTo(px(jointX), arrowY); context.lineTo(px(hammingX), arrowY); context.stroke();
        for (const [x, direction] of [[px(jointX), 1], [px(hammingX), -1]]) {
          context.beginPath(); context.moveTo(x, arrowY); context.lineTo(x + 6 * direction, arrowY - 4); context.lineTo(x + 6 * direction, arrowY + 4); context.closePath(); context.fill();
        }
        context.font = "11px Segoe UI, sans-serif"; context.textAlign = "center";
        context.fillText(`Δγ ${Number(analysis.gain_db).toFixed(2)} дБ`, (px(jointX) + px(hammingX)) / 2, arrowY + 14);
      }
    }
    canvas.dataset.exportRendered = "true";
    updateExportButtons(canvas);
  }

  function renderTable(summary) {
    const rows = (summary.aggregates || []).map(row => `<tr><td>${Number(row.gamma_db).toFixed(3)}</td><td>${row.trials}</td><td>${row.bits}</td><td>${row.bit_errors.hamming} / ${row.bit_errors.joint}</td><td>${row.ber.hamming.toFixed(6)}</td><td>${row.ber.joint.toFixed(6)}</td><td>${row.ser.hamming.toFixed(6)}</td><td>${row.ser.joint.toFixed(6)}</td></tr>`).join("");
    const scenario = scenarioLabels[summary.configuration?.scenario] || "Порівняння метрик";
    const phase = phaseLabels[summary.phase] || "перевірка";
    $("#mx-summary").innerHTML = `<p>${Number(summary.completed_trials)}/${Number(summary.planned_trials)} парних кадрів · ${scenario} · ${phase} · SHA-256 перевірено</p><div class="metric-table"><table><thead><tr><th>γᵦ,ᵈ (дБ)</th><th>Кадрів</th><th>Бітів</th><th>Бітові помилки Хемінг / Евклід</th><th>BER — Хемінг</th><th>BER — Евклід</th><th>SER — Хемінг</th><th>SER — Евклід</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function renderGainStatus(summary) {
    const element = $("#mx-gain-status");
    const analysis = summary.gain_analysis || {};
    const required = analysis.required_gamma_db;
    const gain = analysis.gain_db;
    const interval = analysis.bootstrap?.confidence_interval_db;
    if (summary.configuration?.frontend_mode === "oracle_csi") {
      element.textContent = "Oracle-CSI є лише діагностичним контролем; результат не включається до практичних висновків.";
      return;
    }
    if (!analysis.observed_crossing || !Number.isFinite(gain) || !Number.isFinite(required?.joint) || !Number.isFinite(required?.separate)) {
      element.textContent = `ENERGY_GAIN_NOT_ESTIMABLE — немає виміряного перетину обох кривих при BER ${summary.configuration?.target_ber}. Екстраполяція не застосовується.`;
      return;
    }
    if (summary.configuration?.trials_per_point < 20 || !Array.isArray(interval) || Number(analysis.bootstrap?.valid_fraction || 0) < 0.95) {
      element.textContent = 'INSUFFICIENT_PRECISION — для довірчого виграшу потрібно щонайменше 20 незалежних кадрів на рівень і ≥95% валідних bootstrap-перетинів.';
      return;
    }
    const intervalText = Array.isArray(interval)
      ? `95% парний кластерний bootstrap-ДІ: [${interval[0].toFixed(3)}, ${interval[1].toFixed(3)}] дБ.`
      : `ДІ не подано: валідних bootstrap-перетинів недостатньо (${(100 * Number(analysis.bootstrap?.valid_fraction || 0)).toFixed(1)}%).`;
    element.textContent = `Розвідувальна модельна оцінка при BER ${summary.configuration?.target_ber}: γᵦ,ᵈ(E)=${required.joint.toFixed(3)} дБ, γᵦ,ᵈ(H)=${required.separate.toFixed(3)} дБ; Δ=H−E=${gain.toFixed(3)} дБ. ${intervalText} Не є фізичним Eb/N0 чи confirmatory-висновком.`;
  }

  function renderSummary(summary, preserveTrace = false) {
    state.summary = summary;
    window.dispatchEvent(new CustomEvent('metric-summary', {detail: {...summary, trace_preserve_existing: preserveTrace}}));
    renderTable(summary);
    renderGainStatus(summary);
    renderMetricPlot("metric-ber");
    renderMetricPlot("metric-ser");
  }

  async function refreshSaved() {
    const response = await api("/api/scientific/metric-studies");
    const select = $("#mx-saved");
    const selected = select.value;
    select.innerHTML = '<option value="">Оберіть перевірену серію</option>' + response.studies.map(item => {
      const label = studyLabels[item.experiment_id] || item.experiment_id;
      const status = {completed: "завершено", incomplete: "перервано", failed: "помилка"}[item.status] || "стан невідомий";
      return `<option value="${escapeHtml(item.experiment_id)}">${escapeHtml(label)} · ${item.completed_trials}/${item.planned_trials} · ${status}</option>`;
    }).join("");
    if (response.studies.some(item => item.experiment_id === selected)) select.value = selected;
  }

  async function openSaved() {
    const id = $("#mx-saved").value;
    if (!id) return;
    renderSummary(await api(`/api/scientific/metric-studies/${encodeURIComponent(id)}`));
    $("#mx-status").textContent = "Збережену серію відкрито після перевірки manifest і SHA-256.";
  }

  let extensionAttempts = 0, extensionSubmitting = false;
  window.addEventListener('metric-extension-approved', async () => {
    if (!state.summary || state.timer || extensionSubmitting || extensionAttempts >= 3 || document.getElementById('article-profile').value==='archive') return;
    const config = structuredClone(state.summary.configuration);
    const grid = config.energy_grid_db;
    config.energy_grid_db = [...new Set([Math.min(...grid)-3, ...grid, Math.max(...grid)+3])].sort((a,b)=>a-b);
    if (config.energy_grid_db.length > 21) { $('#mx-status').textContent='Ліміт 21 енергетична точка.'; return; }
    config.experiment_id = 'ui-extension-' + Date.now();
    config.root_seed += 1000000 + extensionAttempts;
    config.time_budget_seconds = Number(document.getElementById('extension-budget').value);
    if (!Number.isFinite(config.time_budget_seconds) || config.time_budget_seconds < 1 || config.time_budget_seconds > 7200) return;
    extensionAttempts++;
    extensionSubmitting = true;document.getElementById('approve-extension').disabled=true;
    state.pendingSweep = null;state.stage='extension';state.sampleTrials=0;state.started=performance.now();
    try {
      const response = await api('/api/scientific/metric-studies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
      state.jobId=response.job_id;$('#mx-run').disabled=true;$('#mx-stop').disabled=false;
      $('#extension-plan').textContent=`Нова незалежна серія ${config.experiment_id}; сітка ${config.energy_grid_db.join(', ')} дБ; ${config.trials_per_point} trials/точку; всього ${config.energy_grid_db.length*config.trials_per_point}; root seed ${config.root_seed}; бюджет ${config.time_budget_seconds} с. Спроба ${extensionAttempts}/3.`;
      document.getElementById('extension-last-executed').textContent=$('#extension-plan').textContent;
      state.timer=window.setInterval(pollStudy,400);
    } catch(e) { $('#mx-status').textContent=e.message; }
    finally { extensionSubmitting = false; }
  });

  async function startStudy(event) {
    event.preventDefault();
    $("#mx-run").disabled = true;
    $("#mx-status").textContent = "Перевірка параметрів і запуск обмеженої розвідувальної серії…";
    try {
      const config = buildConfiguration();
      state.started = performance.now();
      state.stage = 'sample';
      state.sampleTrials = 0;
      state.pendingSweep = document.querySelector('#article-sweep')?.checked
        ? {...config, experiment_id: config.experiment_id + '-sweep'} : null;
      config.experiment_id += '-sample';
      config.energy_grid_db = [0];
      const response = await api("/api/scientific/metric-studies", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(config),
      });
      state.jobId = response.job_id;
      $("#mx-stop").disabled = false;
      $("#mx-progress").value = 0;
      state.timer = window.setInterval(pollStudy, 400);
      await pollStudy();
    } catch (error) {
      $("#mx-status").textContent = `Серію не запущено: ${error.message}`;
      $("#mx-run").disabled = false;
    }
  }

  async function pollStudy() {
    if (!state.jobId) return;
    try {
      const job = await api(`/api/scientific/jobs/${encodeURIComponent(state.jobId)}`);
      $("#mx-progress").value = job.progress || 0;
      $("#mx-status").textContent = job.status === "running"
        ? `Виконано парних кадрів ${job.completed_trials || 0}/${job.planned_trials || 0}.`
        : job.status === "queued" ? "Серію поставлено в чергу."
          : job.status === "failed" ? `Помилка серії: ${job.error}`
            : `Збережено ${job.completed_trials || 0}/${job.planned_trials || 0} парних кадрів (${job.status}).`;
      $('#mx-status').textContent += ` Стадія: ${state.stage}; час ${((performance.now()-state.started)/1000).toFixed(1)} с.`;
      if(state.stage==='extension'){
        const status=document.getElementById('extension-progress');if(status)status.textContent=$('#mx-status').textContent;
      }
      if (["completed", "incomplete", "failed"].includes(job.status)) {
        clearInterval(state.timer); state.timer = null;
        if (state.stage === 'sample') state.sampleTrials = job.completed_trials || 0;
        $("#mx-run").disabled = false; $("#mx-stop").disabled = true;
        if (job.experiment_id && job.status !== "failed") {
          renderSummary(await api(`/api/scientific/metric-studies/${encodeURIComponent(job.experiment_id)}`), state.stage === 'sweep');
          await refreshSaved();
          $("#mx-saved").value = job.experiment_id;
        }
        if (job.status === 'completed' && state.pendingSweep) {
          const config = state.pendingSweep; state.pendingSweep = null;
          state.stage = 'sweep';
          const response = await api('/api/scientific/metric-studies', {
            method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(config),
          });
          state.jobId = response.job_id;
          $('#mx-run').disabled = true; $('#mx-stop').disabled = false;
          state.timer = window.setInterval(pollStudy,400);
        } else {
          $('#mx-status').textContent += ` Демонстраційні кадри: ${state.sampleTrials}; додаткові sweep-кадри: ${state.stage === 'sweep' ? job.completed_trials || 0 : 0}. Час: ${((performance.now()-state.started)/1000).toFixed(1)} с.`;
          if(state.stage==='extension')$('#mx-status').textContent+=` Нова адаптивна серія: ${job.completed_trials||0}/${job.planned_trials||0} парних кадрів.`;
          if(extensionAttempts>=3)document.getElementById('approve-extension').disabled=true;
        }
      }
    } catch (error) {
      clearInterval(state.timer); state.timer = null;
      $("#mx-run").disabled = false; $("#mx-stop").disabled = true;
      $("#mx-status").textContent = `Не вдалося отримати стан серії: ${error.message}`;
    }
  }

  async function stopStudy() {
    state.pendingSweep = null;
    if (!state.jobId) return;
    try {
      await api(`/api/scientific/jobs/${encodeURIComponent(state.jobId)}/stop`, {method: "POST"});
      $("#mx-status").textContent = "Зупинку запитано; поточний парний кадр буде збережено.";
      $("#mx-stop").disabled = true;
    } catch (error) { $("#mx-status").textContent = error.message; }
  }

  function svgEscape(value) {
    return String(value).replace(/[&<>"']/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&apos;"})[character]);
  }

  function exportSvg(canvasId) {
    const canvas = $(`#${canvasId}`);
    const rows = getRows();
    const selected = visibleArms(canvas);
    if (!rows.length || !selected.length || canvas.dataset.exportRendered !== "true") return;
    const kind = canvasId === "metric-ber" ? "ber" : "ser";
    const width = 1200, height = 620, left = 90, right = 1160, top = 35, bottom = 545;
    const values = rows.map(row => Number(row.gamma_db));
    const min = Math.min(...values), max = Math.max(...values);
    const x0 = min === max ? min - 0.5 : min, x1 = min === max ? max + 0.5 : max;
    const px = x => left + (right - left) * (x - x0) / (x1 - x0);
    const py = y => bottom - (bottom - top) * Math.min(1, Math.max(0, y));
    const pieces = [`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
      `<defs><marker id="metric-arrow" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto-start-reverse"><path d="M0 0L7 3.5L0 7Z" fill="#384d57"/></marker></defs>`,
      `<rect width="100%" height="100%" fill="#fff"/>`,
      `<text x="${width / 2}" y="25" text-anchor="middle" font-family="Arial,sans-serif" font-size="20">${kind.toUpperCase()} · порівняння метрик</text>`];
    for (let i = 0; i <= 4; i++) {
      const y = top + (bottom - top) * i / 4;
      pieces.push(`<path d="M${left} ${y}H${right}" stroke="${palette.grid}"/>`);
      pieces.push(`<text x="${left - 12}" y="${y + 5}" text-anchor="end" font-family="Arial,sans-serif" font-size="14">${(1 - i / 4).toFixed(2)}</text>`);
      const x = x0 + (x1 - x0) * i / 4;
      pieces.push(`<text x="${px(x)}" y="${bottom + 24}" text-anchor="middle" font-family="Arial,sans-serif" font-size="14">${x.toFixed(2)}</text>`);
    }
    pieces.push(`<path d="M${left} ${top}V${bottom}H${right}" fill="none" stroke="#47616b" stroke-width="1.5"/>`);
    pieces.push(`<text x="${(left + right) / 2}" y="${height - 20}" text-anchor="middle" font-family="Arial,sans-serif" font-size="16">Нормована дискретна енергетична шкала γᵦ,ᵈ (дБ)</text>`);
    pieces.push(`<text transform="translate(25 ${(top + bottom) / 2}) rotate(-90)" text-anchor="middle" font-family="Arial,sans-serif" font-size="16">${kind.toUpperCase()} (частка помилок, 0–1)</text>`);
    const target = Number(state.summary?.configuration?.target_ber);
    if (kind === "ber" && Number.isFinite(target) && target >= 0 && target <= 1) {
      pieces.push(`<path d="M${left} ${py(target)}H${right}" stroke="${palette.target}" stroke-dasharray="7 5"/>`);
      pieces.push(`<text x="${right - 4}" y="${py(target) - 8}" text-anchor="end" fill="${palette.target}" font-family="Arial,sans-serif" font-size="14">Ціль BER ${target}</text>`);
    }
    selected.forEach((arm, index) => {
      const points = rows.map(row => ({x: Number(row.gamma_db), y: Number(row[kind]?.[arm.result])}));
      const path = points.map((point, i) => `${i ? "L" : "M"}${px(point.x)} ${py(point.y)}`).join(" ");
      pieces.push(`<path d="${path}" fill="none" stroke="${arm.color}" stroke-width="3"/>`);
      for (const point of points) pieces.push(`<circle cx="${px(point.x)}" cy="${py(point.y)}" r="5" fill="${arm.color}"/>`);
      const legendY = 580;
      pieces.push(`<path d="M${left + index * 250} ${legendY}h24" stroke="${arm.color}" stroke-width="4"/>`);
      pieces.push(`<text x="${left + index * 250 + 32}" y="${legendY + 5}" font-family="Arial,sans-serif" font-size="15">${svgEscape(arm.label)}</text>`);
    });
    const analysis = state.summary?.gain_analysis || {};
    if (kind === "ber" && analysis.observed_crossing && Number.isFinite(target)) {
      const jointX = analysis.required_gamma_db?.joint;
      const hammingX = analysis.required_gamma_db?.separate;
      const jointVisible = selected.some(arm => arm.key === "joint");
      const hammingVisible = selected.some(arm => arm.key === "hamming");
      for (const [x, arm, isVisible] of [[jointX, arms.find(a=>a.key==='joint'), jointVisible], [hammingX, arms.find(a=>a.key==='hamming'), hammingVisible]]) {
        if (!isVisible || !Number.isFinite(x)) continue;
        pieces.push(`<path d="M${px(x)} ${top}V${bottom}" stroke="${arm.color}" stroke-dasharray="4 5"/>`);
        pieces.push(`<circle cx="${px(x)}" cy="${py(target)}" r="6" fill="${arm.color}"/>`);
      }
      if (jointVisible && hammingVisible && Number.isFinite(jointX) && Number.isFinite(hammingX)) {
        const arrowY = Math.min(bottom - 8, py(target) + 20);
        pieces.push(`<path d="M${px(jointX)} ${arrowY}H${px(hammingX)}" stroke="#384d57" stroke-width="1.5" marker-start="url(#metric-arrow)" marker-end="url(#metric-arrow)"/>`);
        pieces.push(`<text x="${(px(jointX) + px(hammingX)) / 2}" y="${arrowY + 17}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13">Δγ ${Number(analysis.gain_db).toFixed(2)} дБ</text>`);
      }
    }
    pieces.push("</svg>");
    const blob = new Blob([pieces.join("")], {type: "image/svg+xml;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url;
    anchor.download = `${state.summary.experiment_id}-${kind}.svg`;
    anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportPng(canvasId) {
    const canvas = $(`#${canvasId}`);
    if (!canvas || canvas.dataset.exportRendered !== "true" || !visibleArms(canvas).length) return;
    const link = document.createElement("a");
    link.download = `${state.summary.experiment_id}-${canvasId.endsWith("ber") ? "ber" : "ser"}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  $("#metric-study-form").addEventListener("submit", startStudy);
  $("#mx-stop").addEventListener("click", stopStudy);
  $("#mx-open").addEventListener("click", () => openSaved().catch(error => { $("#mx-summary").textContent = error.message; }));
  $("#metric-ber-svg").addEventListener("click", () => exportSvg("metric-ber"));
  $("#metric-ser-svg").addEventListener("click", () => exportSvg("metric-ser"));
  $("#metric-ber-png").addEventListener("click", () => exportPng("metric-ber"));
  $("#metric-ser-png").addEventListener("click", () => exportPng("metric-ser"));
  ["#mx-frame", "#mx-preamble", "#mx-period", "#mx-burst", "#mx-amplitude", "#mx-scenario"].forEach(selector => {
    $(selector).addEventListener("input", updatePilotOverhead);
    $(selector).addEventListener("change", updatePilotOverhead);
  });
  window.addEventListener("resize", () => { if (state.summary) { renderMetricPlot("metric-ber"); renderMetricPlot("metric-ser"); } });
  document.querySelector('[data-view="metric"]')?.addEventListener("click", () => {
    window.setTimeout(() => { if (state.summary) { renderMetricPlot("metric-ber"); renderMetricPlot("metric-ser"); } }, 0);
  });
  updatePilotOverhead();
  refreshSaved().catch(error => { $("#mx-status").textContent = `Список серій недоступний: ${error.message}`; });
})();
