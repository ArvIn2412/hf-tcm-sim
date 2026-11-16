(() => {
  const state = {runId: null, summary: null, trace: null, viterbi: null, longFrameArchive: null, selectedSymbol: 0, selectedSample: 0, selectedTransition: null, jobId: null, timer: null, energyJobId: null, energyTimer: null, energySummary: null, exp03bResults: null, activeView: "parameters"};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const esc = (value) => String(value).replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
  const fmt = (value, digits = 5) => Number(value).toLocaleString("uk-UA", {maximumFractionDigits: digits});

  async function api(url, options) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
    return body;
  }

  function selectView(name) {
    state.activeView = name;
    $$(".tab").forEach(button => button.classList.toggle("active", button.dataset.view === name));
    $$(".view").forEach(section => section.classList.toggle("active", section.id === `view-${name}`));
    if (name === "saved") refreshRuns();
    if (name === "statistical") { refreshEnergyStudies(); updateEnergyConfigPreview(); }
    if (name === "energy") { if (state.energySummary) renderEnergyStudy(state.energySummary); refreshPlotExportButtons(); }
    if (state.trace && name === "comparison") drawAll();
    if (["transmitter", "channel", "joint", "separate", "viterbi"].includes(name)) loadWindow();
    window.dispatchEvent(new CustomEvent('scientific-view',{detail:name}));
  }

  function configFromForm() {
    const form = new FormData($("#run-form"));
    const profile = form.get("channel_profile");
    let delays = [0], coeffs = [[1, 0]];
    if (profile === "static_multipath") {
      delays = [0, 3];
      coeffs = [[Number($("#h0i").value), Number($("#h0q").value)], [Number($("#h1i").value), Number($("#h1q").value)]];
    } else if (profile === "static_single_path") {
      coeffs = [[Number($("#h0i").value), Number($("#h0q").value)]];
    } else if (profile === "rician_ar1_multipath") {
      delays = [0, 3];
    }
    return {
      frame_symbols: Number(form.get("frame_symbols")),
      source_seed: Number(form.get("source_seed")),
      channel_seed: Number(form.get("channel_seed")),
      amplitude: Number(form.get("amplitude")),
      channel_profile: profile,
      noise_variance: Number(form.get("noise_variance")),
      delays_samples: delays,
      path_coefficients: coeffs,
      path_powers: [1, 0.25],
      rician_k_factors: [4, 1],
      los_phases_rad: [0, 0.7],
      fading_correlation: 0.98,
      traceback_depth: 20,
      include_b1: $("#include-b1").checked && profile !== "rician_ar1_multipath"
    };
  }

  async function startRun(event) {
    event.preventDefault();
    const button = $("#run-button");
    button.disabled = true;
    $("#job-status").textContent = "Перевірка конфігурації…";
    try {
      const queued = await api("/api/scientific/run", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(configFromForm())});
      state.jobId = queued.job_id;
      $("#job-status").textContent = "Запуск у фоні. Інтерфейс залишається доступним.";
      state.timer = window.setInterval(pollJob, 400);
    } catch (error) {
      $("#job-status").textContent = `Конфігурацію не прийнято: ${error.message}`;
      button.disabled = false;
    }
  }

  async function pollJob() {
    if (!state.jobId) return;
    try {
      const job = await api(`/api/scientific/jobs/${encodeURIComponent(state.jobId)}`);
      $("#job-status").textContent = job.status === "running" ? "Виконується моделювання…" : job.status === "queued" ? "У черзі…" : job.status === "completed" ? "Симуляцію завершено · результати збережено." : `Помилка: ${job.error}`;
      if (["completed", "failed"].includes(job.status)) {
        clearInterval(state.timer); state.timer = null; $("#run-button").disabled = false;
        if (job.status === "completed") {
          await loadRun(job.run_id);
          if (document.getElementById("es-auto-after-run")?.checked) {
            selectView("statistical");
            await launchEnergyStudy();
          }
        }
      }
    } catch (error) {
      clearInterval(state.timer); state.timer = null; $("#run-button").disabled = false;
      $("#job-status").textContent = `Не вдалося отримати стан завдання: ${error.message}`;
    }
  }

  function metricList(target, entries) {
    $(target).innerHTML = entries.map(([label, value]) => `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  }

  function renderSingleRunEnergy(summary) {
    const e = summary.energy;
    if (!e) {
      $("#energy-single-values").textContent = "Для архівного запуску немає збереженого енергетичного підсумку.";
      return;
    }
    const entries = [
      ["Енергія переданих відліків Σ|x[n]|²", fmt(e.tx_energy_discrete, 8)],
      ["Енергія на інформаційний біт E_b,d", fmt(e.energy_per_information_bit_discrete, 8)],
      ["Амплітуда A", fmt(e.amplitude, 8)],
      ["Комплексна дисперсія шуму σ²_c", fmt(e.noise_variance_complex_per_sample, 8)],
      ["Нормоване відношення γ_b,d", e.gamma_b_d_db === null ? "Не визначено за нульового шуму" : `${fmt(e.gamma_b_d_db, 5)} дБ`],
      ["Інформаційна швидкість", `${e.information_bits_per_symbol} біт/елемент`],
      ["Перевірка E_b,d = 4A²", e.energy_relation_valid ? "Збігається з фактичними samples" : "Не збігається — перевірте Tx trace"],
      ["Відліки передавача", `${e.sample_count} (${e.symbol_count} елементів)`]
    ];
    for (const [key, label] of [["joint", "Спільне приймання — метрика Евкліда"], ["separate", "Роздільне приймання — метрика Хемінга"], ["b1", "Роздільне приймання з оцінюванням каналу — метрика Хемінга"]]) {
      const receiver = summary[key];
      if (!receiver) continue;
      entries.push(
        [`${label}: BER / SER інформаційних пар`, `${fmt(receiver.ber, 6)} / ${fmt(receiver.ser, 6)}`],
        [`${label}: помилкові біти / пари`, `${receiver.bit_errors}/${receiver.compared_bits} / ${receiver.symbol_errors}/${receiver.compared_symbols}`]
      );
    }
    metricList("#energy-single-values", entries);
  }

  function clearEnergyStudyDisplay() {
    state.energySummary = null;
    $("#energy-study-results").textContent = "Відкрийте збережену серію або запустіть статистичне дослідження.";
    $("#energy-gain-status").textContent = "Енергетичний виграш не визначається за одним кадром.";
    $("#energy-range-diagnostic").hidden = true;
    $("#es-study-summary").textContent = "Статистичну серію не відкрито.";
    for (const id of ["energy-ber", "energy-ser", "energy-gain", "energy-efficiency"]) {
      const canvas = document.getElementById(id);
      if (!canvas) continue;
      canvas.dataset.exportRendered = "false";
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    refreshPlotExportButtons();
  }

  async function loadRun(runId) {
    const summary = await api(`/api/scientific/runs/${encodeURIComponent(runId)}`);
    $$('canvas[id]').forEach(canvas => { canvas.dataset.exportRendered = "false"; });
    state.runId = runId; state.summary = summary; state.longFrameArchive = null; $("#survivor-endpoint").value="";
    clearEnergyStudyDisplay();
    window.dispatchEvent(new CustomEvent('scientific-summary',{detail:summary}));
    refreshPlotExportButtons();
    state.selectedSymbol = 0; state.selectedSample = 0; state.selectedTransition = null;
    $("#paired-badge").textContent = summary.paired_observation_verified ? "Обидва приймачі використали одне спостереження" : "Спостереження не збігаються";
    $("#paired-badge").classList.toggle("status-partial", !summary.paired_observation_verified);
    const receiverKeys = ["joint", "separate", ...(summary.b1 ? ["b1"] : [])];
    const cards = receiverKeys.map(key => {
      const r = summary[key], title = key === "joint" ? "Спільна демодуляція та декодування — метрика Евкліда" : key === "b0" || key === "separate" ? "Роздільна демодуляція та декодування — метрика Хемінга" : "Роздільне приймання з компенсацією каналу — метрика Хемінга";
      const pairText = Number.isFinite(r.information_pair_ser) ? `SER інформаційних пар ${fmt(r.information_pair_ser, 7)} · ${r.information_pair_errors}/${r.compared_information_pairs} пар` : "SER інформаційних пар недоступний";
      const phaseText = Number.isFinite(r.phase_symbol_ser) ? `SER фаз 8PSK (${key==='joint'?'відновлені після декодування':'жорсткі рішення до декодування'}) ${fmt(r.phase_symbol_ser, 7)} · ${r.phase_symbol_errors}/${r.compared_phase_symbols} фаз` : "SER фаз 8PSK недоступний";
      return `<article class="card receiver-card"><h2>${title}</h2><div class="big-metric">BER ${fmt(r.ber, 7)}</div><div class="receiver-meta">${r.bit_errors} помилок / ${r.compared_bits} бітів<br>${pairText}<br>${phaseText}<br>Вітербі, η=${r.traceback_depth}<br>Час: ${fmt(r.runtime_seconds, 3)} с</div></article>`;
    }).join("");
    $("#comparison-cards").innerHTML = cards;
    metricList("#joint-result", [["BER", fmt(summary.joint.ber, 7)], ["Помилки", `${summary.joint.bit_errors}/${summary.joint.compared_bits}`], ["Стани / переходи", `${summary.joint.trellis_state_count} / ${summary.joint.trellis_edge_count}`]]);
    metricList("#separate-result", [["BER", fmt(summary.separate.ber, 7)], ["Помилки", `${summary.separate.bit_errors}/${summary.separate.compared_bits}`], ["Декодер", "Viterbi · Hamming"]]);
    metricList("#channel-values", [["Відліки", summary.sample_count], ["Шум", "Дисперсія на комплексний відлік"]]);
    metricList("#joint-values", [["Метрика", "Квадрат евклідової відстані"], ["Решітка", `${summary.joint.trellis_state_count} станів / ${summary.joint.trellis_edge_count} переходів`], ["Оцінювання каналу", "Адаптивне"]]);
    metricList("#separate-values", [["Демодуляція", "Жорсткі рішення 8PSK"], ["Метрика", "Відстань Хемінга"], ["Спільне спостереження", summary.paired_observation_verified ? "Так" : "Ні"]]);
    renderSingleRunEnergy(summary);
    $("#window-start-tx").max = Math.max(0, summary.frame_symbols - 1);
    $("#window-start-channel").max = Math.max(0, summary.frame_symbols - 1);
    $("#selected-symbol-joint").max = Math.max(0, summary.frame_symbols - 1);
    $("#selected-symbol-separate").max = Math.max(0, summary.frame_symbols - 1);
    $("#global-symbol").max = Math.max(0, summary.frame_symbols - 1);
    $("#viterbi-symbol").max = Math.max(0, summary.frame_symbols - 1);
    $("#global-sample").max = Math.max(0, summary.sample_count - 1);
    const receiverSelect = $("#global-receiver");
    receiverSelect.querySelector('option[value="b1"]').disabled = !summary.b1;
    if (!summary.b1 && receiverSelect.value === "b1") receiverSelect.value = "joint";
    $("#sync-status").textContent = `Моделювання завершено · ${summary.frame_symbols} елементів сигналу`;
    await loadWindow();
    await refreshRuns();
  }

  async function loadWindow() {
    if (!state.runId) return;
    const global = $("#global-symbol");
    if (global) global.value = String(state.selectedSymbol);
    for (const selector of ["#window-start-tx", "#window-start-channel", "#selected-symbol-joint", "#selected-symbol-separate", "#viterbi-symbol"]) {
      const input = $(selector); if (input) input.value = String(state.selectedSymbol);
    }
    const start = state.selectedSymbol;
    if (state.longFrameArchive) {
      $("#sync-status").textContent = `Архів: ${state.longFrameArchive.repro08_metrics.frame_symbols} символів · відліки I/Q відсутні`;
      if (state.activeView === "viterbi") await loadViterbi();
      return;
    }
    try {
      state.trace = await api(`/api/scientific/traces?run_id=${encodeURIComponent(state.runId)}&start=${start}&count=20`);
      drawAll();
      if (state.activeView === "viterbi") await loadViterbi();
    } catch (error) { console.error(error); }
  }

  function chart(canvas, series, options = {}) {
    if (!canvas) return;
    const originalSeries=series;
    let controls=canvas.parentElement.querySelector(`[data-series-for="${canvas.id}"]`);
    if(!controls){controls=document.createElement('div');controls.className='series-controls';controls.dataset.seriesFor=canvas.id;canvas.before(controls);}
    const signature=series.map(s=>s.label).join('|');
    if(controls.dataset.signature!==signature){controls.dataset.signature=signature;controls.innerHTML=series.map((s,i)=>`<label><input type="checkbox" checked data-series-index="${i}">${esc(s.label)}</label>`).join('');}
    controls.querySelectorAll('input').forEach(input=>input.onchange=()=>chart(canvas,originalSeries,options));
    series=series.map((s,i)=>({...s,colorIndex:i})).filter((s,i)=>controls.querySelector(`[data-series-index="${i}"]`).checked);
    canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth || 800, height = canvas.clientHeight || 300;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, width, height);
    const left = 52, right = width - 18, top = 43, bottom = height - 42;
    const title = canvas.closest(".card")?.querySelector("h2")?.textContent?.trim() || "Графік симуляції";
    ctx.fillStyle = "#123045"; ctx.font = "600 13px Segoe UI, sans-serif";
    // The card is the sole on-screen title; exports keep axes and legend.
    ctx.strokeStyle = "#e3eaec"; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) { const y = top + (bottom-top)*i/4; ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke(); }
    ctx.fillStyle = "#75848c";ctx.font="11px Segoe UI, sans-serif";ctx.fillText(options.ylabel || "Амплітуда", 8, 32);
    ctx.textAlign="center";ctx.fillText(options.xlabel || "Індекс", (left+right)/2, height-9, right-left);ctx.textAlign="left";
    const values = series.flatMap(s => s.values.filter(Number.isFinite));
    if (!values.length) {
      ctx.fillStyle = "#65757e"; ctx.font = "12px Segoe UI, sans-serif";
      ctx.fillText(originalSeries.some(s=>s.values.length)?"Усі криві вимкнено":"Немає даних для цього графіка", left, top + 18);
      canvas.dataset.exportRendered = "true";
      return;
    }
    let min = options.min ?? Math.min(...values), max = options.max ?? Math.max(...values);
    if (min === max) { min -= 1; max += 1; }
    const colors = ["#087f8c", "#ec8b4b", "#7b6cb1", "#55a879", "#d25a6a", "#4e7291"];
    const legend = series.slice(0, 5);
    legend.forEach((item, i) => {
      const x = left + i * Math.max(92, (right-left)/Math.max(1, legend.length));
      ctx.strokeStyle=colors[item.colorIndex%colors.length];ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,top-7);ctx.lineTo(x+14,top-7);ctx.stroke();
      ctx.fillStyle="#50636d";ctx.font="10px Segoe UI, sans-serif";ctx.fillText(item.label || `Серія ${i+1}`,x+18,top-3);
    });
    series.forEach((s, si) => { if (!s.values.length) return; ctx.strokeStyle=colors[s.colorIndex%colors.length];ctx.lineWidth=1.8;ctx.beginPath();s.values.forEach((v,i)=>{const x=left+(right-left)*(series.every(item=>item.values.length<2)?0:i/(Math.max(...series.map(item=>item.values.length))-1));const y=bottom-(bottom-top)*(v-min)/(max-min);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke(); });
    ctx.fillStyle="#60737d";ctx.fillText(fmt(max,3), 5, top+4);ctx.fillText(fmt(min,3), 5, bottom);
    canvas.dataset.exportRendered = "true";
  }

  function plotEnergyCurve(canvas, series, {ylabel, xlabel, target, log = true, crossings = [], gainPairs = []} = {}) {
    if (!canvas) return;
    let controls = canvas.parentElement.querySelector(`[data-series-for="${canvas.id}"]`);
    if (!controls) { controls = document.createElement("div"); controls.className = "series-controls"; controls.dataset.seriesFor = canvas.id; canvas.before(controls); }
    const signature = series.map(item => item.label).join("|");
    if (controls.dataset.signature !== signature) {
      controls.dataset.signature = signature;
      controls.innerHTML = series.map((item, index) => `<label><input type="checkbox" checked data-energy-series="${index}">${esc(item.label)}</label>`).join("");
    }
    controls.querySelectorAll("input").forEach(input => input.onchange = () => plotEnergyCurve(canvas, series, {ylabel, xlabel, target, log, crossings, gainPairs}));
    const visible = series.filter((item, index) => controls.querySelector(`[data-energy-series="${index}"]`).checked);
    canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth || 760, height = canvas.clientHeight || 300;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height);
    const left = 78, right = width - 24, top = 48, bottom = height - 52;
    const all = visible.flatMap(item => item.points.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y)));
    const targetValue = Number.isFinite(target) ? target : null;
    if (!all.length) {
      ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI";
      ctx.fillText(series.some(item => item.points.length) ? "Усі криві вимкнено" : "Немає завершених вимірювань", left, top + 20);
      canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return;
    }
    const xs = all.map(point => point.x), positiveY = all.map(point => point.y).filter(value => value > 0);
    if (targetValue !== null && (!log || targetValue > 0)) positiveY.push(targetValue);
    let xMin = Math.min(...xs), xMax = Math.max(...xs);
    if (xMin === xMax) { xMin -= 0.5; xMax += 0.5; }
    let yMin = log ? (positiveY.length ? 10 ** (Math.floor(Math.log10(Math.min(...positiveY))) - 1) : 1e-6) : Math.min(0, ...all.map(point => point.y));
    let yMax = log ? (positiveY.length ? 10 ** (Math.ceil(Math.log10(Math.max(...positiveY))) + 0.25) : 1) : Math.max(1e-12, ...all.map(point => point.y), targetValue || 0);
    if (!log && yMin === yMax) yMax = yMin + 1;
    const px = x => left + (right - left) * (x - xMin) / (xMax - xMin);
    const py = y => {
      if (log) return y <= 0 ? bottom : bottom - (bottom - top) * (Math.log10(y) - Math.log10(yMin)) / (Math.log10(yMax) - Math.log10(yMin));
      return bottom - (bottom - top) * (y - yMin) / (yMax - yMin);
    };
    ctx.strokeStyle = "#e3eaec"; ctx.fillStyle = "#52646d"; ctx.lineWidth = 1; ctx.font = "11px Segoe UI";
    for (let index = 0; index <= 4; index++) {
      const y = top + (bottom - top) * index / 4;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      const value = log ? 10 ** (Math.log10(yMax) - (Math.log10(yMax) - Math.log10(yMin)) * index / 4) : yMax - (yMax-yMin) * index / 4;
      ctx.fillText(fmt(value, 4), 5, y + 4);
      const xv = xMin + (xMax - xMin) * index / 4;
      ctx.fillText(fmt(xv, 2), px(xv) - 14, height - 26);
    }
    ctx.fillStyle = "#123045"; ctx.font = "600 12px Segoe UI"; ctx.fillText(ylabel || "Частка помилок", 8, 19);
    ctx.textAlign = "center"; ctx.fillText(xlabel || "γ_b,d (дБ)", (left + right) / 2, height - 7); ctx.textAlign = "left";
    if (targetValue !== null && (!log || targetValue >= yMin) && targetValue <= yMax) {
      ctx.save(); ctx.setLineDash([6, 4]); ctx.strokeStyle = "#7b6cb1"; ctx.lineWidth = 1.7;
      ctx.beginPath(); ctx.moveTo(left, py(targetValue)); ctx.lineTo(right, py(targetValue)); ctx.stroke(); ctx.restore();
      ctx.fillStyle = "#665a9a"; ctx.font = "11px Segoe UI"; ctx.fillText(`Ціль BER ${fmt(targetValue, 4)}`, right - 110, py(targetValue) - 5);
    }
    if (targetValue !== null) {
      const colorsByArm = {joint:"#087f8c", b0:"#e8833f", b1:"#7b6cb1"};
      crossings.forEach(item=>{
        if (!Number.isFinite(item.x) || item.x < xMin || item.x > xMax) return;
        const x=px(item.x);ctx.save();ctx.setLineDash([3,4]);ctx.strokeStyle=colorsByArm[item.arm]||"#087f8c";ctx.beginPath();ctx.moveTo(x,py(targetValue));ctx.lineTo(x,bottom);ctx.stroke();ctx.restore();
        ctx.fillStyle=colorsByArm[item.arm]||"#087f8c";ctx.beginPath();ctx.arc(x,py(targetValue),5,0,Math.PI*2);ctx.fill();
        ctx.fillStyle="#40515c";ctx.font="10px Segoe UI";ctx.textAlign="center";ctx.fillText(item.label,x,height-38);ctx.textAlign="left";
      });
      gainPairs.forEach((pair,index)=>{
        if (!Number.isFinite(pair.joint) || !Number.isFinite(pair.separate) || pair.joint<xMin || pair.joint>xMax || pair.separate<xMin || pair.separate>xMax) return;
        const y=py(targetValue)-7-index*8,x0=px(pair.joint),x1=px(pair.separate);ctx.strokeStyle=pair.color;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x0,y);ctx.lineTo(x1,y);ctx.moveTo(x0,y-3);ctx.lineTo(x0,y+3);ctx.moveTo(x1,y-3);ctx.lineTo(x1,y+3);ctx.stroke();ctx.fillStyle=pair.color;ctx.font="10px Segoe UI";ctx.textAlign="center";ctx.fillText(`Δ=${fmt(Math.abs(pair.separate-pair.joint),2)} дБ`,(x0+x1)/2,y-3);ctx.textAlign="left";
      });
    }
    const palette = ["#087f8c", "#e8833f", "#7b6cb1"];
    visible.forEach((item, index) => {
      const color = palette[series.indexOf(item) % palette.length];
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
      let previous = null;
      for (const point of item.points) {
        const x = px(point.x), y = py(point.y);
        if (point.y > 0 && previous) { ctx.beginPath(); ctx.moveTo(previous.x, previous.y); ctx.lineTo(x, y); ctx.stroke(); }
        if (point.y > 0) previous = {x, y}; else previous = null;
        ctx.beginPath();
        if (point.y > 0) ctx.arc(x, y, 4, 0, Math.PI * 2);
        else { ctx.moveTo(x, bottom - 2); ctx.lineTo(x - 4, bottom - 9); ctx.lineTo(x + 4, bottom - 9); ctx.closePath(); }
        ctx.fill();
      }
      const legendX = left + index * Math.min(190, (right - left) / Math.max(1, visible.length));
      ctx.strokeStyle = color; ctx.beginPath(); ctx.moveTo(legendX, top - 13); ctx.lineTo(legendX + 16, top - 13); ctx.stroke();
      ctx.fillStyle = "#40515c"; ctx.font = "11px Segoe UI"; ctx.fillText(item.label, legendX + 21, top - 9, 155);
    });
    if (all.some(point => point.y === 0) && log) {
      ctx.fillStyle = "#687982"; ctx.font = "10px Segoe UI";
      ctx.fillText("Трикутник унизу: 0 помилок у вибірці; це не оцінка P=0.", left, bottom + 20);
    }
    canvas.dataset.exportRendered = "true"; refreshPlotExportButtons();
  }

  // Energy probability charts use a fixed linear [0, 1] scale. The external
  // checkbox row is the single legend and also provides per-series control.
  function plotEnergyCurve(canvas, series, {ylabel, xlabel, target, crossings = [], gainPairs = []} = {}) {
    if (!canvas) return;
    canvas.dataset.yMin = "0";
    canvas.dataset.yMax = "1";
    const palette = {joint: "#087f8c", b0: "#e8833f", b1: "#7b6cb1"};
    const colorFor = (item, index) => palette[item.arm] || ["#087f8c", "#e8833f", "#7b6cb1"][index % 3];
    let controls = canvas.parentElement.querySelector(`[data-series-for="${canvas.id}"]`);
    if (!controls) {
      controls = document.createElement("div");
      controls.className = "series-controls";
      controls.dataset.seriesFor = canvas.id;
      canvas.before(controls);
    }
    const signature = series.map(item => `${item.arm || ""}:${item.label}`).join("|");
    if (controls.dataset.signature !== signature) {
      controls.dataset.signature = signature;
      controls.innerHTML = series.map((item, index) => `<label><input type="checkbox" checked data-energy-series="${index}"><span class="series-swatch" style="--series-color:${colorFor(item, index)}"></span><span>${esc(item.label)}</span></label>`).join("");
    }
    controls.querySelectorAll("input").forEach(input => {
      input.onchange = () => plotEnergyCurve(canvas, series, {ylabel, xlabel, target, crossings, gainPairs});
    });
    const visible = series.filter((item, index) => controls.querySelector(`[data-energy-series="${index}"]`).checked);
    canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 760, height = canvas.clientHeight || 300;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height);
    const left = 84, right = width - 24, top = 28;
    const all = visible.flatMap(item => item.points.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0 && point.y <= 1));
    if (!all.length) {
      ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI, sans-serif";
      ctx.fillText(series.some(item => item.points.length) ? "Усі криві вимкнено" : "Немає завершених вимірювань", left, top + 18);
      canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return;
    }
    const xs = all.map(point => point.x);
    const hasZeroPoint = all.some(point => point.y === 0);
    const bottom = height - (hasZeroPoint ? 76 : 50);
    let xMin = Math.min(...xs), xMax = Math.max(...xs);
    if (xMin === xMax) { xMin -= 0.5; xMax += 0.5; }
    const px = x => left + (right - left) * (x - xMin) / (xMax - xMin);
    const py = y => bottom - (bottom - top) * y;
    ctx.font = "12px Segoe UI, sans-serif";
    for (let index = 0; index <= 4; index++) {
      const fraction = index / 4, y = top + (bottom - top) * fraction;
      ctx.strokeStyle = "#e3eaec"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      ctx.fillStyle = "#52646d"; ctx.textAlign = "right"; ctx.fillText((1 - fraction).toFixed(2), left - 10, y + 4);
      const xValue = xMin + (xMax - xMin) * fraction;
      ctx.textAlign = "center"; ctx.fillText(fmt(xValue, 2), px(xValue), height - 27);
    }
    ctx.textAlign = "left"; ctx.fillStyle = "#123045"; ctx.font = "600 12px Segoe UI, sans-serif";
    ctx.fillText(ylabel || "Частка помилок (0…1)", 8, 17);
    ctx.textAlign = "center"; ctx.fillText(xlabel || "Енергетична шкала γ_b,d (дБ)", (left + right) / 2, height - 6); ctx.textAlign = "left";
    if (Number.isFinite(target) && target >= 0 && target <= 1) {
      ctx.save(); ctx.setLineDash([6, 4]); ctx.strokeStyle = "#7b6cb1"; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.moveTo(left, py(target)); ctx.lineTo(right, py(target)); ctx.stroke(); ctx.restore();
      ctx.fillStyle = "#665a9a"; ctx.font = "11px Segoe UI, sans-serif"; ctx.fillText(`Ціль BER ${fmt(target, 4)}`, Math.max(left + 4, right - 120), py(target) - 5);
    }
    const crossingColors = {joint: "#087f8c", b0: "#e8833f", b1: "#7b6cb1"};
    for (const row of crossings) {
      if (!Number.isFinite(row.x) || row.x < xMin || row.x > xMax) continue;
      const x = px(row.x); ctx.save(); ctx.setLineDash([3, 4]); ctx.strokeStyle = crossingColors[row.arm] || "#40515c";
      ctx.beginPath(); ctx.moveTo(x, py(Number.isFinite(target) ? target : 0)); ctx.lineTo(x, bottom); ctx.stroke(); ctx.restore();
      ctx.fillStyle = crossingColors[row.arm] || "#40515c"; ctx.beginPath(); ctx.arc(x, py(Number.isFinite(target) ? target : 0), 4, 0, Math.PI * 2); ctx.fill();
    }
    gainPairs.forEach((pair, index) => {
      if (!Number.isFinite(pair.joint) || !Number.isFinite(pair.separate) || pair.joint < xMin || pair.joint > xMax || pair.separate < xMin || pair.separate > xMax) return;
      const y = Math.max(top + 12, py(Number.isFinite(target) ? target : 0) - 9 - index * 8), x0 = px(pair.joint), x1 = px(pair.separate);
      ctx.strokeStyle = pair.color || "#40515c"; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.moveTo(x0, y - 3); ctx.lineTo(x0, y + 3); ctx.moveTo(x1, y - 3); ctx.lineTo(x1, y + 3); ctx.stroke();
    });
    visible.forEach((item, visibleIndex) => {
      const index = series.indexOf(item), color = colorFor(item, index);
      const points = item.points.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y) && point.y >= 0 && point.y <= 1).slice().sort((a, b) => a.x - b.x);
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2.2; ctx.beginPath();
      points.forEach((point, pointIndex) => pointIndex ? ctx.lineTo(px(point.x), py(point.y)) : ctx.moveTo(px(point.x), py(point.y)));
      ctx.stroke();
      points.forEach(point => { ctx.beginPath(); ctx.arc(px(point.x), py(point.y), point.y === 0 ? 4.5 : 3.5, 0, Math.PI * 2); ctx.fill(); });
    });
    if (hasZeroPoint) {
      ctx.fillStyle = "#52646d"; ctx.font = "10px Segoe UI, sans-serif";
      ctx.fillText("Нульові точки: 0 помилок у кадрах; це не доказ P=0.", left, bottom + 17);
    }
    canvas.dataset.exportRendered = "true"; refreshPlotExportButtons();
  }

  function plotEnergyGain(summary) {
    const canvas = $("#energy-gain"); if (!canvas) return;
    canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth || 760, height = canvas.clientHeight || 250;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height);
    const analyses = summary.analyses || {}, arms = Object.keys(analyses);
    const estimates = arms.map(arm => ({arm, ...analyses[arm]})).filter(item => Number.isFinite(item.gain_db));
    const left = 82, right = width - 24, top = 44, bottom = height - 48;
    ctx.strokeStyle = "#e4eaec"; ctx.beginPath(); ctx.moveTo(left, bottom); ctx.lineTo(right, bottom); ctx.stroke();
    ctx.fillStyle = "#123045"; ctx.font = "600 12px Segoe UI"; ctx.fillText("Модельний виграш 10 log₁₀(E_b,розд / E_b,спіл), дБ", left, 18);
    if (summary.sweep === "noise") {
      ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI"; ctx.fillText("Зміна дисперсії оцінює поріг γ_b,d, а не необхідну передану енергію.", left, top + 20);
      canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return;
    }
    if (summary.exploratory) {
      ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI"; ctx.fillText("Розвідувальна серія: енергетичний виграш і довірчий інтервал не оцінюються.", left, top + 20);
      canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return;
    }
    if (!estimates.length) {
      ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI"; ctx.fillText("Недостатньо даних для визначення енергетичного виграшу.", left, top + 20);
      canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return;
    }
    const values = estimates.flatMap(item => [item.gain_db, ...(item.bootstrap?.confidence_interval_db || [])]);
    const minimum = Math.min(0, ...values), maximum = Math.max(0, ...values), padding = Math.max(0.5, (maximum - minimum) * 0.15);
    const yMin = minimum < 0 ? minimum - padding : 0, yMax = maximum + padding;
    const py = value => bottom - (bottom - top) * (value - yMin) / (yMax - yMin || 1);
    ctx.strokeStyle = "#9baeb5"; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(left, py(0)); ctx.lineTo(right, py(0)); ctx.stroke(); ctx.setLineDash([]);
    for (let index = 0; index <= 4; index++) {
      const value = yMax - (yMax - yMin) * index / 4, y = py(value);
      ctx.strokeStyle = "#e4eaec"; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      ctx.fillStyle = "#52646d"; ctx.font = "11px Segoe UI"; ctx.fillText(fmt(value, 2), 12, y + 4);
    }
    const names = summary.contrast_mode === "metric" ? {b0: "A-H"} : {b0: "B0", b1: "B1"}, colors = {b0: "#e8833f", b1: "#7b6cb1"};
    estimates.forEach((item, index) => {
      const x = left + (right - left) * (index + 0.5) / estimates.length, y = py(item.gain_db), ci = item.bootstrap?.confidence_interval_db;
      ctx.strokeStyle = colors[item.arm] || "#087f8c"; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2;
      if (ci) { ctx.beginPath(); ctx.moveTo(x, py(ci[0])); ctx.lineTo(x, py(ci[1])); ctx.moveTo(x - 6, py(ci[0])); ctx.lineTo(x + 6, py(ci[0])); ctx.moveTo(x - 6, py(ci[1])); ctx.lineTo(x + 6, py(ci[1])); ctx.stroke(); }
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#40515c"; ctx.font = "11px Segoe UI"; ctx.textAlign = "center"; ctx.fillText(names[item.arm] || item.arm, x, height - 21); ctx.fillText(`${fmt(item.gain_db, 2)} дБ`, x, y - 10); ctx.textAlign = "left";
    });
    canvas.dataset.exportRendered = "true"; refreshPlotExportButtons();
  }

  function plotEnergyEfficiency(summary) {
    const canvas = $("#energy-efficiency"); if (!canvas) return;
    const records = summary.records || [], arms = summary.receiver_arms || [];
    const points = {};
    for (const arm of arms) {
      points[arm] = [];
      for (const gamma of [...new Set(records.map(record => record.gamma_db))].sort((a,b)=>a-b)) {
        const group = records.filter(record => record.gamma_db === gamma);
        const bits = group.reduce((sum, record) => sum + record.bits, 0);
        const symbols = group.reduce((sum, record) => sum + record.frame_symbols, 0);
        const correct = group.reduce((sum, record) => sum + record.bits - record.bit_errors[arm], 0);
        const energy = group.reduce((sum, record) => sum + record.tx_energy, 0);
        points[arm].push({x: correct / symbols, y: correct / energy, gamma});
      }
    }
    const all = Object.values(points).flat(); canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth || 760, height = canvas.clientHeight || 250;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height);
    const left = 85, right = width - 22, top = 44, bottom = height - 50;
    if (!all.length) { ctx.fillStyle = "#52646d"; ctx.font = "14px Segoe UI"; ctx.fillText("Немає завершених вимірювань", left, top + 20); canvas.dataset.exportRendered = "true"; refreshPlotExportButtons(); return; }
    const xMax = Math.max(2, ...all.map(point => point.x)) * 1.05, yMax = Math.max(...all.map(point => point.y)) * 1.08 || 1;
    const px = value => left + (right - left) * value / xMax, py = value => bottom - (bottom - top) * value / yMax;
    ctx.strokeStyle = "#e4eaec"; ctx.fillStyle = "#52646d"; ctx.font = "11px Segoe UI";
    for (let index = 0; index <= 4; index++) { const x = left + (right-left)*index/4, y = top + (bottom-top)*index/4; ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(fmt(xMax*index/4,2),x-12,height-25);ctx.fillText(fmt(yMax*(1-index/4),5),8,y+4); }
    ctx.fillStyle = "#123045";ctx.font="600 12px Segoe UI";ctx.fillText("Успішні інформаційні біти / E_tx,d",8,18);ctx.textAlign="center";ctx.fillText("Успішно прийняті біти на елемент сигналу",(left+right)/2,height-6);ctx.textAlign="left";
    const colors = {joint:"#087f8c",b0:"#e8833f",b1:"#7b6cb1"}, labels = {joint:"Спільне — Евклід",b0:"Роздільне B0 — Хемінг",b1:"Роздільне B1 — канал + Хемінг"};
    arms.forEach(arm=>{const row=points[arm];ctx.strokeStyle=colors[arm];ctx.fillStyle=colors[arm];ctx.lineWidth=2;ctx.beginPath();row.forEach((point,index)=>{const x=px(point.x),y=py(point.y);index?ctx.lineTo(x,y):ctx.moveTo(x,y);ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.beginPath();});ctx.stroke();ctx.fillStyle=colors[arm];ctx.font="11px Segoe UI";ctx.fillText(labels[arm]||arm,left+12,top+14+15*arms.indexOf(arm));});
    canvas.dataset.exportRendered = "true"; refreshPlotExportButtons();
  }

  function plotEnergyEfficiency(summary) {
    const canvas = $("#energy-efficiency");
    if (!canvas) return;
    const records = summary.records || [], arms = summary.receiver_arms || [];
    const labels = {joint:"Спільне приймання — метрика Евкліда",b0:"Роздільне приймання — метрика Хемінга",b1:"Роздільне приймання з оцінюванням каналу — метрика Хемінга"};
    if (summary.contrast_mode === "metric") Object.assign(labels, {joint:"Декодер Вітербі A-E — евклідова метрика",b0:"Декодер Вітербі A-H — метрика Хемінга"});
    const colors = {joint:"#087f8c",b0:"#e8833f",b1:"#7b6cb1"};
    const gammaValues = [...new Set(records.map(record => Number(record.gamma_db)).filter(Number.isFinite))].sort((a,b)=>a-b);
    const series = arms.map(arm => ({arm,label:labels[arm]||arm,points:gammaValues.map(gamma => {
      const rows = records.filter(record => Number(record.gamma_db) === gamma);
      const symbols = rows.reduce((sum, row) => sum + Number(row.frame_symbols || 0), 0);
      const bits = rows.reduce((sum, row) => sum + Number(row.bits || 0), 0);
      const correct = rows.reduce((sum, row) => sum + Number(row.bits || 0) - Number(row.bit_errors?.[arm] || 0), 0);
      const energy = rows.reduce((sum, row) => sum + Number(row.tx_energy || 0), 0);
      return {x:symbols ? correct / symbols : 0,y:energy ? correct / energy : 0};
    })}));
    let controls = canvas.parentElement.querySelector(`[data-series-for="${canvas.id}"]`);
    if (!controls) { controls = document.createElement("div"); controls.className="series-controls"; controls.dataset.seriesFor=canvas.id; canvas.before(controls); }
    const signature = series.map(item=>`${item.arm}:${item.label}`).join("|");
    if (controls.dataset.signature !== signature) {
      controls.dataset.signature = signature;
      controls.innerHTML = series.map((item,index)=>`<label><input type="checkbox" checked data-energy-series="${index}"><span class="series-swatch" style="--series-color:${colors[item.arm]||"#087f8c"}"></span><span>${esc(item.label)}</span></label>`).join("");
    }
    controls.querySelectorAll("input").forEach(input=>input.onchange=()=>plotEnergyEfficiency(summary));
    const visible = series.filter((item,index)=>controls.querySelector(`[data-energy-series="${index}"]`).checked);
    canvas.dataset.exportRendered="false";
    const ratio=window.devicePixelRatio||1,width=canvas.clientWidth||760,height=canvas.clientHeight||250;
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    const ctx=canvas.getContext("2d");ctx.scale(ratio,ratio);ctx.fillStyle="#fff";ctx.fillRect(0,0,width,height);
    const left=88,right=width-24,top=28,bottom=height-50,all=visible.flatMap(item=>item.points);
    if(!all.length){ctx.fillStyle="#52646d";ctx.font="14px Segoe UI,sans-serif";ctx.fillText("Немає завершених вимірювань або всі криві вимкнено",left,top+18);canvas.dataset.exportRendered="true";refreshPlotExportButtons();return;}
    const xMax=Math.max(1,...all.map(point=>point.x))*1.05,yMax=Math.max(1e-12,...all.map(point=>point.y))*1.08;
    const px=value=>left+(right-left)*value/xMax,py=value=>bottom-(bottom-top)*value/yMax;
    for(let index=0;index<=4;index++){
      const fraction=index/4,x=left+(right-left)*fraction,y=top+(bottom-top)*fraction;
      ctx.strokeStyle="#e3eaec";ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
      ctx.fillStyle="#52646d";ctx.font="11px Segoe UI,sans-serif";ctx.textAlign="center";ctx.fillText(fmt(xMax*fraction,2),x,bottom+18);ctx.textAlign="right";ctx.fillText(fmt(yMax*(1-fraction),5),left-8,y+4);
    }
    ctx.fillStyle="#123045";ctx.font="600 12px Segoe UI,sans-serif";ctx.textAlign="left";ctx.fillText("Успішні біти / E_tx,d (дискретна шкала)",8,16);ctx.textAlign="center";ctx.fillText("Успішні біти на елемент сигналу",(left+right)/2,height-5);ctx.textAlign="left";
    visible.forEach(item=>{const color=colors[item.arm]||"#087f8c";ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2.2;ctx.beginPath();item.points.forEach((point,index)=>index?ctx.lineTo(px(point.x),py(point.y)):ctx.moveTo(px(point.x),py(point.y)));ctx.stroke();item.points.forEach(point=>{ctx.beginPath();ctx.arc(px(point.x),py(point.y),3.5,0,Math.PI*2);ctx.fill();});});
    canvas.dataset.exportRendered="true";refreshPlotExportButtons();
  }

  function adaptExp03bResult(results, block, scenario, target = 0.05) {
    const metric = block === "metric";
    const section = metric
      ? results.metric_isolation?.[scenario]?.amplitude_fixed_noise
      : results.full_system_comparison?.[scenario];
    if (!section) throw new Error("Для вибраного сценарію немає підтверджувальних результатів.");
    const sourcePoints = section.point_summaries || [];
    const receiverArms = metric ? ["joint", "b0"] : section.arms;
    const sourceArm = metric ? {joint: "euclidean", b0: "hamming"} : Object.fromEntries(receiverArms.map(arm => [arm, arm]));
    const remapValues = values => Object.fromEntries(receiverArms.map(arm => [arm, values?.[sourceArm[arm]]]));
    const points = sourcePoints.map(point => ({
      ...point,
      ber: remapValues(point.ber),
      ser: remapValues(point.ser_information_pairs),
      ser_information_pairs: remapValues(point.ser_information_pairs),
      fer: remapValues(point.fer),
      bit_errors: remapValues(point.bit_errors),
      pair_errors: remapValues(point.pair_errors),
      frame_errors: remapValues(point.frame_errors),
      bootstrap_95ci: point.bootstrap_95ci ? {
        ...point.bootstrap_95ci,
        ber: remapValues(point.bootstrap_95ci.ber),
        ser_information_pairs: remapValues(point.bootstrap_95ci.ser_information_pairs),
        fer: remapValues(point.bootstrap_95ci.fer)
      } : point.bootstrap_95ci
    }));
    const gainByArm = metric
      ? {b0: section.metric_gain?.[String(target)]}
      : section.energy_gain?.[String(target)];
    const analyses = {};
    for (const arm of receiverArms.filter(value => value !== "joint")) {
      const estimate = gainByArm?.[arm];
      const observed = estimate?.observed?.log_ber || {};
      const euclideanCrossing = observed.euclidean || {};
      const hammingCrossing = observed.hamming || {};
      const crossing = value => Number.isFinite(value.gamma_db)
        ? {status: value.status, required_gamma_db: value.gamma_db, bracket_gamma_db: value.bracket_db}
        : {status: value.status || "NO_CROSSING", required_gamma_db: null};
      const confidence = estimate?.bootstrap?.log_ber || {};
      analyses[arm] = {
        aggregate: points,
        crossings: {joint: crossing(euclideanCrossing), [arm]: crossing(hammingCrossing)},
        gain_db: estimate?.gain_db_log_ber ?? null,
        bootstrap: {
          confidence_interval_db: confidence.gain_db_ci95,
          valid_replicates: confidence.valid_replicates || 0,
          total_replicates: confidence.replicates || 0,
          valid_fraction: confidence.valid_fraction ?? 0
        }
      };
    }
    const records = points.map(point => ({
      gamma_db: point.gamma_db,
      bits: point.bits,
      frame_symbols: point.total_signal_symbols,
      tx_energy: point.tx_energy_discrete,
      bit_errors: metric
        ? {joint: point.bit_errors.euclidean, b0: point.bit_errors.hamming}
        : {...point.bit_errors}
    }));
    const firstPoint = points[0] || {};
    const gainsAvailable = Object.values(analyses).some(item => Number.isFinite(item.gain_db));
    const allCisAvailable = Object.values(analyses).every(item => item.bootstrap.confidence_interval_db);
    return {
      experiment_id: `scientific-exp03b-${block}-${scenario}`,
      contrast_mode: metric ? "metric" : "system",
      status: "completed",
      historical: false,
      exploratory: false,
      completed_trials: section.provenance?.manifest?.completed_trials || 0,
      planned_trials: section.provenance?.manifest?.planned_trials || 0,
      target_ber: target,
      channel_profile: scenario.startsWith("awgn") ? "awgn" : scenario.startsWith("static") ? "static_multipath" : "rician_ar1_multipath",
      sweep: "amplitude",
      receiver_arms: receiverArms,
      analyses,
      records,
      configuration: {
        sweep: "amplitude",
        noise_variance: firstPoint.noise_variance_complex,
        frame_symbols: firstPoint.trials ? firstPoint.total_signal_symbols / firstPoint.trials : null,
        amplitude: null
      },
      energy_gain_status_uk: gainsAvailable && allCisAvailable
        ? "Модельний енергетичний виграш оцінено за виміряними перетинами; це не фізичне Eb/N₀."
        : "Недостатньо даних для визначення енергетичного виграшу.",
      provenance_verified: true,
      analysis_sha256: results.analysis_sha256
    };
  }

  function renderEnergyStudy(summary) {
    state.energySummary = summary;
    const analyses = summary.analyses || {}, first = Object.values(analyses)[0], points = first?.aggregate || [];
    const arms = summary.receiver_arms || [];
    const labels = {joint:"Спільне приймання — метрика Евкліда",b0:"Роздільне приймання — метрика Хемінга",b1:"Роздільне приймання з оцінюванням каналу — метрика Хемінга"};
    if (summary.contrast_mode === "metric") Object.assign(labels, {joint:"Декодер Вітербі A-E — евклідова метрика",b0:"Декодер Вітербі A-H — метрика Хемінга"});
    const berSeries = arms.map(arm=>({arm,label:labels[arm]||arm,points:points.map(point=>({x:Number(point.gamma_db),y:Number(point.ber[arm])}))}));
    const serSeries = arms.map(arm=>({arm,label:labels[arm]||arm,points:points.map(point=>({x:Number(point.gamma_db),y:Number(point.ser[arm])}))}));
    const crossingRows=[];const gainPairs=[];let sharedJoint=null;
    for(const [arm,analysis] of Object.entries(analyses)){
      const joint=analysis.crossings?.joint?.required_gamma_db,separate=analysis.crossings?.[arm]?.required_gamma_db;
      if(Number.isFinite(joint)){sharedJoint=joint;crossingRows.push({arm:"joint",x:joint,label:"Joint"});}
      if(Number.isFinite(separate))crossingRows.push({arm,x:separate,label:arm.toUpperCase()});
      if(!summary.exploratory&&Number.isFinite(joint)&&Number.isFinite(separate))gainPairs.push({joint,separate,color:arm==="b1"?"#7b6cb1":"#e8833f"});
    }
    const uniqueCrossings=[...new Map(crossingRows.map(row=>[`${row.arm}:${row.x}`,row])).values()];
    plotEnergyCurve($("#energy-ber"), berSeries, {ylabel:"BER інформаційних бітів (частка 0–1)",xlabel:"Нормована дискретна шкала γ_b,d (дБ)",target:Number(summary.target_ber),crossings:uniqueCrossings,gainPairs});
    plotEnergyCurve($("#energy-ser"), serSeries, {ylabel:"SER інформаційних пар (частка 0–1)",xlabel:"Нормована дискретна шкала γ_b,d (дБ)"});
    plotEnergyGain(summary); plotEnergyEfficiency(summary);
    $("#energy-gain-status").textContent = summary.energy_gain_status_uk || "Недостатньо даних для визначення енергетичного виграшу.";
    const configuration = summary.configuration || {}, noise = Number(configuration.noise_variance), amplitude = Number(configuration.amplitude);
    const rows = [];
    for (const [arm, analysis] of Object.entries(analyses)) {
      const crossing = analysis.crossings || {}, jointGamma = crossing.joint?.required_gamma_db, separateGamma = crossing[arm]?.required_gamma_db;
      const eb = value => Number.isFinite(value) ? `${fmt(noise * 10 ** (value / 10), 7)} (дискретна E_b,d)` : "не визначено";
      const interval = summary.exploratory ? null : analysis.bootstrap?.confidence_interval_db;
      const gain = configuration.sweep === "noise" ? "Недостатньо даних для визначення енергетичного виграшу: амплітуда тут стала." : summary.exploratory ? "Недостатньо незалежних кадрів для оцінки виграшу; результат розвідувальний." : Number.isFinite(analysis.gain_db) ? `${fmt(analysis.gain_db, 4)} дБ${interval ? ` · 95% ДІ ${fmt(interval[0], 4)}…${fmt(interval[1], 4)} дБ` : " · 95% ДІ недостатньо валідних перетинів"}` : "Недостатньо даних для визначення енергетичного виграшу.";
      rows.push(`<div class="metric"><span>${esc(labels[arm]||arm)}</span><strong>γ_спіл ${Number.isFinite(jointGamma)?`${fmt(jointGamma,3)} дБ`:"—"} · γ_розд ${Number.isFinite(separateGamma)?`${fmt(separateGamma,3)} дБ`:"—"}<br>${configuration.sweep === "amplitude" ? `E_b,d спільного приймача ${eb(jointGamma)} · роздільного ${eb(separateGamma)}` : `Амплітуда стала A=${fmt(amplitude,4)}; оцінено поріг γ, не необхідну амплітуду`}<br>${esc(gain)}<br>Парних bootstrap-вибірок: ${analysis.bootstrap?.valid_replicates||0}/${analysis.bootstrap?.total_replicates||0}</strong></div>`);
    }
    $("#energy-study-results").innerHTML = rows.join("") || "Статистичне дослідження ще не відкрите.";
    const target = Number(summary.target_ber);
    const unavailableArms = arms.filter(arm => points.length && points.every(point => Number(point.ber?.[arm]) > target));
    const diagnostic = $("#energy-range-diagnostic");
    diagnostic.hidden = unavailableArms.length === 0;
    diagnostic.textContent = unavailableArms.length
      ? `Цільовий BER ${fmt(target, 4)} не досягнуто в дослідженому діапазоні енергії для ${unavailableArms.map(arm => labels[arm] || arm).join(", ")}. Можна вручну спланувати ширшу сітку; зафіксовану confirmatory-сітку не змінено. Довжина кадру: ${summary.configuration?.frame_symbols ?? "—"}; кадрів на точку: ${points[0]?.trials ?? "—"}.`
      : "";
    const status = summary.status === "completed" ? "Завершено" : "Перервано; результат можна відновити";
    const exploratory = summary.exploratory ? "Розвідувальний режим: менше 20 незалежних кадрів на точку." : "Не позначено як розвідувальну серію.";
    const origin = summary.historical ? "Перевірена історична серія · provenance підтверджено" : "Поточна серія";
    const channelNames = {identity:"Ідеальний канал",awgn:"AWGN",static_single_path:"Статичний однопроменевий канал",static_multipath:"Статичний багатопроменевий канал",rician_ar1_multipath:"Райсівський багатопроменевий канал AR(1)"};
    const sweepNames = {amplitude:"зміна амплітуди за фіксованого шуму",noise:"зміна шуму за фіксованої амплітуди"};
    $("#es-study-summary").innerHTML = `<div class="metric"><span>${origin}</span><strong>${status} · ${summary.completed_trials}/${summary.planned_trials} кадрів</strong></div><div class="metric"><span>Канал / енергетична сітка / ціль</span><strong>${esc(channelNames[summary.channel_profile] || summary.channel_profile)} · ${esc(sweepNames[summary.sweep] || summary.sweep)} · BER ${fmt(summary.target_ber,5)}</strong></div><div class="metric"><span>Інтерпретація</span><strong>${exploratory}</strong></div><div class="metric"><span>Метод</span><strong>Інтерполяція лише в межах сітки; парний bootstrap за цілими кадрами</strong></div>`;
    refreshPlotExportButtons();
  }

  function refreshPlotExportButtons() {
    const available = Boolean(state.summary || state.mcSummary || state.energySummary || state.longFrameArchive);
    $$("[data-export-canvas]").forEach(button => {
      const canvas = document.getElementById(button.dataset.exportCanvas);
      button.disabled = !available || canvas?.dataset.exportRendered !== "true";
    });
    $$('[data-export-svg]').forEach(button => {
      const graphic = document.getElementById(button.dataset.exportSvg);
      button.disabled = !available || graphic?.dataset.exportRendered !== "true";
    });
  }

  function installPlotExportButtons() {
    $$("canvas[id]").forEach(canvas => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button plot-export-button";
      button.textContent = "Зберегти PNG";
      button.dataset.exportCanvas = canvas.id;
      button.disabled = true;
      button.addEventListener("click", () => {
        const currentCanvas = document.getElementById(button.dataset.exportCanvas);
        if (!currentCanvas || currentCanvas.dataset.exportRendered !== "true" || !currentCanvas.width || !currentCanvas.height) return;
        const runId = state.runId || state.mcSummary?.experiment_id || "saved-result";
        const anchor = document.createElement("a");
        anchor.download = `hf-tcm-${runId}-${currentCanvas.id}-k${state.selectedSymbol}.png`;
        anchor.href = currentCanvas.toDataURL("image/png");
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
      });
      canvas.insertAdjacentElement("beforebegin", button);
    });
    const trellis = $("#trellis-svg");
    if (trellis && !$("[data-export-svg='trellis-svg']")) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button plot-export-button";
      button.textContent = "Зберегти SVG";
      button.dataset.exportSvg = "trellis-svg";
      button.disabled = true;
      button.addEventListener("click", () => {
        const source = $("#trellis-svg");
        if (!source || source.dataset.exportRendered !== "true" || !source.childElementCount) return;
        const clone = source.cloneNode(true);
        clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        clone.setAttribute("width", "1000"); clone.setAttribute("height", "500");
        const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        background.setAttribute("width", "100%"); background.setAttribute("height", "100%"); background.setAttribute("fill", "#ffffff");
        clone.insertBefore(background, clone.firstChild);
        const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
        style.textContent = ".trellis-edge{fill:none;stroke:#b8c5ca;stroke-width:1.1;opacity:.38}.trellis-edge.survivor{stroke:#4c8890;stroke-width:2;opacity:.85}.trellis-edge.selected{stroke:#e06d2f;stroke-width:4;opacity:1}.trellis-node{fill:#fff;stroke:#48636d;stroke-width:1.5}.trellis-node-label{font:11px sans-serif;fill:#42545c}";
        clone.insertBefore(style, background.nextSibling);
        const blob = new Blob([new XMLSerializer().serializeToString(clone)], {type:"image/svg+xml;charset=utf-8"});
        const url = URL.createObjectURL(blob), anchor = document.createElement("a");
        anchor.download = `hf-tcm-${state.runId || "saved-result"}-trellis-k${state.selectedSymbol}.svg`;
        anchor.href = url; document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
      });
      trellis.insertAdjacentElement("beforebegin", button);
    }
    refreshPlotExportButtons();
  }

  function installEnergySvgExportButtons() {
    for (const id of ["energy-ber", "energy-ser", "energy-gain", "energy-efficiency"]) {
      const canvas = document.getElementById(id);
      if (!canvas || document.querySelector(`[data-export-svg="${id}"]`)) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button plot-export-button";
      button.textContent = "Зберегти SVG";
      button.dataset.exportSvg = id;
      button.disabled = true;
      button.addEventListener("click", () => {
        const current = document.getElementById(id);
        if (!current || current.dataset.exportRendered !== "true" || !current.width || !current.height) return;
        const width = current.width, height = current.height;
        const png = current.toDataURL("image/png");
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><image x="0" y="0" width="${width}" height="${height}" href="${png}" xlink:href="${png}"/></svg>`;
        const blob = new Blob([svg], {type:"image/svg+xml;charset=utf-8"});
        const url = URL.createObjectURL(blob), anchor = document.createElement("a");
        anchor.download = `hf-tcm-${state.energySummary?.experiment_id || "energy"}-${id}.svg`;
        anchor.href = url; document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
      });
      canvas.insertAdjacentElement("beforebegin", button);
    }
    refreshPlotExportButtons();
  }

  function constellation(canvas, phaseIndices) {
    if (!canvas) return;
    canvas.dataset.exportRendered = "false";
    const ratio=window.devicePixelRatio||1,width=360,height=360;
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    const ctx=canvas.getContext("2d");ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);ctx.fillStyle="#ffffff";ctx.fillRect(0,0,width,height);
    const cx=width/2,cy=height/2,r=Math.min(width,height)*0.38;
    ctx.fillStyle="#123045";ctx.font="600 13px Segoe UI, sans-serif";
    ctx.strokeStyle="#dbe5e8";ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.moveTo(cx-r-10,cy);ctx.lineTo(cx+r+10,cy);ctx.moveTo(cx,cy-r-10);ctx.lineTo(cx,cy+r+10);ctx.stroke();
    for(let phase=0;phase<8;phase++){const angle=phase*Math.PI/4;const x=cx+r*Math.cos(angle),y=cy-r*Math.sin(angle);ctx.fillStyle="#bcc9ce";ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.fillStyle="#637780";ctx.font="10px Segoe UI";ctx.fillText(String(phase),x+6,y-5);}
    phaseIndices.forEach((phase,index)=>{const angle=phase*Math.PI/4;const x=cx+r*Math.cos(angle),y=cy-r*Math.sin(angle);ctx.fillStyle="#087f8c";ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();});
    ctx.fillStyle="#60737d";ctx.font="11px Segoe UI";ctx.fillText("I",width-16,cy-8);ctx.fillText("Q",cx+7,12);
    canvas.dataset.exportRendered = "true";
  }

  function drawAll() {
    const t = state.trace; if (!t) return;
    const idx = t.absolute_sample_indices.map(String);
    chart($("#chart-tx"), [{values:t.tx_i,label:"Переданий I"},{values:t.tx_q,label:"Переданий Q"}], {ylabel:"I / Q",xlabel:`Відліки ${t.sample_start}–${t.sample_stop-1}`});
    chart($("#chart-channel"), [{values:t.tx_i,label:"Переданий I"},{values:t.tx_q,label:"Переданий Q"},{values:t.received_i,label:"Прийнятий I"},{values:t.received_q,label:"Прийнятий Q"}], {ylabel:"I / Q (нормовані)",xlabel:"Абсолютний індекс комплексного відліку (відліки)"});
    chart($("#chart-paths"), t.path_contributions_i.map((values,i)=>({values,label:`Шлях ${i}`})), {ylabel:"Внесок I",xlabel:"Відлік"});
    chart($("#chart-joint-metrics"), (t.joint_metrics[0] || []).slice(0,5).map((_,i)=>({values:t.joint_metrics.map(row=>row[i]),label:`Перехід ${i}`})), {ylabel:"Метрика переходу",xlabel:"Символ у вікні"});
    chart($("#chart-hamming"), (t.hamming_metrics[0] || []).slice(0,5).map((_,i)=>({values:t.hamming_metrics.map(row=>row[i]),label:`Перехід ${i}`})), {ylabel:"Кількість бітів",xlabel:"Символ у вікні",min:0,max:3});
    $("#transmitter-values").classList.remove("empty");
    $("#transmitter-values").innerHTML = `<table><thead><tr><th>Символ</th><th>Біти</th><th>Кодова трійка</th><th>Стан до → після</th><th>Фаза 8PSK</th></tr></thead><tbody>${t.phase_indices.map((phase,i)=>`<tr class="${i===0?'current-symbol':''}"><td>${t.start_symbol+i}</td><td>${t.information_bits.slice(2*i,2*i+2).join(' ')}</td><td>${t.coded_triples[i].join(' ')}</td><td>${esc(JSON.stringify(t.pre_states[i]))} → ${esc(JSON.stringify(t.post_states[i]))}</td><td>${phase}</td></tr>`).join('')}</tbody></table>`;
    constellation($("#chart-constellation"),t.phase_indices.slice(0,1));
    const errorSeries=[['joint','Спільне — Евклід'],['separate','Роздільне — Хемінг'],...(state.summary.b1?[['b1','З компенсацією каналу']]:[])].map(([key,label])=>{const errors=new Set(state.summary[key].bit_error_positions);return {label,values:Array.from({length:state.summary[key].compared_bits},(_,i)=>Number(errors.has(i)))};});
    chart($("#chart-errors"), errorSeries, {ylabel:"Помилка біта: 0 / 1",xlabel:"Індекс інформаційного біта",min:-0.05,max:1.05,discrete:true});
    if(errorSeries.every(s=>s.values.every(v=>v===0))){const ctx=$("#chart-errors").getContext('2d');ctx.fillStyle='#123045';ctx.fillText('Помилок не виявлено',70,70);}
    refreshPlotExportButtons();
  }

  async function loadViterbi() {
    if (!state.runId || !state.summary) return;
    const receiver = $("#global-receiver").value;
    if (receiver === "b1" && !state.summary.b1) {
      $("#trellis-caption").textContent = "У цьому результаті B1 не запускався.";
      return;
    }
    // The shared navigation state is canonical; the stage-specific input is a
    // view of it and may briefly lag while an async trace request is pending.
    const symbol = Math.max(0, Math.min(Number(state.selectedSymbol), state.summary.frame_symbols - 1));
    const depth = Math.max(1, Number($("#traceback-depth").value || 20));
    const survivorState=$("#survivor-endpoint").value;
    state.selectedSymbol = symbol;
    $("#global-symbol").value = String(symbol);
    try {
      const endpoint = state.longFrameArchive
        ? `/api/scientific/long-frame/viterbi?symbol=${symbol}&depth=${depth}${survivorState===""?"":`&survivor_state=${survivorState}`}`
        : `/api/scientific/viterbi?run_id=${encodeURIComponent(state.runId)}&receiver=${receiver}&symbol=${symbol}&depth=${depth}${survivorState===""?"":`&survivor_state=${survivorState}`}`;
      state.viterbi = await api(endpoint);
      renderViterbi();
    } catch (error) {
      $("#trellis-caption").textContent = `Діагностика недоступна: ${error.message}`;
    }
  }

  function renderViterbi() {
    const trace = state.viterbi, summary = state.summary;
    if (!trace?.available) {
      $("#trellis-caption").textContent = trace?.reason || "Для цього архіву немає збереженої Viterbi diagnostics.";
      $("#trellis-svg").replaceChildren();
      $("#trellis-svg").dataset.exportRendered = "false";
      $("#transition-table").textContent = trace?.reason || "Diagnostics недоступні.";
      refreshPlotExportButtons();
      return;
    }
    const trellis = trace.trellis_nodes
      ? {nodes:trace.trellis_nodes,edges:trace.trellis_edges,state_count:trace.trellis_nodes.length}
      : trace.receiver === "joint" ? summary.trellises.joint : summary.trellises.encoder_a;
    const edges = trace.transitions;
    const nodes = trace.receiver === "joint" ? trellis.nodes : Array.from({length:trellis.state_count},(_,i)=>({node_id:i,encoder_state:edges.find(e=>e.source_state_id===i)?.source_state||[]}));
    const states = nodes.length, steps = trace.traceback_steps || [];
    const endpointSelect=$("#survivor-endpoint"), priorEndpoint=endpointSelect.value;
    endpointSelect.innerHTML='<option value="">Мінімальна метрика</option>'+nodes.map((node,index)=>`<option value="${index}">Стан ${index} ${esc(JSON.stringify(node.encoder_state||[]))}</option>`).join("");
    if(priorEndpoint!==""&&Number(priorEndpoint)<states)endpointSelect.value=priorEndpoint;
    else endpointSelect.value="";
    $("#trellis-title").textContent = `${trace.receiver === "joint" && states > 4 ? "Розширена решітка" : "Решітка кодера"} · ${states} станів / ${edges.length} переходів`;
    $("#trellis-caption").textContent = `${state.longFrameArchive?"Архівна діагностика · відліки сигналу відсутні · ":""}k=${trace.symbol_index} · відліки [${trace.sample_start}, ${trace.sample_stop}) · вікно k=${trace.window_start_symbol}…${trace.window_stop_symbol-1} · кінцевий стан ${trace.endpoint_state_id}`;
    const svg = $("#trellis-svg");
    svg.dataset.exportRendered = "false";
    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    svg.setAttribute("width", "1000"); svg.setAttribute("height", "500");
    const H=500,W=1000,left=58,right=965,top=28,bottom=H-34;
    const y=id=>top+(bottom-top)*(states<=1?0.5:id/(states-1));
    const edgeById=new Map(edges.map(edge=>[Number(edge.edge_id),edge]));
    const local=trace.traceback_local_survivor_path||[];
    const selectedLocal=local.length?Number(local.at(-1).edge_id):null;
    const parts=[]; const pathAt=new Map(local.map(row=>[row.symbol_index,Number(row.edge_id)])); const filter=$("#trellis-filter")?.value||"all";
    for(let si=0;si<steps.length;si++){
      const step=steps[si], x1=left+(right-left)*(steps.length<=1?0:si/steps.length), x2=left+(right-left)*((si+1)/steps.length);
      const selected=new Set(step.survivor_edge_ids_by_destination.map(Number));
      const candidates=si===steps.length-1?edges:edges.filter(edge=>selected.has(Number(edge.edge_id)));
      for(const edge of candidates){
        const source=trace.receiver==="joint"?Number(edge.source_node_id):Number(edge.source_state_id);
        const target=trace.receiver==="joint"?Number(edge.target_node_id):Number(edge.target_state_id);
        const survivor=selected.has(Number(edge.edge_id));
        const onPath=pathAt.get(step.symbol_index)===Number(edge.edge_id);
        if(filter==="path"&&!onPath||filter==="survivors"&&!survivor)continue;
        const active=step.symbol_index===trace.symbol_index&&Number(edge.edge_id)===(state.selectedTransition??selectedLocal);
        const mid=(x1+x2)/2;
        parts.push(`<path class="trellis-edge ${survivor?"survivor":"rejected"} ${onPath?"local-path":""} ${active?"selected":""}" data-edge-id="${edge.edge_id}" data-symbol="${step.symbol_index}" d="M ${x1} ${y(source)} C ${mid} ${y(source)}, ${mid} ${y(target)}, ${x2} ${y(target)}"><title>k=${step.symbol_index}, edge ${edge.edge_id}, metric ${fmt(step.branch_metrics[edge.edge_id],5)}${survivor?", survivor":""}</title></path>`);
      }
    }
    for(let si=0;si<steps.length+1;si++){
      const x=left+(right-left)*(steps.length<=1?0.5:si/steps.length);
      nodes.forEach((node,i)=>{parts.push(`<circle class="trellis-node" cx="${x}" cy="${y(i)}" r="5"><title>State ${i}</title></circle>`);if(si===0)parts.push(`<text class="trellis-node-label" x="8" y="${y(i)+4}">S${i} ${esc(JSON.stringify(node.encoder_state||[]))}</text>`);});
    }
    svg.innerHTML=parts.join("");
    svg.querySelectorAll("[data-edge-id]").forEach(path=>path.addEventListener("click",()=>{
      state.selectedTransition=Number(path.dataset.edgeId);
      svg.querySelectorAll(".trellis-edge.selected").forEach(item=>item.classList.remove("selected"));path.classList.add("selected");
      const edge=edgeById.get(state.selectedTransition);const metric=trace.transitions.find(item=>Number(item.edge_id)===state.selectedTransition)?.branch_metric;
      $("#selected-transition").innerHTML=`<div class="metric"><span>Перехід решітки</span><strong>${edge.edge_id}</strong></div><div class="metric"><span>Стан кодера</span><strong>${edge.source_node_id??edge.source_state_id} → ${edge.target_node_id??edge.target_state_id}</strong></div><div class="metric"><span>Інформаційна пара / кодова трійка</span><strong>${esc(JSON.stringify(edge.input_pair))} / ${esc(JSON.stringify(edge.coded_triple))}</strong></div><div class="metric"><span>Фаза 8PSK / метрика переходу</span><strong>${edge.phase_index} / ${fmt(metric,7)}</strong></div>`;
    }));
    const emitted=trace.emitted_decision_for_selected_symbol, arrival=trace.emitted_decision_on_this_arrival;
    $("#viterbi-decisions").innerHTML=`<div class="metric"><span>Видане рішення для k</span><strong>${emitted?`edge ${emitted.edge_id} · готовність ${emitted.decision_available_at} · глибина ${emitted.traceback_depth_used}`:"Ще не видано або завершення кадру"}</strong></div><div class="metric"><span>Рішення, видане при надходженні цього k</span><strong>${arrival?`source k=${arrival.symbol_index} · перехід ${arrival.edge_id} · глибина ${arrival.traceback_depth_used}`:"немає"}</strong></div><div class="metric"><span>Кінцевий стан локального шляху</span><strong>стан ${trace.endpoint_state_id} · метрика ${fmt(trace.endpoint_metric,7)}</strong></div><div class="metric"><span>Перехід, відновлений із виданих бітів</span><strong>${trace.reconstructed_edge_from_emitted_bits??"недоступно"}</strong></div><div class="metric"><span>η / інтервал відліків</span><strong>${trace.traceback_window_transitions} переходів · ${trace.sample_start}…${trace.sample_stop-1}</strong></div>`;
    const selectedCurrent=new Set(steps.at(-1)?.survivor_edge_ids_by_destination.map(Number)||[]);
    $("#transition-table").innerHTML=`<table><thead><tr><th>Перехід</th><th>Стан</th><th>Біти</th><th>Код</th><th>Фаза</th><th>Метрика переходу</th><th>Рішення</th></tr></thead><tbody>${edges.map(edge=>`<tr class="${selectedCurrent.has(Number(edge.edge_id))?"survivor-row":""}" data-transition-row="${edge.edge_id}"><td>${edge.edge_id}</td><td>${edge.source_node_id??edge.source_state_id}→${edge.target_node_id??edge.target_state_id}</td><td>${esc(JSON.stringify(edge.input_pair))}</td><td>${esc(JSON.stringify(edge.coded_triple))}</td><td>${edge.phase_index}</td><td>${fmt(edge.branch_metric,7)}</td><td>${selectedCurrent.has(Number(edge.edge_id))?"Збережено":"Відхилено"}</td></tr>`).join("")}</tbody></table>`;
    $("#traceback-table").innerHTML=local.map(row=>`<div class="traceback-step ${row.symbol_index===trace.symbol_index?"selected":""}"><button data-trace-symbol="${row.symbol_index}">k=${row.symbol_index} · перехід ${row.edge_id} · ${esc(JSON.stringify(row.input_pair))} → ${esc(JSON.stringify(row.coded_triple))} · φ=${row.phase_index}</button></div>`).join("")||"Локальний шлях недоступний.";
    $$('[data-trace-symbol]').forEach(button=>button.addEventListener("click",()=>setSelectedSymbol(Number(button.dataset.traceSymbol))));
    $("#state-metrics-table").innerHTML=trace.state_metrics.map((value,index)=>`<div class="metric"><span>Стан ${index}</span><strong>${fmt(value,8)}</strong></div>`).join("");
    loadSampleZoom();
    svg.dataset.exportRendered = "true";
    refreshPlotExportButtons();
  }

  async function loadSampleZoom() {
    if (!state.runId || !state.summary) return;
    const count=Math.min(20,state.summary.sample_count), start=Math.max(0,Math.min(state.selectedSample-9,state.summary.sample_count-count));
    try {
      const sample=await api(`/api/scientific/samples?run_id=${encodeURIComponent(state.runId)}&start=${start}&count=${count}`);
      $("#sample-zoom-caption").textContent=`20 комплексних відліків · ${sample.sample_start}…${sample.sample_stop-1} · символ k=${Math.floor(sample.sample_start/8)} · хвіст=${sample.tail_sample.some(Boolean)?"так":"ні"}`;
      chart($("#chart-sample-zoom"),[{values:sample.received_i,label:"Прийнятий I"},{values:sample.received_q,label:"Прийнятий Q"}],{ylabel:"Комплексна амплітуда",xlabel:`Абсолютні відліки ${sample.sample_start}…${sample.sample_stop-1}`});
      state.sampleWindow=sample;
    } catch(error) { $("#sample-zoom-caption").textContent=`Вікно відліків недоступне: ${error.message}`; }
  }

  async function setSelectedSymbol(symbol) {
    if (!state.summary) return;
    state.selectedSymbol=Math.max(0,Math.min(Number(symbol)||0,state.summary.frame_symbols-1));
    state.selectedSample=8*state.selectedSymbol;
    $("#global-sample").value=String(state.selectedSample);
    await loadWindow();
  }

  async function refreshRuns() {
    try {
      const [data, experiments] = await Promise.all([api("/api/scientific/runs"),api("/api/scientific/experiments")]);
      const list = $("#saved-runs");
      if (!data.runs.length && !experiments.experiments.length) { list.innerHTML = '<div class="card empty">Збережених запусків ще не знайдено.</div>'; return; }
      list.innerHTML = data.runs.map((run,index) => `<article class="card saved-row"><div><h2>Моделювання ${index+1}</h2><p>${run.frame_symbols} символів · BER ${fmt(run.joint.ber,7)} / ${fmt(run.separate.ber,7)}</p></div><button class="secondary-button" data-open-run="${esc(run.run_id)}">Відкрити</button></article>`).join("")+experiments.experiments.map((run,index)=>`<article class="card saved-row"><div><h2>Статистична серія ${index+1}</h2><p>${run.completed_trials}/${run.planned_trials} пар · ${run.points.length} рівнів шуму · ${esc(run.status)}</p></div><button class="secondary-button" data-open-experiment="${esc(run.experiment_id)}">Відкрити</button></article>`).join("");
      $$('[data-open-run]').forEach(button => button.addEventListener("click", async () => { await loadRun(button.dataset.openRun); selectView("comparison"); }));
      $$('[data-open-experiment]').forEach(button => button.addEventListener("click", async () => { await loadMonteCarlo(button.dataset.openExperiment); selectView("monte-carlo"); }));
    } catch (error) { $("#saved-runs").textContent = error.message; }
  }

  async function openLongFrameArchive() {
    const archive=await api("/api/scientific/long-frame");
    state.longFrameArchive=archive;
    refreshPlotExportButtons();
    state.runId="repro06c-reference-20000";
    state.summary={run_id:state.runId,frame_symbols:archive.repro06c_trace.frame_symbols,sample_count:160003,receiver_observation_sha256:archive.repro06c_trace.observation_sha256,trellises:{joint:{state_count:17,edge_count:68}}};
    state.selectedSymbol=state.summary.frame_symbols-1;state.selectedSample=state.summary.sample_count-1;
    $("#global-symbol").value=String(state.selectedSymbol);$("#global-sample").value=String(state.selectedSample);$("#viterbi-symbol").value=String(state.selectedSymbol);$("#traceback-depth").value="20";$("#global-receiver").value="joint";
    $("#sync-status").textContent=`Архів завантажено · ${archive.repro08_metrics.frame_symbols} символів`;$("#survivor-endpoint").value="";
    const metric=archive.repro08_metrics;
    $("#comparison-cards").innerHTML=[ ["Спільна демодуляція та декодування — метрика Евкліда",metric.joint], ["Роздільна демодуляція та декодування — метрика Хемінга",metric.separate] ].map(([title,r])=>`<article class="card receiver-card"><h2>${title}</h2><div class="big-metric">BER ${fmt(r.ber,7)}</div><div class="receiver-meta">${r.bit_errors} / ${metric.compared_bits} бітів · SER інформаційних пар ${fmt(r.ser,7)} (${r.pair_symbol_errors}/${metric.frame_symbols})<br>Час: ${fmt(r.runtime_seconds,3)} с</div></article>`).join("");
    $("#paired-badge").textContent="Спільне прийняте спостереження перевірено";
    $("#paired-badge").classList.remove("status-partial");
    $("#mc-results").innerHTML=`<h2>Перевірені довгі архіви</h2><p>REPRO-08: фактичні BER/SER і paired errors, F=20000. REPRO-06C: окремий decoder trace з іншим observation hash ${archive.repro06c_trace.observation_sha256.slice(0,16)}… . Їх не об'єднано в одне порівняння. У trace архіві немає received/transmitted I/Q або EvaluationTruth.</p>`;
    selectView("viterbi");await loadViterbi();
  }

  function monteCarloConfig() {
    const noise = $("#mc-noise").value.split(",").map(value => Number(value.trim()));
    if (!noise.length || noise.some(value => !Number.isFinite(value) || value < 0)) throw new Error("Перевірте сітку дисперсій шуму.");
    const id = $("#mc-id").value.trim();
    if (!id) throw new Error("Введіть ID експерименту.");
    const channelProfile=$("#mc-profile").value;
    const singlePath=["identity","static_single_path","rician_single_path"].includes(channelProfile);
    return {
      experiment_id: id,
      experiment_label: "REPRO-09 GUI paired pilot",
      frame_symbols: Number($("#mc-frame").value),
      noise_variances: noise,
      trials_per_point: Number($("#mc-trials").value),
      root_seed: Number($("#mc-seed").value),
      run_level: "smoke",
      preset_mode: "custom_research",
      channel_profile: channelProfile,
      path_delays_samples: singlePath ? [0] : [0, 3],
      path_powers: singlePath ? [1] : [1, 0.25],
      rician_k_factors: singlePath ? [4] : [4, 1],
      los_phases_rad: singlePath ? [0] : [0, 0.7],
      fading_correlation: 0.98,
      samples_per_symbol: 8,
      decoder_mode: "finite_depth",
      traceback_depth: 20,
      confidence_level: 0.95,
      bootstrap_replicates: 500,
      bootstrap_seed: Number($("#mc-seed").value) + 1,
      max_wall_seconds: Number($("#mc-budget").value),
      max_trials: noise.length * Number($("#mc-trials").value),
      max_disk_bytes: 500000000,
      diagnostics_level: "summary_only",
      selected_trial_indices: []
    };
  }

  async function startMonteCarlo(event) {
    event.preventDefault();
    $("#mc-run").disabled = true;
    $("#mc-status").textContent = "Перевірка конфігурації…";
    try {
      const response = await api("/api/scientific/experiments", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(monteCarloConfig())});
      state.mcJobId = response.job_id;
      $("#mc-stop").disabled = false;
      state.mcTimer = window.setInterval(pollMonteCarlo, 500);
      await pollMonteCarlo();
    } catch (error) {
      $("#mc-status").textContent = `Серію не запущено: ${error.message}`;
      $("#mc-run").disabled = false;
    }
  }

  async function pollMonteCarlo() {
    if (!state.mcJobId) return;
    try {
      const job = await api(`/api/scientific/jobs/${encodeURIComponent(state.mcJobId)}`);
      const completed = job.completed_trials || 0, planned = job.planned_trials || 0;
      $("#mc-status").textContent = job.status === "running" ? `Завершено парних випробувань: ${completed}/${planned}. Працює рівень шуму ${job.point_index === undefined ? "—" : job.point_index + 1}.` : job.status === "queued" ? "У черзі…" : job.status === "failed" ? `Помилка: ${job.error}` : `Серію збережено: ${completed}/${planned} пар · ${job.status}.`;
      if (["completed", "incomplete", "failed"].includes(job.status)) {
        clearInterval(state.mcTimer); state.mcTimer = null; $("#mc-run").disabled = false; $("#mc-stop").disabled = true;
        if (job.experiment_id) await loadMonteCarlo(job.experiment_id);
      }
    } catch (error) {
      clearInterval(state.mcTimer); state.mcTimer = null; $("#mc-run").disabled = false; $("#mc-stop").disabled = true;
      $("#mc-status").textContent = `Не вдалося отримати стан серії: ${error.message}`;
    }
  }

  async function stopMonteCarlo() {
    if (!state.mcJobId) return;
    try {
      await api(`/api/scientific/jobs/${encodeURIComponent(state.mcJobId)}/stop`, {method:"POST"});
      $("#mc-status").textContent = "Зупинку запитано; поточна пара завершиться й буде збережена.";
      $("#mc-stop").disabled = true;
    } catch (error) { $("#mc-status").textContent = error.message; }
  }

  function plotMonteCarlo(summary) {
    const canvas = $("#mc-ber"), points = summary.points.filter(point => point.status !== "no_completed_trials");
    let controls=canvas.parentElement.querySelector('.mc-series-controls');
    if(!controls){controls=document.createElement('div');controls.className='series-controls mc-series-controls';controls.innerHTML='<label><input type="checkbox" value="joint_ber" checked>Спільне приймання</label><label><input type="checkbox" value="separate_ber" checked>Роздільне приймання</label>';canvas.before(controls);}
    controls.querySelectorAll('input').forEach(input=>input.onchange=()=>plotMonteCarlo(summary));
    canvas.dataset.exportRendered = "false";
    const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth || 700, height = canvas.clientHeight || 280;
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.clearRect(0, 0, width, height);
    ctx.fillStyle="#ffffff";ctx.fillRect(0,0,width,height);
    if (!points.length) { ctx.fillStyle="#65757e";ctx.font="12px Segoe UI";ctx.fillText("Немає завершених вимірювань",20,32);canvas.dataset.exportRendered="true";return; }
    const left=58,right=width-18,top=43,bottom=height-46;
    const xs=points.map(p=>Number(p.noise_variance_complex_per_sample));
    const ys=points.flatMap(p=>[Number(p.joint_ber||0),Number(p.separate_ber||0)]);
    const xmin=Math.min(...xs),xmax=Math.max(...xs),ymax=Math.max(0.001,...ys)*1.1;
    ctx.strokeStyle="#e3eaec";ctx.fillStyle="#65757e";ctx.font="11px Segoe UI";
    for(let i=0;i<=4;i++){const y=top+(bottom-top)*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(fmt(ymax*(1-i/4),3),8,y+4);}
    const px=x=>left+(right-left)*(xmax===xmin?0.5:(x-xmin)/(xmax-xmin));
    const py=y=>bottom-(bottom-top)*y/ymax;
    for(const [key,color] of [["joint_ber","#087f8c"],["separate_ber","#ec8b4b"]]){
      if(!controls.querySelector(`input[value="${key}"]`).checked)continue;
      ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();
      points.forEach((point,i)=>{const x=px(Number(point.noise_variance_complex_per_sample)),y=py(Number(point[key]||0));if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.beginPath();});
    }
    ctx.fillStyle="#123045";ctx.font="600 13px Segoe UI, sans-serif";ctx.fillText("BER (безрозмірна частка)",left,17,right-left);
    ctx.fillStyle="#087f8c";ctx.font="11px Segoe UI";ctx.fillText("Спільне — Евклід",left,34);ctx.fillStyle="#ec8b4b";ctx.fillText("Роздільне — Хемінг",left+135,34);
    points.forEach(p=>ctx.fillText(fmt(p.noise_variance_complex_per_sample,3),px(Number(p.noise_variance_complex_per_sample))-14,height-12));
    canvas.dataset.exportRendered = "true";
  }

  function plotDeltaConfidence(summary) {
    const canvas=$("#mc-delta"), points=summary.points.filter(point=>Array.isArray(point.confidence_intervals?.delta_ber_ci)&&point.confidence_intervals.delta_ber_ci.length===2);
    canvas.dataset.exportRendered = "false";
    const ratio=window.devicePixelRatio||1,width=canvas.clientWidth||700,height=canvas.clientHeight||240;
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    const ctx=canvas.getContext("2d");ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);ctx.fillStyle="#ffffff";ctx.fillRect(0,0,width,height);
    if(!points.length){ctx.fillStyle="#65757e";ctx.font="12px Segoe UI";ctx.fillText("Довірчі інтервали недоступні",20,32);canvas.dataset.exportRendered="true";return;}
    const vals=points.flatMap(point=>[Number(point.delta_ber_joint_minus_separate),...point.confidence_intervals.delta_ber_ci.map(Number)]).filter(Number.isFinite);
    const min=Math.min(0,...vals),max=Math.max(0,...vals),range=max-min||1,left=68,right=width-18,top=43,bottom=height-38;
    const py=v=>bottom-(bottom-top)*(v-min)/range,px=i=>left+(right-left)*(i+.5)/points.length;
    ctx.strokeStyle="#dce5e7";ctx.beginPath();ctx.moveTo(left,py(0));ctx.lineTo(right,py(0));ctx.stroke();
    points.forEach((point,i)=>{const [lo,hi]=point.confidence_intervals.delta_ber_ci.map(Number),delta=Number(point.delta_ber_joint_minus_separate),x=px(i);ctx.strokeStyle="#087f8c";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,py(lo));ctx.lineTo(x,py(hi));ctx.moveTo(x-5,py(lo));ctx.lineTo(x+5,py(lo));ctx.moveTo(x-5,py(hi));ctx.lineTo(x+5,py(hi));ctx.stroke();ctx.fillStyle="#e8833f";ctx.beginPath();ctx.arc(x,py(delta),4,0,Math.PI*2);ctx.fill();ctx.fillStyle="#60737d";ctx.font="10px Segoe UI";ctx.fillText(fmt(point.noise_variance_complex_per_sample,3),x-20,height-12);});
    ctx.fillStyle="#123045";ctx.font="600 13px Segoe UI, sans-serif";ctx.fillText("ΔBER (безрозмірна різниця)",left,17,right-left);
    ctx.fillStyle="#60737d";ctx.font="10px Segoe UI";ctx.fillText(`DeltaBER (${fmt(max,5)} … ${fmt(min,5)})`,5,34);
    canvas.dataset.exportRendered = "true";
  }

  async function loadMonteCarlo(experimentId) {
    const summary = await api(`/api/scientific/experiments/${encodeURIComponent(experimentId)}`);
    state.mcSummary = summary; plotMonteCarlo(summary); plotDeltaConfidence(summary);
    $("#mc-results").innerHTML = `<h2>Статистика серії · ${esc(summary.status)}</h2>${summary.points.map(point=>{const ci=point.confidence_intervals||{};const delta=ci.delta_ber_ci?ci.delta_ber_ci.map(v=>fmt(v,6)).join(" – "):ci.status||"недостатньо незалежних trials";return `<div class="metric"><span>σ²=${fmt(point.noise_variance_complex_per_sample,5)} · trials ${point.completed_trials}</span><strong>BER J ${fmt(point.joint_ber,7)} · B0 ${fmt(point.separate_ber,7)} · Δ ${fmt(point.delta_ber_joint_minus_separate,7)}<br>SER інформаційних пар J ${fmt(point.joint_pair_ser,7)} · B0 ${fmt(point.separate_pair_ser,7)}<br>95% парний довірчий інтервал ΔBER: ${esc(delta)}</strong></div>`;}).join("")}<p>${summary.completed_trials}/${summary.planned_trials} завершених парних випробувань · відношення сум · інтервали парного bootstrap групуються за trial.</p>`;
    refreshPlotExportButtons();
  }

  function updateEnergyConfigPreview() {
    const profile = $("#channel-profile").value;
    const frame = Number($("#es-frame").value || $("[name=frame_symbols]").value);
    const count = $("#es-grid").value.split(",").filter(value=>value.trim()).length;
    const b1 = $("#es-b1");
    b1.disabled = profile === "rician_ar1_multipath";
    if (b1.disabled) b1.checked = false;
    $("#es-config-preview").textContent = `${profile} · F=${frame} · ${count} енергетичних точок · ${$("#es-trials").value||"—"} кадрів/точку · амплітуда ${$("[name=amplitude]").value} · σ²=${$("[name=noise_variance]").value}`;
  }

  function buildEnergyStudyConfig() {
    const base = configFromForm();
    const grid = $("#es-grid").value.split(",").map(value => Number(value.trim()));
    if (!grid.length || grid.some(value => !Number.isFinite(value)) || new Set(grid).size !== grid.length) throw new Error("Введіть унікальні скінченні точки γ через кому.");
    const sweep = $("#es-sweep").value;
    if (sweep === "amplitude" && base.noise_variance <= 0) throw new Error("Для зміни амплітуди задайте в параметрах додатну дисперсію шуму.");
    const arms = ["joint"];
    if ($("#es-b0").checked) arms.push("b0");
    if ($("#es-b1").checked) arms.push("b1");
    if (arms.length < 2) throw new Error("Оберіть хоча б один роздільний приймач.");
    const count = base.delays_samples.length;
    const pathCoefficients = base.channel_profile === "rician_ar1_multipath" ? [] : base.path_coefficients;
    return {
      experiment_id: $("#es-id").value.trim(),
      frame_symbols: Number($("#es-frame").value),
      gamma_grid_db: grid,
      trials_per_point: Number($("#es-trials").value),
      root_seed: Number($("#es-seed").value),
      target_ber: Number($("#es-target").value),
      time_budget_seconds: Number($("#es-budget").value),
      sweep,
      receiver_arms: arms,
      channel_profile: base.channel_profile,
      noise_variance: base.noise_variance,
      amplitude: base.amplitude,
      delays_samples: base.delays_samples,
      path_coefficients: pathCoefficients,
      path_powers: base.path_powers.slice(0, count),
      rician_k_factors: base.rician_k_factors.slice(0, count),
      los_phases_rad: base.los_phases_rad.slice(0, count),
      fading_correlation: base.fading_correlation,
      bootstrap_replicates: Number($("#es-bootstrap").value)
    };
  }

  async function launchEnergyStudy() {
    $("#es-run").disabled = true; $("#es-status").textContent = "Перевірка конфігурації…";
    try {
      const configuration = buildEnergyStudyConfig();
      const response = await api("/api/scientific/energy-studies", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(configuration)});
      state.energyJobId = response.job_id; $("#es-stop").disabled = false;
      $("#es-progress").value = 0; $("#es-progress").max = 1;
      state.energyTimer = window.setInterval(pollEnergyStudy, 500); await pollEnergyStudy();
    } catch (error) { $("#es-status").textContent = `Серію не запущено: ${error.message}`; $("#es-run").disabled = false; }
  }

  async function startEnergyStudy(event) {
    event.preventDefault();
    await launchEnergyStudy();
  }

  async function pollEnergyStudy() {
    if (!state.energyJobId) return;
    try {
      const job = await api(`/api/scientific/jobs/${encodeURIComponent(state.energyJobId)}`);
      const completed = job.completed_trials || 0, planned = job.planned_trials || 0;
      $("#es-progress").value = job.progress || 0;
      $("#es-status").textContent = job.status === "running" ? `Завершено парних кадрів ${completed}/${planned}; обробляється один receiver observation на кадр.` : job.status === "queued" ? "У черзі…" : job.status === "failed" ? `Помилка: ${job.error}` : `${completed}/${planned} кадрів · ${job.status === "completed" ? "завершено" : "зупинено або бюджет вичерпано"}.`;
      if (["completed", "incomplete", "failed"].includes(job.status)) {
        clearInterval(state.energyTimer); state.energyTimer = null; $("#es-run").disabled = false; $("#es-stop").disabled = true;
        if (job.experiment_id && job.status !== "failed") { await loadEnergyStudy(job.experiment_id); selectView("energy"); }
      }
    } catch (error) {
      clearInterval(state.energyTimer); state.energyTimer = null; $("#es-run").disabled = false; $("#es-stop").disabled = true;
      $("#es-status").textContent = `Не вдалося отримати стан серії: ${error.message}`;
    }
  }

  async function stopEnergyStudy() {
    if (!state.energyJobId) return;
    try { await api(`/api/scientific/jobs/${encodeURIComponent(state.energyJobId)}/stop`, {method:"POST"}); $("#es-status").textContent = "Зупинку запитано; поточне парне випробування завершиться та буде збережене."; $("#es-stop").disabled = true; }
    catch (error) { $("#es-status").textContent = error.message; }
  }

  async function refreshEnergyStudies() {
    try {
      const response = await api("/api/scientific/energy-studies");
      const select = $("#es-saved"), selected = select.value;
      select.innerHTML = '<option value="">Оберіть завершену або перервану серію</option><option value="historical:exp01b-static">Перевірена статична серія, 1 160 кадрів — енергетичне дослідження</option>' + response.studies.map(study=>`<option value="${esc(study.experiment_id)}">${esc(study.experiment_id)} · ${study.completed_trials}/${study.planned_trials} кадрів · ${esc(study.status)}</option>`).join("");
      if (selected === "historical:exp01b-static" || response.studies.some(study=>study.experiment_id===selected)) select.value=selected;
    } catch (error) { $("#es-study-summary").textContent = `Список не завантажено: ${error.message}`; }
  }

  function refreshExp03bScenarios() {
    const block = $("#exp03b-block")?.value || "metric";
    const select = $("#exp03b-scenario");
    if (!select) return;
    const options = block === "metric" ? [
      ["awgn_direct", "AWGN без equalizer"],
      ["awgn_pilot", "AWGN зі спільним pilot frontend"],
      ["static_pilot", "Статичний multipath [0,3]"],
      ["rician_period32", "Rician AR(1), період пілотів 32"],
      ["rician_period8", "Rician AR(1), період пілотів 8"]
    ] : [
      ["awgn", "AWGN"],
      ["static", "Статичний multipath [0,3]"],
      ["rician", "Rician AR(1) multipath"]
    ];
    const selected = select.value;
    select.innerHTML = options.map(([value, label]) => `<option value="${value}">${esc(label)}</option>`).join("");
    if (options.some(([value]) => value === selected)) select.value = selected;
  }

  async function openExp03bResults() {
    const button = $("#open-exp03b-results");
    button.disabled = true;
    $("#exp03b-status").textContent = "Перевірка хешу аналізу, manifest та confirmatory provenance…";
    try {
      state.exp03bResults = await api("/api/scientific/exp03b-results");
      const block = $("#exp03b-block").value;
      const scenario = $("#exp03b-scenario").value;
      const summary = adaptExp03bResult(state.exp03bResults, block, scenario, 0.05);
      renderEnergyStudy(summary);
      $("#exp03b-status").textContent = `Завантажено ${block === "metric" ? "ізольоване порівняння A-E/A-H" : "порівняння повних способів приймання"}: ${scenario}; ${summary.completed_trials}/${summary.planned_trials} незалежних кадрів. Хеші та manifest підтверджені.`;
      $("#es-status").textContent = "Відкрито збережені confirmatory-результати SCIENTIFIC-EXP-03B без повторного декодування.";
      selectView("energy");
    } catch (error) {
      $("#exp03b-status").textContent = `Не вдалося відкрити confirmatory-результати: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  }

  async function loadEnergyStudy(studyId) {
    const summary = await api(`/api/scientific/energy-studies/${encodeURIComponent(studyId)}`);
    renderEnergyStudy(summary); await refreshEnergyStudies();
    $("#es-status").textContent = `${summary.completed_trials}/${summary.planned_trials} парних випробувань збережено; ${summary.exploratory ? "розвідувальний обсяг" : "обсяг не позначений як розвідувальний"}.`;
    return summary;
  }

  async function openEnergyStudy() {
    const id = $("#es-saved").value;
    if (!id) { $("#es-study-summary").textContent = "Оберіть збережене дослідження."; return; }
    if (id === "historical:exp01b-static") {
      try {
        const summary = await api("/api/scientific/energy-studies/historical/exp01b-static-amplitude-005");
        renderEnergyStudy(summary);
        $("#es-status").textContent = `Відкрито перевірену статичну серію: ${summary.completed_trials} парних кадрів, BER 0,05.`;
        selectView("energy");
      } catch (error) { $("#es-study-summary").textContent = `Історичну серію не відкрито: ${error.message}`; }
      return;
    }
    try { await loadEnergyStudy(id); selectView("energy"); }
    catch (error) { $("#es-study-summary").textContent = `Результат не відкрито: ${error.message}`; }
  }

  async function openHistoricalEnergyStudy() {
    const button = $("#open-historical-energy");
    button.disabled = true;
    $("#energy-gain-status").textContent = "Перевірка manifest, хешів і повторний аналіз парних кадрів…";
    try {
      const summary = await api("/api/scientific/energy-studies/historical/static-amplitude-005");
      renderEnergyStudy(summary);
      $("#es-status").textContent = `Відкрито перевірену історичну серію: ${summary.completed_trials} парних кадрів, BER 0,05.`;
      selectView("energy");
    } catch (error) {
      $("#energy-gain-status").textContent = `Історичний результат не відкрито: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  }

  function updateChannelFields() {
    const profile = $("#channel-profile").value;
    $("#static-fields").classList.toggle("hidden", !profile.startsWith("static_"));
    $("#rician-fields").classList.toggle("hidden", profile !== "rician_ar1_multipath");
    const b1 = $("#include-b1");
    if (profile === "rician_ar1_multipath") { b1.checked = false; b1.disabled = true; }
    else b1.disabled = false;
    const variance = $("[name=noise_variance]");
    if (profile === "identity") variance.value = "0";
    if (profile === "awgn" && Number(variance.value) === 0) variance.value = "0.05";
  }

  $$(".tab").forEach(button => button.addEventListener("click", () => selectView(button.dataset.view)));
  $("#run-form").addEventListener("submit", startRun);
  $("#channel-profile").addEventListener("change", updateChannelFields);
  $("#channel-profile").addEventListener("change", updateEnergyConfigPreview);
  $("#run-form").addEventListener("input", updateEnergyConfigPreview);
  $("#es-frame").addEventListener("input", updateEnergyConfigPreview);
  $("#es-trials").addEventListener("input", updateEnergyConfigPreview);
  $$("[data-load-window]").forEach(button => button.addEventListener("click", () => {
    const source = state.activeView === "channel" ? $("#window-start-channel") : state.activeView === "joint" ? $("#selected-symbol-joint") : state.activeView === "separate" ? $("#selected-symbol-separate") : $("#window-start-tx");
    setSelectedSymbol(Number(source.value));
  }));
  $("#global-symbol").addEventListener("change", event => setSelectedSymbol(Number(event.target.value)));
  $("#global-sample").addEventListener("change", event => {
    state.selectedSample=Math.max(0,Number(event.target.value)||0);
    if(state.summary)state.selectedSample=Math.min(state.selectedSample,state.summary.sample_count-1);
    state.selectedSymbol=Math.min(Math.floor(state.selectedSample/8),Math.max(0,(state.summary?.frame_symbols||1)-1));
    $("#global-symbol").value=String(state.selectedSymbol);loadWindow();
  });
  $("#global-receiver").addEventListener("change",()=>{state.selectedTransition=null;$("#survivor-endpoint").value="";if(state.activeView==="viterbi")loadViterbi();});
  $("#viterbi-symbol").addEventListener("change",event=>setSelectedSymbol(Number(event.target.value)));
  $("#load-viterbi").addEventListener("click",loadViterbi);
  $("#traceback-depth").addEventListener("change",loadViterbi);
  $("#survivor-endpoint").addEventListener("change",loadViterbi);
  $("#trellis-filter").addEventListener("change",renderViterbi);
  $("#symbol-previous").addEventListener("click",()=>setSelectedSymbol(state.selectedSymbol-1));
  $("#symbol-next").addEventListener("click",()=>setSelectedSymbol(state.selectedSymbol+1));
  $("#zoom-20-samples").addEventListener("click",async()=>{selectView("viterbi");await loadSampleZoom();});
  $("#refresh-runs").addEventListener("click", refreshRuns);
  $("#open-long-frame").addEventListener("click",async()=>{try{await openLongFrameArchive();}catch(error){$("#sync-status").textContent=`Архів не відкрито: ${error.message}`;}});
  $("#energy-study-form").addEventListener("submit", startEnergyStudy);
  $("#es-stop").addEventListener("click", stopEnergyStudy);
  $("#es-open").addEventListener("click", openEnergyStudy);
  $("#refresh-energy-studies").addEventListener("click", refreshEnergyStudies);
  $("#open-historical-energy").addEventListener("click", openHistoricalEnergyStudy);
  $("#exp03b-block").addEventListener("change", refreshExp03bScenarios);
  $("#open-exp03b-results").addEventListener("click", openExp03bResults);
  refreshExp03bScenarios();
  const autoEnergy = $("#es-auto-after-run");
  autoEnergy.checked = localStorage.getItem("hf-tcm-auto-energy-after-run") === "true";
  autoEnergy.addEventListener("change", () => localStorage.setItem("hf-tcm-auto-energy-after-run", String(autoEnergy.checked)));
  window.addEventListener("resize",()=>{drawAll();if(state.viterbi)renderViterbi();if(state.mcSummary){plotMonteCarlo(state.mcSummary);plotDeltaConfidence(state.mcSummary);}if(state.energySummary)renderEnergyStudy(state.energySummary);});
  installPlotExportButtons();
  installEnergySvgExportButtons();
  updateChannelFields();
  $("#es-frame").value = $("[name=frame_symbols]").value;
  updateEnergyConfigPreview();
  refreshEnergyStudies();
  refreshRuns();
})();
