"use strict";

// Real Edge/Chromium DevTools Protocol QA. Node >=22, no npm dependencies.
// Use an existing locally authorized Edge instance with remote debugging on
// port 9222. A temporary localhost studio server is started only if needed.
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const URL_ROOT = process.env.M11D_URL || "http://127.0.0.1:18766";
const CDP_ROOT = process.env.M11D_CDP || "http://127.0.0.1:9222";
const REPORT_PATH = path.join(ROOT, "tmp", "m11d-browser-qa.json");
const SCREENSHOTS = path.join(ROOT, "docs", "screenshots");
const DOWNLOADS = path.join(ROOT, "tmp", "m11d-downloads");
const report = { started: new Date().toISOString(), browser: null, url: URL_ROOT,
  checks: [], screenshots: [], downloads: [], consoleErrors: [], networkErrors: [],
  externalRequests: [], viewports: [], serverStarted: false, passed: false };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let ownedServer;

class CDP {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 0;
    this.pending = new Map();
    this.listeners = [];
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", event => {
      const value = JSON.parse(event.data);
      if (value.id) {
        const item = this.pending.get(value.id);
        if (item) {
          clearTimeout(item.timeout);
          this.pending.delete(value.id);
          value.error ? item.reject(Error(JSON.stringify(value.error))) : item.resolve(value.result);
        }
      } else this.listeners.forEach(listener => listener(value));
    });
  }
  async send(method, params = {}) {
    await this.ready;
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(Error(`CDP timeout: ${method}`));
      }, 20000);
      this.pending.set(id, { resolve, reject, timeout });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression, returnByValue: true, awaitPromise: true,
    });
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  async until(expression, timeout = 15000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if (await this.evaluate(expression)) return;
      await sleep(80);
    }
    throw Error(`Timed out waiting for ${expression}`);
  }
  async click(selector) {
    const point = await this.evaluate(`(() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      if (!element) throw Error('Missing clickable element: ' + ${JSON.stringify(selector)});
      element.scrollIntoView({block:'center',inline:'nearest'});
      const r = element.getBoundingClientRect();
      if (!r.width || !r.height || element.disabled) throw Error('Unavailable click target');
      return {x:r.left+r.width/2,y:r.top+r.height/2};
    })()`);
    await this.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point, button: "left", clickCount: 1 });
    await this.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point, button: "left", clickCount: 1 });
    await sleep(60);
  }
  async input(selector, value, event = "change") {
    await this.evaluate(`(() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      if (!element) throw Error('Missing input');
      element.value = ${JSON.stringify(String(value))};
      element.dispatchEvent(new Event(${JSON.stringify(event)}, {bubbles:true}));
    })()`);
    await sleep(30);
  }
  async key(key, code, keyCode, modifiers = 0) {
    await this.send("Input.dispatchKeyEvent", { type: "keyDown", key, code,
      windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode, modifiers });
    await this.send("Input.dispatchKeyEvent", { type: "keyUp", key, code,
      windowsVirtualKeyCode: keyCode, nativeVirtualKeyCode: keyCode, modifiers });
  }
  close() { this.socket.close(); }
}

function check(name, value, detail = null) {
  const passed = Boolean(value);
  report.checks.push({ name, passed, detail });
  if (!passed) throw Error(`QA failed: ${name}${detail ? `: ${JSON.stringify(detail)}` : ""}`);
}

async function ensureServer() {
  try {
    const response = await fetch(`${URL_ROOT}/api/health`);
    if (response.ok) return;
  } catch { /* Start a server owned by this harness. */ }
  const parsed = new URL(URL_ROOT);
  if (parsed.hostname !== "127.0.0.1") throw Error("Automatic server startup requires 127.0.0.1");
  ownedServer = spawn(process.env.M11D_PYTHON || "python", ["-m", "hf_tcm.demo_studio",
    "--no-browser", "--port", parsed.port || "80"], {
    cwd: ROOT, stdio: "ignore", windowsHide: true,
  });
  report.serverStarted = true;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(`${URL_ROOT}/api/health`)).ok) return; } catch { /* retry */ }
    if (ownedServer.exitCode !== null) throw Error("Temporary studio server exited before readiness");
    await sleep(100);
  }
  throw Error("Temporary studio server did not become ready");
}

async function screenshot(cdp, name, viewport) {
  await cdp.evaluate("window.scrollTo(0,0)");
  await sleep(100);
  const result = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const relative = `docs/screenshots/m11d-${name}-${viewport}.png`;
  fs.writeFileSync(path.join(ROOT, relative), Buffer.from(result.data, "base64"));
  report.screenshots.push(relative);
}

async function layout(cdp, name) {
  const details = await cdp.evaluate(`(() => {
    const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
    return {viewport:innerWidth,width:document.documentElement.scrollWidth,
      rawPre:[...document.querySelectorAll('.view.active pre')].filter(visible).map(e=>e.textContent.slice(0,80)),
      active:document.querySelector('.view.active')?.id};
  })()`);
  check(`${name}: no page horizontal overflow`, details.width <= details.viewport + 1, details);
  check(`${name}: raw JSON is collapsed`, details.rawPre.length === 0, details);
}

async function navigate(cdp, view) {
  await cdp.click(`[data-view="${view}"]`);
  await cdp.until(`document.getElementById('view-${view}').classList.contains('active')`);
}

async function runViewport(width, height, browser) {
  const viewport = `${width}x${height}`;
  report.viewports.push(viewport);
  const target = await browser.send("Target.createTarget", { url: "about:blank" });
  const targets = await (await fetch(`${CDP_ROOT}/json/list`)).json();
  const cdp = new CDP(targets.find(item => item.id === target.targetId).webSocketDebuggerUrl);
  const requests = [];
  cdp.listeners.push(({ method, params }) => {
    if (method === "Runtime.exceptionThrown") report.consoleErrors.push({ viewport, ...params });
    if (method === "Runtime.consoleAPICalled" && params.type === "error") report.consoleErrors.push({ viewport, ...params });
    if (method === "Network.requestWillBeSent") {
      requests.push({ url: params.request.url, method: params.request.method });
      if (/^https?:/.test(params.request.url) && !params.request.url.startsWith(URL_ROOT + "/")) {
        report.externalRequests.push(params.request.url);
      }
    }
    if (method === "Network.responseReceived" && params.response.status >= 400) {
      report.networkErrors.push({ viewport, url: params.response.url, status: params.response.status });
    }
    if (method === "Network.loadingFailed" && !params.canceled) report.networkErrors.push({ viewport, ...params });
  });
  try {
    await Promise.all([cdp.send("Page.enable"), cdp.send("Runtime.enable"), cdp.send("Network.enable")]);
    await cdp.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
    await cdp.send("Page.navigate", { url: `${URL_ROOT}/` });
    await cdp.until("typeof app !== 'undefined' && app.metadata && window.M11DUX && document.getElementById('ux-mode')");
    check(`${viewport}: GET did not run receiver`, !requests.some(item => item.method === "POST"));
    const startState = await cdp.evaluate("({charset:document.characterSet,active:document.querySelector('.view.active')?.id,breadcrumb:document.querySelector('#view-demo #ux-breadcrumb')?.textContent,explainer:document.querySelector('#view-demo #ux-explainer')?.innerText,hasUkrainian:document.body.innerText.includes('Налаштування та запуск симуляції')})");
    check(`${viewport}: default Simulation Start and UTF-8 Ukrainian`, startState.charset.toUpperCase()==="UTF-8" && startState.active==="view-demo" && startState.hasUkrainian, startState);
    await layout(cdp, `${viewport} landing`);
    await screenshot(cdp, "start", viewport);
    await navigate(cdp, "demo");
    await cdp.input("#demo-preset", "defense_f32");
    await cdp.click("#run-demo");
    await cdp.until("app.trace?.input.symbol_count === 32 && !document.getElementById('run-demo').disabled");
    const summary = await cdp.evaluate("({symbols:app.trace.input.symbol_count,samples:app.trace.input.sample_count,rng:app.trace.input.rng_used,pairing:app.trace.pairing,arms:app.trace.arms.map(a=>({id:a.candidate_id,decoderCalls:a.viterbi.decoder_calls}))})");
    report.parameterRegistryDiagnostic = await cdp.evaluate(`(() => {
      const registry=app.metadata.parameters,live=runtimeInspectorEntries();
      const ids=new Set(registry.map(p=>p.parameter));
      return {registryCount:registry.length,registryCategories:Object.fromEntries(['core','runtime','technical'].map(c=>[c,registry.filter(p=>M11DUX.parameterCategory(p)===c).length])),
        liveCount:live.length,liveIds:live.map(p=>p.parameter),exactIdOverlap:live.filter(p=>ids.has(p.parameter)).map(p=>p.parameter),
        renderedCounts:Object.fromEntries(['core','runtime','technical','all'].map(c=>{const s=document.getElementById('parameter-category');s.value=c;s.dispatchEvent(new Event('change',{bubbles:true}));return [c,{registry:document.querySelectorAll('#parameter-groups .ux-param').length,selectedTrace:document.querySelectorAll('#parameter-groups .ux-live-value').length}]}))};
    })()`);
    check(`${viewport}: deterministic paired F32`, summary.symbols === 32 && summary.samples === 256 &&
      !summary.rng && summary.pairing.same_received_sha256 && summary.arms.length === 2 &&
      summary.arms.every(item => item.decoderCalls === 1), summary);
    check(`${viewport}: post-run result summary is human-readable`, await cdp.evaluate("document.querySelector('#demo-summary')?.innerText.includes('32') && document.querySelector('#demo-summary')?.innerText.includes('BER')"));
    await screenshot(cdp, "demo-results-post-run", viewport);
    check(`${viewport}: one explicit POST`, requests.filter(item => item.method === "POST").length === 1);
    for (const f of [0, 15, 31]) {
      await cdp.input("#ux-symbol", f, "input");
      check(`${viewport}: synchronized symbol ${f}`, await cdp.evaluate(`app.symbol === ${f} && ['ux-symbol','global-symbol','symbol-index','compare-index','table-index'].every(id=>Number(document.getElementById(id).value)===${f})`));
      const formulas = await cdp.evaluate(`window.M11DUX.formulaData(app.trace,1,${f},15)`);
      check(`${viewport}: formula context ${f}`, formulas.f === f && formulas.edge === 15 && formulas.nextAvailable === (f < 31), formulas);
    }
    await cdp.input("#ux-symbol", 15, "input");
    await navigate(cdp, "pipeline");
    await layout(cdp, `${viewport} pipeline`);
    await screenshot(cdp, "pipeline", viewport);
    await cdp.click("#view-pipeline [data-go='tables']");
    await cdp.until("document.getElementById('view-tables').classList.contains('active')");
    const hypothesisTable = await cdp.evaluate(`(() => {const rows=[...document.querySelectorAll('#exact-tables tbody tr')],r=app.trace.arms[Number(document.getElementById('table-arm').value)||0].symbols[app.symbol];return {rows:rows.length,metrics:r.candidate_metrics.length,weights:r.posterior.length,weightSum:r.posterior.reduce((a,b)=>a+b,0),allValuesMatch:rows.length===16&&rows.every((row,i)=>row.cells[5].textContent===r.candidate_metrics[i].toPrecision(10)&&row.cells[6].textContent===r.posterior[i].toPrecision(10))}})()`);
    check(`${viewport}: sixteen actual metrics and normalized posterior rows`, hypothesisTable.rows === 16 &&
      hypothesisTable.metrics === 16 && hypothesisTable.weights === 16 && Math.abs(hypothesisTable.weightSum-1)<1e-12 && hypothesisTable.allValuesMatch,hypothesisTable);
    await navigate(cdp, "pipeline");
    await navigate(cdp, "trellis");
    await cdp.input("#trellis-mode", "graph");
    const graph = await cdp.evaluate("({stateCount:app.metadata.states.length,distinctStates:new Set(app.metadata.states.map(x=>JSON.stringify(x))).size,edgeIds:app.metadata.edges.map(x=>x.edge_id),renderedPaths:document.querySelectorAll('#trellis-canvas [data-edge-graph]').length,tableRows:document.querySelectorAll('#edge-table tbody tr').length})");
    check(`${viewport}: exact four-state, sixteen-edge graph and edge table`, graph.stateCount === 4 &&
      graph.distinctStates === 4 && JSON.stringify(graph.edgeIds) === JSON.stringify(Array.from({length:16},(_,i)=>i)) &&
      graph.renderedPaths === 16 && graph.tableRows === 16, graph);
    for (const edge of [0, 15]) {
      await cdp.input("#hypothesis-select", edge);
      check(`${viewport}: selected edge ${edge}`, await cdp.evaluate(`app.edge === ${edge} && Number(document.getElementById('hypothesis-select').value) === ${edge}`));
    }
    await layout(cdp, `${viewport} graph`);
    await screenshot(cdp, "trellis", viewport);
    await cdp.input("#trellis-mode", "time");
    await layout(cdp, `${viewport} time trellis`);
    await screenshot(cdp, "time-trellis", viewport);
    for (const view of ["symbol", "estimator", "decode", "compare", "datasets"]) {
      await navigate(cdp, view);
      if (view === "symbol") {
        check(`${viewport}: real I/Q signal plot is visible`, await cdp.evaluate("document.querySelector('#symbol-detail svg')?.getAttribute('role')==='img' || document.querySelector('#symbol-detail svg')?.querySelectorAll('polyline').length===3"));
        const phaseHelp = `.view.active [data-help="source.phase_increment"]`;
        await cdp.click(phaseHelp);
        await cdp.until("document.getElementById('help-dialog').open");
        const phaseText = await cdp.evaluate("document.getElementById('help-body').innerText");
        check(`${viewport}: phase increment help distinguishes Δφ from φ0`, phaseText.includes("π/4") && phaseText.includes("SOURCE_EXACT_VERIFIED") && phaseText.includes("φ₀"), phaseText);
        await cdp.click("#help-close");
      }
      if (view === "estimator") {
        const actualFormula = await cdp.evaluate(`(() => {const ai=Number(document.getElementById('estimator-arm').value)||0,d=window.M11DUX.formulaData(app.trace,ai,app.symbol,15),t=document.getElementById('estimator-view').innerText,parts=v=>v.map(x=>x.toPrecision(7));return {hasSubstitution:t.includes('Підстановка з фактичного trace'),hasResult:t.includes('Результат trace'),hasSource:t.includes('[A] с. 4'),post:d.post,innovation:d.innovation,hasActualPost:parts(d.post).every(x=>t.includes(x)),hasActualInnovation:parts(d.innovation).every(x=>t.includes(x))}})()`);
        check(`${viewport}: estimator formula uses actual pre/post trace operands`, actualFormula.hasSubstitution && actualFormula.hasResult &&
          actualFormula.hasSource && actualFormula.hasActualPost && actualFormula.hasActualInnovation, actualFormula);
      }
      if (view === "decode") {
        const decode = await cdp.evaluate("(() => {const box=document.querySelector('#ux-decode');return {text:box?.innerText,html:box?.innerHTML.slice(0,1200),active:document.querySelector('.view.active')?.id,rows:box?.querySelectorAll('tbody tr').length,trace:!!app.trace,arms:app.trace?.arms?.length}})()");
        check(`${viewport}: actual conditional Viterbi path is visible`, Boolean(decode.text?.includes("Viterbi") && decode.text.length > 100), decode);
      }
      if (view === "compare") {
        check(`${viewport}: both policies use shared received buffer`, await cdp.evaluate("document.querySelector('#compare-view')?.innerText.includes(app.trace.input.received_sha256) && app.trace.pairing.same_received_sha256"));
      }
      if (view === "datasets") {
        await cdp.until("document.querySelectorAll('#research-dashboard article.card').length===8");
        const archived = await cdp.evaluate(`(async()=>{const d=await(await fetch('/api/archive-views')).json(),m9=d.charts.find(c=>c.id==='m9-delta-ber'),m10=d.charts.find(c=>c.id==='m10-p1-delta-ber');return {chartCount:d.charts.length,allAvailable:d.charts.every(c=>c.status==='AVAILABLE'),m9:m9.series[0].values,m9Zero:m9.contains_zero,m10:m10.series[0].values,m10Zero:m10.contains_zero,categories:d.charts.map(c=>c.evidence_category)}})()`);
        check(`${viewport}: archived M9/M10 CIs preserve exact values and contain zero`, archived.chartCount === 8 && archived.allAvailable &&
          archived.m9[1] === -0.0011328125 && archived.m9[0] === -0.0032226562500000007 && archived.m9[2] === 0.0006835937499999994 &&
          archived.m9Zero && archived.m10[1] === -0.00031249999999999334 && archived.m10[0] === -0.0020512695312500002 && archived.m10[2] === 0.0014453125 && archived.m10Zero, archived);
      }
      await layout(cdp, `${viewport} ${view}`);
      await screenshot(cdp, view, viewport);
    }
    await navigate(cdp, "parameters");
    const categories = {};
    for (const category of ["core", "runtime", "technical", "all"]) {
      await cdp.input("#parameter-category", category);
      categories[category] = await cdp.evaluate("document.querySelectorAll('#parameter-groups .ux-param').length");
      const inventory = await cdp.evaluate(`({shown:document.querySelectorAll('#parameter-groups .ux-param').length,baseCount:app.metadata.parameters.length,runtimeCount:window.M11DUX.parameterCategory?document.querySelectorAll('#parameter-groups .ux-param').length:0,select:document.querySelector('#parameter-category').value,search:document.querySelector('#parameter-search').value,traceSymbols:app.trace?.input.symbol_count,arm:app.arm,groupCounts:Object.fromEntries(['core','runtime','technical'].map(c=>[c,app.metadata.parameters.filter(p=>window.M11DUX.parameterCategory(p)===c).length])),examples:app.metadata.parameters.slice(0,3).map(p=>({parameter:p.parameter,group:p.group,type:p.type}))})`);
      check(`${viewport}: category ${category} populated`, categories[category] > 0, {rows:categories[category],inventory});
    }
    if (report.parameterRegistryDiagnostic.registryCount === 459) {
      check(`${viewport}: registry categories preserve 459-entry baseline`,
        categories.core === 125 && categories.runtime === 258 && categories.technical === 76 && categories.all === 459,
        {core:categories.core,runtime:categories.runtime,technical:categories.technical,all:categories.all});
      check(`${viewport}: selected-symbol runtime snapshot remains available outside registry count`,
        await cdp.evaluate("document.querySelectorAll('#parameter-groups .ux-live-value').length===27"),
        report.parameterRegistryDiagnostic.renderedCounts);
    }
    check(`${viewport}: categories form full partition`, categories.all === categories.core + categories.runtime + categories.technical, categories);
    await cdp.input("#parameter-category", "core");
    await cdp.input("#parameter-search", "alpha", "input");
    check(`${viewport}: parameter search`, await cdp.evaluate("document.querySelectorAll('#parameter-groups .ux-param').length > 0 && [...document.querySelectorAll('#parameter-groups .ux-param')].every(e=>e.textContent.toLowerCase().includes('alpha'))"));
    await cdp.input("#parameter-search", "", "input");
    await layout(cdp, `${viewport} parameters`);
    await screenshot(cdp, "parameters", viewport);
    for (const mode of ["scientific", "simple"]) {
      await cdp.input("#ux-mode", mode);
      check(`${viewport}: mode ${mode}`, await cdp.evaluate(`document.getElementById('ux-mode').value === '${mode}'`));
      await navigate(cdp, "symbol");
      await layout(cdp, `${viewport} ${mode} mode`);
    }
    await navigate(cdp, "parameters");
    await cdp.input("#parameter-category", "all");
    for (const [parameter, expected] of [["profile.sigma_squared", "M9b approved config"], ["profile.gamma_b_eff_db", "M9b approved config"]]) {
      await cdp.input("#parameter-search", parameter, "input");
      const selector = "#parameter-groups .ux-param .help-button";
      const exists = await cdp.evaluate(`document.querySelectorAll(${JSON.stringify(selector)}).length===1 && document.querySelector(${JSON.stringify(selector)}).dataset.help===${JSON.stringify(parameter)}`);
      check(`${viewport}: archived ${parameter} is searchable with help`, exists);
      await cdp.click(selector);
      await cdp.until("document.getElementById('help-dialog').open");
      const helpText = await cdp.evaluate("document.getElementById('help-body').innerText");
      check(`${viewport}: ${parameter} help identifies archive provenance and fixture boundary`, helpText.includes(expected) && helpText.includes("not the F=32 fixture"), helpText);
      await cdp.click("#help-close");
    }
    await cdp.input("#parameter-search", "", "input");
    await cdp.input("#parameter-category", "runtime");
    await cdp.input("#parameter-search", "runtime.alpha_prime", "input");
    const helpSelector = ".view.active [data-help]";
    await cdp.evaluate(`window.__helpMouseOpener=document.querySelector('${helpSelector}')`);
    await cdp.click(helpSelector);
    await cdp.until("document.getElementById('help-dialog').open");
    check(`${viewport}: help opens by mouse`, await cdp.evaluate("document.getElementById('help-dialog').open"));
    const focusBeforeEscape = await cdp.evaluate(`(() => {
      const dialog=document.getElementById('help-dialog');
      const active=document.activeElement;
      return {activeTag:active.tagName,activeId:active.id,activeClass:active.className,
        dialogOpen:dialog.open,activeInside:dialog.contains(active),
        openerCount:document.querySelectorAll('${helpSelector}').length,
        openerConnected:window.__helpMouseOpener?.isConnected,
        openerTag:window.__helpMouseOpener?.tagName,openerClass:window.__helpMouseOpener?.className,
        activeIsOpener:active===window.__helpMouseOpener};
    })()`);
    await cdp.key("Escape", "Escape", 27);
    await cdp.until("!document.getElementById('help-dialog').open");
    const focusAfterEscape = await cdp.evaluate(`(() => {
      const e=document.activeElement;
      return {activeTag:e.tagName,activeId:e.id,activeClass:e.className,
        isHelp:e.matches('[data-help]'),dialogOpen:document.getElementById('help-dialog').open};
    })()`);
    await cdp.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
    const focusAfterStabilization = await cdp.evaluate(`(() => {
      const e=document.activeElement;
      return {activeTag:e.tagName,activeId:e.id,activeClass:e.className,
        isHelp:e.matches('[data-help]'),dialogOpen:document.getElementById('help-dialog').open};
    })()`);
    report.focusDiagnostic = {viewport,beforeEscape:focusBeforeEscape,
      immediatelyAfterEscape:focusAfterEscape,afterDomStabilization:focusAfterStabilization};
    await cdp.evaluate(`(() => {const e=document.querySelector('${helpSelector}');if(!e)throw Error('No visible help button'); window.__helpKeyboardOpener=e;e.scrollIntoView({block:'center'});e.focus();})()`);
    await cdp.key("Enter", "Enter", 13);
    await cdp.until("document.getElementById('help-dialog').open");
    check(`${viewport}: help keyboard focus contained`, await cdp.evaluate("document.getElementById('help-dialog').contains(document.activeElement)"));
    const alphaHelp = await cdp.evaluate(`(() => {const v=document.getElementById('help-body').innerText,a=app.trace.arms[Number(document.getElementById('symbol-arm').value)||0],exact=String(a.parameters.alpha_prime);return {text:v,expectedValue:exact,hasExactValue:v.includes(exact),hasSource:v.includes('[A] p.4 (1)'),hasStatus:v.includes('SOURCE_PARTIAL')}})()`);
    check(`${viewport}: alpha-prime help shows exact value and source fidelity`, alphaHelp.hasExactValue && alphaHelp.hasSource && alphaHelp.hasStatus, alphaHelp);
    await cdp.key("Tab", "Tab", 9);
    check(`${viewport}: help Tab remains contained`, await cdp.evaluate("document.getElementById('help-dialog').contains(document.activeElement)"));
    await cdp.key("Tab", "Tab", 9, 8);
    check(`${viewport}: help Shift+Tab remains contained`, await cdp.evaluate("document.getElementById('help-dialog').contains(document.activeElement)"));
    await screenshot(cdp, "help", viewport);
    await cdp.key("Escape", "Escape", 27);
    await cdp.until("!document.getElementById('help-dialog').open");
    check(`${viewport}: help Escape restores exact mouse opener`, await cdp.evaluate("document.activeElement===window.__helpMouseOpener"));
    await cdp.evaluate(`window.__dialogListenerAdds=0;const d=document.getElementById('help-dialog'),add=d.addEventListener.bind(d);d.addEventListener=(type,...args)=>{if(type==='keydown'||type==='close')window.__dialogListenerAdds++;return add(type,...args)}`);
    await cdp.click(helpSelector);
    await cdp.until("document.getElementById('help-dialog').open");
    await cdp.click("#help-close");
    check(`${viewport}: close button restores exact opener`, await cdp.evaluate("document.activeElement===window.__helpKeyboardOpener"));
    const listenerBaseline = await cdp.evaluate("window.__dialogListenerAdds");
    for (let cycle = 0; cycle < 10; cycle++) {
      await cdp.click(helpSelector);
      await cdp.until("document.getElementById('help-dialog').open");
      await cdp.key("Escape", "Escape", 27);
      await cdp.until("!document.getElementById('help-dialog').open");
      check(`${viewport}: help repeated cycle ${cycle + 1} restores focus`, await cdp.evaluate("document.activeElement===window.__helpKeyboardOpener"));
    }
    check(`${viewport}: help repeated cycles add no dialog listeners`, await cdp.evaluate(`window.__dialogListenerAdds===${listenerBaseline}`), {baseline:listenerBaseline,after:await cdp.evaluate("window.__dialogListenerAdds")});
    await cdp.input("#symbol-arm", "1");
    await cdp.evaluate(`window.__helpKeyboardOpener=document.querySelector('${helpSelector}')`);
    await cdp.click(helpSelector);
    await cdp.until("document.getElementById('help-dialog').open");
    const switchedHelp = await cdp.evaluate(`(() => {const v=document.getElementById('help-body').innerText;return {arm:app.arm,alpha:app.trace.arms[app.arm].parameters.alpha_prime,exact:v.includes(String(app.trace.arms[app.arm].parameters.alpha_prime)),openerConnected:window.__helpKeyboardOpener?.isConnected}})()`);
    check(`${viewport}: receiver switch refreshes help value and opener`, switchedHelp.arm === 1 && switchedHelp.alpha === 0.85 && switchedHelp.exact && switchedHelp.openerConnected, switchedHelp);
    await cdp.key("Escape", "Escape", 27);
    await cdp.until("!document.getElementById('help-dialog').open");
    check(`${viewport}: receiver-switched help restores current opener`, await cdp.evaluate("document.activeElement===window.__helpKeyboardOpener"));
    await cdp.click(helpSelector);
    await cdp.until("document.getElementById('help-dialog').open");
    await cdp.evaluate(`window.__helpKeyboardOpener.remove()`);
    await cdp.click("#help-close");
    check(`${viewport}: removed opener uses Inspector fallback`, await cdp.evaluate("document.activeElement.id==='parameter-search'"));
    await navigate(cdp, "defense");
    await cdp.click("#defense-reset");
    const slideTitles = [];
    for (let step = 0; step < 18; step++) {
      check(`${viewport}: presentation ${step + 1}`, await cdp.evaluate(`app.defense===${step} && document.getElementById('defense-content').textContent.length>100`));
      slideTitles.push(await cdp.evaluate("document.querySelector('#defense-content h2')?.textContent"));
      await layout(cdp, `${viewport} presentation ${step + 1}`);
      if ([0, 10, 12, 14, 16, 17].includes(step)) await screenshot(cdp, `presentation-${step + 1}`, viewport);
      if (step < 17) await cdp.click("#defense-next");
    }
    check(`${viewport}: 18 distinct presentation titles`, new Set(slideTitles).size === 18, slideTitles);
    await cdp.click("#defense-prev");
    check(`${viewport}: presentation previous`, await cdp.evaluate("app.defense===16"));
    await cdp.click("#defense-return");
    await cdp.click('.nav-item[data-view="pipeline"]');
    await cdp.until("document.getElementById('view-pipeline').classList.contains('active')");
    await cdp.click("#view-pipeline [data-go='tables']");
    for (const selector of ["#export-json", "#export-csv"]) {
      const count = report.downloads.length;
      await cdp.click(selector);
      for (let attempt = 0; attempt < 100 && report.downloads.length === count; attempt++) await sleep(50);
      check(`${viewport}: download ${selector}`, report.downloads.length > count);
    }
    await navigate(cdp, "demo");
    check(`${viewport}: return to detailed simulation`, await cdp.evaluate("document.getElementById('view-demo').classList.contains('active')"));
    check(`${viewport}: no console errors`, report.consoleErrors.length === 0, report.consoleErrors);
    check(`${viewport}: no network errors`, report.networkErrors.length === 0, report.networkErrors);
    check(`${viewport}: local-only requests`, report.externalRequests.length === 0, report.externalRequests);
  } finally {
    cdp.close();
    await browser.send("Target.closeTarget", { targetId: target.targetId });
  }
}

async function main() {
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
  fs.mkdirSync(DOWNLOADS, { recursive: true });
  await ensureServer();
  const version = await (await fetch(`${CDP_ROOT}/json/version`)).json();
  report.browser = version.Browser;
  const browser = new CDP(version.webSocketDebuggerUrl);
  browser.listeners.push(({ method, params }) => {
    if (method === "Browser.downloadWillBegin") report.downloads.push(params);
    if (method === "Browser.downloadProgress") {
      const download = report.downloads.find(item => item.guid === params.guid);
      if (download) Object.assign(download, { state: params.state, receivedBytes: params.receivedBytes });
    }
  });
  try {
    await browser.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: DOWNLOADS, eventsEnabled: true });
    await runViewport(1366, 768, browser);
    await runViewport(1920, 1080, browser);
    await sleep(200);
    check("All four downloads completed", report.downloads.length === 4 && report.downloads.every(item => item.state === "completed"), report.downloads);
    report.passed = true;
  } finally { browser.close(); }
}

main().catch(error => {
  report.failure = error.stack || String(error);
  process.exitCode = 1;
}).finally(() => {
  if (ownedServer) ownedServer.kill();
  report.finished = new Date().toISOString();
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length,
    screenshots: report.screenshots.length, report: REPORT_PATH, failure: report.failure || null }, null, 2));
});
