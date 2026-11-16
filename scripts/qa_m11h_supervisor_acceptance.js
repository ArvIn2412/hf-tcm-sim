"use strict";

// Additional real Edge acceptance for M11h. Runs only the deterministic UI fixture.
const fs = require("node:fs");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.M11H_URL || "http://127.0.0.1:18768";
const CDP = process.env.M11H_CDP || "http://127.0.0.1:9224";
const report = { viewports: [], checks: [], screenshots: [], exceptions: [] };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

class Edge {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.pending = new Map(); this.onEvent = () => {}; this.ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id) { const p = this.pending.get(m.id); if (p) { this.pending.delete(m.id); m.error ? p.reject(Error(JSON.stringify(m.error))) : p.resolve(m.result); } } else this.onEvent(m); }); }
  async ready() { if (this.ws.readyState !== WebSocket.OPEN) await new Promise((resolve, reject) => { this.ws.addEventListener("open", resolve, { once: true }); this.ws.addEventListener("error", reject, { once: true }); }); }
  async send(method, params = {}) { await this.ready(); const id = ++this.id; return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params })); }); }
  async eval(expression, gesture = false) { const r = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: gesture }); if (r.exceptionDetails) throw Error(JSON.stringify(r.exceptionDetails)); return r.result.value; }
  async until(expression, ms = 20000) { const end = Date.now() + ms; while (Date.now() < end) { if (await this.eval(expression)) return; await pause(100); } throw Error(`Timed out: ${expression}`); }
  check(name, ok, details) { report.checks.push({ name, ok: Boolean(ok), details }); if (!ok) throw Error(`${name}: ${JSON.stringify(details)}`); }
  async click(selector) { await this.eval(`document.querySelector(${JSON.stringify(selector)})?.click()`, true); }
  async shot(name, viewport, selector) { await this.eval(`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:'center'})`); await pause(200); const r = await this.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); const file = `m11h-${name}-${viewport}.png`; fs.writeFileSync(path.join(ROOT, "docs", "screenshots", file), Buffer.from(r.data, "base64")); report.screenshots.push(`docs/screenshots/${file}`); }
}

async function runViewport(width, height) {
  const label = `${width}x${height}`; report.viewports.push(label);
  const targets = await fetch(`${CDP}/json`).then(r => r.json());
  const target = targets.find(x => x.type === "page"); if (!target) throw Error("No Edge target");
  const b = new Edge(target.webSocketDebuggerUrl);
  b.onEvent = e => { if (e.method === "Runtime.exceptionThrown") report.exceptions.push({ viewport: label, text: e.params.exceptionDetails?.text }); };
  await Promise.all([b.send("Page.enable"), b.send("Runtime.enable")]);
  await b.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await b.send("Page.navigate", { url: `${BASE}/` });
  await b.until("window.M11DUX && app.metadata && document.getElementById('run-demo')");
  b.check(`${label} GET is side-effect free`, await b.eval("app.trace===null"));
  await b.click("#run-demo");
  await b.until("app.trace?.input.symbol_count===32 && !document.getElementById('run-demo').disabled");
  const first = await b.eval("({bits:app.trace.input.information_bits.join(''),encoded:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.encoded_output_bits)),tx:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.transmitted_samples)),rx:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.received_samples)),metrics:JSON.stringify(app.trace.arms.map(a=>a.symbols.map(s=>s.candidate_metrics)))})");
  b.check(`${label} F=32 produced actual data`, first.bits.length === 64 && first.tx.length > 100 && first.rx.length > 100);
  await b.eval("(()=>{const e=document.getElementById('interactive-bits');e.value=e.value.split('').map(x=>x==='0'?'1':'0').join('');e.dispatchEvent(new Event('input',{bubbles:true}))})()");
  await b.click("#run-demo");
  await b.until("app.trace?.input.symbol_count===32 && !document.getElementById('run-demo').disabled && app.trace.input.information_bits.join('')===document.getElementById('interactive-bits').value");
  const second = await b.eval("({bits:app.trace.input.information_bits.join(''),encoded:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.encoded_output_bits)),tx:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.transmitted_samples)),rx:JSON.stringify(app.trace.arms[0].symbols.map(s=>s.received_samples)),metrics:JSON.stringify(app.trace.arms.map(a=>a.symbols.map(s=>s.candidate_metrics)))})");
  b.check(`${label} changed input changes encoder output and downstream trace`, first.bits !== second.bits && first.encoded !== second.encoded && first.tx !== second.tx && first.rx !== second.rx && first.metrics !== second.metrics, { inputChanged: first.bits !== second.bits, encodedChanged: first.encoded !== second.encoded, txChanged: first.tx !== second.tx, rxChanged: first.rx !== second.rx, metricsChanged: first.metrics !== second.metrics });
  await b.click("#projector-toggle");
  for (const [view, shot, selector] of [["signal", "signal", "#signal-chart svg"], ["trellis", "trellis", ".trellis-svg"], ["estimator", "estimator", "#estimator-view svg"], ["decode", "viterbi", "#ux-decode .data-table"]]) {
    await b.click(`.nav-item[data-view='${view}']`);
    await b.until(`document.getElementById('view-${view}')?.classList.contains('active')`);
    if (view === "trellis") {
      const overview = await b.eval("({mode:document.getElementById('trellis-display-mode')?.value,edges:document.querySelectorAll('#trellis-canvas [data-projector-edge]').length,labels:[...document.querySelectorAll('#trellis-canvas .p-edge-label')].filter(e=>getComputedStyle(e).display!=='none').length,decoded:document.querySelectorAll('#trellis-canvas .p-edge-viterbi').length,reference:document.querySelectorAll('#trellis-canvas .p-edge-reference').length})");
      b.check(`${label} A overview keeps all 16 edges, hides mass labels, highlights both paths`, overview.mode === 'overview' && overview.edges === 16 && overview.labels === 0 && overview.decoded > 0 && overview.reference > 0, overview);
      await b.eval("(()=>{const e=document.getElementById('trellis-display-mode');e.value='detail';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
      const detail = await b.eval("({labels:[...document.querySelectorAll('#trellis-canvas .p-edge-label')].filter(e=>getComputedStyle(e).display!=='none').length,text:document.getElementById('trellis-edge-detail').innerText,tab:document.querySelector('#trellis-canvas [data-projector-edge]')?.getAttribute('tabindex')})");
      b.check(`${label} A detail mode labels only selected transition and exposes exact fields`, detail.labels === 1 && /Source|Джерело/.test(detail.text) && /Metric|Метрика/.test(detail.text) && detail.tab === '0', detail);
      await b.eval("document.querySelector('#trellis-canvas [data-projector-edge=\\\"7\\\"]')?.focus()");
      await b.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter" });
      await b.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter" });
      const keyboardEdge = await b.eval("({edge:app.edge,selected:document.querySelector('#trellis-canvas [data-projector-edge=\\\"7\\\"]')?.classList.contains('p-edge-selected')})");
      b.check(`${label} A trellis edge can be selected with the keyboard`, keyboardEdge.edge === 7 && keyboardEdge.selected, keyboardEdge);
      await b.shot("trellis-detail", label, "#trellis-canvas svg");
      await b.click('#trellis-show-all');
      b.check(`${label} A show-all button reveals a separate 16-row transition table`, await b.eval("!document.getElementById('edge-table').hidden && document.querySelectorAll('#edge-table tbody tr').length===16"));
      await b.click('#trellis-show-all');
      await b.eval("(()=>{const e=document.getElementById('trellis-display-mode');e.value='overview';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
    }
    const state = await b.eval(`(()=>{const p=document.getElementById('view-${view}'),g=p.querySelector(${JSON.stringify(selector)}),r=g?.getBoundingClientRect(),fonts=[...p.querySelectorAll('svg text')].map(e=>parseFloat(getComputedStyle(e).fontSize));return{graph:!!g,width:r?Math.round(r.width):0,height:r?Math.round(r.height):0,axisMax:Math.max(0,...fonts),pageOverflow:document.documentElement.scrollWidth>innerWidth,text:p.innerText,projector:document.body.classList.contains('projector-mode')}})()`);
    b.check(`${label} projector ${view} view has actual graph/data and fits`, state.graph && state.width > 400 && !state.pageOverflow && state.projector, state);
    if (view === "signal" || view === "trellis" || view === "estimator") b.check(`${label} projector ${view} axes are legible`, state.axisMax >= 16, state);
    await b.shot(shot, label, selector);
  }
  const decode = await b.eval("document.getElementById('ux-decode').innerText");
  b.check(`${label} decoded result and single-frame caveat visible`, /BER/.test(decode) && /SER/.test(decode) && decode.includes('не повний декодер'));
  b.check(`${label} Ukrainian projector descriptions present`, await b.eval("['#view-signal','#view-trellis','#view-estimator','#view-decode'].every(s=>/Що тут відбувається|Симуляція/.test(document.querySelector(s).innerText))"));
  await b.click(".nav-item[data-view='signal']");
  await b.eval("(()=>{const e=document.getElementById('signal-chart-type');e.value='constellation';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  const constellation = await b.eval("({markers:document.querySelectorAll('#signal-chart circle.signal-point,#signal-chart circle.signal-selected-point,#signal-chart circle.signal-window-point').length,title:document.getElementById('signal-chart-title').innerText,window:document.getElementById('signal-window-label').innerText})");
  b.check(`${label} projector constellation contains actual trace symbols and window selection`, constellation.markers >= 20 && /8PSK|constellation/i.test(constellation.title), constellation);
  await b.shot("constellation", label, "#signal-chart svg");
  await b.click("#projector-fullscreen");
  await b.until("document.fullscreenElement===document.documentElement", 4000);
  b.check(`${label} browser fullscreen entered from user gesture`, await b.eval("document.fullscreenElement===document.documentElement"));
  await b.click("#projector-fullscreen");
  await b.until("document.fullscreenElement===null", 4000);
  await b.click(".nav-item[data-view='demo']");
  await b.eval("(()=>{const e=document.getElementById('interactive-encoder');e.value='B';e.dispatchEvent(new Event('change',{bubbles:true}));document.getElementById('interactive-bits').value='001011';document.getElementById('interactive-state').value='5'})()");
  b.check(`${label} B allows all 16 explicit preview initial states`, await b.eval("document.getElementById('interactive-state').value==='5' && document.getElementById('interactive-state').options.length===16 && document.getElementById('run-demo').disabled"));
  await b.click("#encoder-b-preview");
  await b.until("document.getElementById('interactive-warning').innerText.includes('B preview успішний')");
  const bState = await b.eval("({text:document.getElementById('encoder-b-result').innerText,rows:document.querySelectorAll('#encoder-b-result tbody tr').length})");
  b.check(`${label} B preview displays actual selected start and state trajectory, without receiver`, bState.rows === 64 && bState.text.includes('Початковий стан: 5 (0101)') && bState.text.includes('Становий ID шлях: 5 → 1 → 8 → 14') && bState.text.includes('Приймач не викликався'), bState);
  const bOverview = await b.eval("({states:document.querySelectorAll('#encoder-b-graph .p-state').length,edges:document.querySelectorAll('#encoder-b-graph [data-projector-edge]').length,labels:[...document.querySelectorAll('#encoder-b-graph .p-edge-label')].filter(e=>getComputedStyle(e).display!=='none').length,path:document.querySelectorAll('#encoder-b-graph .p-edge-reference').length,selected:document.querySelectorAll('#encoder-b-graph .p-edge-symbol').length})");
  b.check(`${label} B overview renders 16 states/64 edges without labels and marks reference/selected paths`, bOverview.states === 16 && bOverview.edges === 64 && bOverview.labels === 0 && bOverview.path === 3 && bOverview.selected === 1, bOverview);
  await b.shot("encoder-b-trellis", label, "#encoder-b-graph svg");
  await b.eval("(()=>{const e=document.getElementById('encoder-b-display-mode');e.value='detail';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  const bDetail = await b.eval("({labels:[...document.querySelectorAll('#encoder-b-graph .p-edge-label')].filter(e=>getComputedStyle(e).display!=='none').length,text:document.getElementById('encoder-b-edge-detail').innerText})");
  b.check(`${label} B detail keeps phase/metric/posterior unavailable rather than inventing values`, bDetail.labels === 1 && /Фаза[\s\S]*недоступна/.test(bDetail.text) && /Метрика[\s\S]*недоступна/.test(bDetail.text) && /posterior[\s\S]*недоступний/.test(bDetail.text), bDetail);
  await b.click('#encoder-b-show-all');
  b.check(`${label} B show-all button reveals all 64 source transitions`, await b.eval("!document.getElementById('encoder-b-transition-table').hidden && document.querySelectorAll('#encoder-b-transition-table tbody tr').length===64"));
  await b.shot("encoder-b-preview", label, "#encoder-b-result h3");
  await b.click(".nav-item[data-view='signal']");
  await b.eval("document.activeElement?.blur();document.body.focus()");
  const initial = await b.eval("app.currentView");
  await b.eval("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',code:'ArrowRight',bubbles:true}))");
  const keyboard = await b.eval("({view:app.currentView,active:[...document.querySelectorAll('.view.active')].map(x=>x.id)})");
  b.check(`${label} keyboard navigation changes the active projector view`, keyboard.view !== initial && keyboard.active.length === 1, { initial, ...keyboard });
  b.check(`${label} no runtime JS exceptions`, report.exceptions.filter(x => x.viewport === label).length === 0, report.exceptions.filter(x => x.viewport === label));
  b.ws.close();
}

(async () => {
  try { await runViewport(1366, 768); await runViewport(1920, 1080); report.passed = true; }
  catch (e) { report.error = e.stack || String(e); }
  const target = path.join(ROOT, "tmp", "m11h-edge-acceptance.json"); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, failed: report.checks.filter(x => !x.ok), viewports: report.viewports, screenshots: report.screenshots, error: report.error || null, report: target }, null, 2));
  if (!report.passed) process.exitCode = 1;
})();
