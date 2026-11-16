"use strict";

// Real Microsoft Edge QA for M11g interactive controls and projector mode.
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.M11G_URL || "http://127.0.0.1:18768";
const CDP = process.env.M11G_CDP || "http://127.0.0.1:9224";
const screenshots = path.join(ROOT, "docs", "screenshots");
fs.mkdirSync(screenshots, { recursive: true });
const report = { url: BASE, viewports: [], checks: [], screenshots: [], exceptions: [] };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

class Browser {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.onEvent = () => {};
    this.socket.addEventListener("message", event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (pending) { this.pending.delete(message.id); message.error ? pending.reject(Error(JSON.stringify(message.error))) : pending.resolve(message.result); }
      } else this.onEvent(message);
    });
  }
  async ready() { if (this.socket.readyState !== WebSocket.OPEN) await new Promise((resolve, reject) => { this.socket.addEventListener("open", resolve, { once: true }); this.socket.addEventListener("error", reject, { once: true }); }); }
  async send(method, params = {}) { await this.ready(); const id = ++this.id; return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.socket.send(JSON.stringify({ id, method, params })); }); }
  async evaluate(expression) { const result = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails)); return result.result.value; }
  async until(expression, timeout = 20000) { const stop = Date.now() + timeout; while (Date.now() < stop) { if (await this.evaluate(expression)) return; await pause(100); } throw Error(`Timeout waiting for ${expression}`); }
  async click(selector) { const point = await this.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('missing '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`); await this.send("Input.dispatchMouseEvent", { type: "mousePressed", ...point, button: "left", clickCount: 1 }); await this.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...point, button: "left", clickCount: 1 }); }
  async typeRange(selector, value) { await this.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.value=${Number(value)};e.dispatchEvent(new Event('input',{bubbles:true}))})()`); }
  async screenshot(name, viewport) { await this.evaluate("document.getElementById('signal-chart-title')?.scrollIntoView({block:'start'})"); await pause(150); const png = await this.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); const file = `m11g-${name}-${viewport}.png`; fs.writeFileSync(path.join(screenshots, file), Buffer.from(png.data, "base64")); report.screenshots.push(`docs/screenshots/${file}`); }
  check(name, ok, details) { report.checks.push({ name, ok: Boolean(ok), details }); if (!ok) throw Error(`${name}: ${JSON.stringify(details)}`); }
}

async function viewport(width, height) {
  const label = `${width}x${height}`;
  const targets = await fetch(`${CDP}/json`).then(response => response.json());
  const target = targets.find(item => item.type === "page");
  if (!target) throw Error("No Edge page target available");
  const browser = new Browser(target.webSocketDebuggerUrl);
  report.viewports.push(label);
  browser.onEvent = message => { if (message.method === "Runtime.exceptionThrown") report.exceptions.push({ viewport: label, details: message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text, stack: message.params.exceptionDetails?.exception?.description?.split("\n").slice(1) }); };
  await Promise.all([browser.send("Page.enable"), browser.send("Runtime.enable"), browser.send("Network.enable")]);
  await browser.send("Network.setCacheDisabled", { cacheDisabled: true });
  await browser.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await browser.send("Page.navigate", { url: `${BASE}/` });
  await browser.until("window.M11DUX && app.metadata && document.getElementById('signal-chart-type')");
  browser.check(`${label}: GET does not run simulation`, await browser.evaluate("app.trace===null"));
  browser.check(`${label}: interactive inputs and projector controls exist`, await browser.evaluate("!!document.getElementById('interactive-bits') && !!document.getElementById('interactive-file') && !!document.getElementById('projector-toggle') && document.getElementById('run-demo').disabled===false"));
  browser.check(`${label}: source/status caveat visible`, await browser.evaluate("document.getElementById('view-signal').innerText.includes('paper_exact:false') && document.getElementById('view-signal').innerText.includes('receiver_enabled:false')"));
  browser.check(`${label}: custom input Start handler is installed`, await browser.evaluate("String(document.getElementById('run-demo').onclick).includes('parseManualBits')"));
  await browser.evaluate("document.querySelector('[data-help=\\\"interactive.encoder\\\"]').click()");
  browser.check(`${label}: encoder help button opens Inspector dialog`, await browser.evaluate("document.getElementById('help-dialog').open && document.getElementById('help-title').innerText.includes('encoder')"));
  await browser.evaluate("document.getElementById('help-close').click()");
  browser.check(`${label}: encoder A initial state is fixed to compatible reset`, await browser.evaluate("document.getElementById('interactive-state').disabled && document.getElementById('interactive-state').value==='0'"));
  await browser.evaluate("(()=>{const e=document.getElementById('interactive-bits');e.value='01x0';e.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('run-demo').onclick()})()");
  browser.check(`${label}: invalid manual input is rejected before POST`, await browser.evaluate("app.trace===null && document.getElementById('interactive-warning').innerText.includes('0')"));
  await browser.evaluate("(()=>{const e=document.getElementById('interactive-file');Object.defineProperty(e,'files',{configurable:true,value:[new File(['01,10\\n0011'],'bits.csv',{type:'text/csv'})]});e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  await browser.until("document.getElementById('interactive-bits').value==='01100011'");
  browser.check(`${label}: local CSV bits are loaded and parsed`, await browser.evaluate("document.getElementById('interactive-template').value==='custom' && document.getElementById('interactive-bits').value==='01100011'"));
  await browser.evaluate("(()=>{const e=document.getElementById('interactive-template');e.value='verified';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  browser.check(`${label}: verified F=32 preset restores exactly 64 bits`, await browser.evaluate("document.getElementById('interactive-bits').value.length===64 && document.getElementById('interactive-bits').value===app.metadata.demo.defense_preset.bits.join('')"));
  browser.check(`${label}: supported receiver parameters are editable in interactive mode`, await browser.evaluate("['alpha','k-i','k-q','beta','noise-fixture','receiver-mode'].every(id=>!document.getElementById(id).disabled)"));
  await browser.evaluate("(()=>{const e=document.getElementById('interactive-bits');e.value='01'.repeat(32);e.dispatchEvent(new Event('input',{bubbles:true}))})()");
  browser.check(`${label}: valid manually entered bits are retained exactly`, await browser.evaluate("document.getElementById('interactive-bits').value==='01'.repeat(32) && document.getElementById('interactive-template').value==='custom'"));
  browser.check(`${label}: initial page fits width`, await browser.evaluate("document.documentElement.scrollWidth<=innerWidth+1"));
  await browser.evaluate("document.getElementById('run-demo').onclick()");
  try { await browser.until("app.trace?.input.symbol_count===32 && !document.getElementById('run-demo').disabled"); } catch (error) { const state = await browser.evaluate("({trace:app.trace?.input,button:document.getElementById('run-demo').disabled,status:document.getElementById('demo-status').innerText,warning:document.getElementById('interactive-warning').innerText,bits:document.getElementById('interactive-bits').value,handler:String(document.getElementById('run-demo').onclick),encoder:document.getElementById('interactive-encoder').value,exceptions:window.__m11gErrors||[]})"); throw Error(`${error.message}; browser state=${JSON.stringify(state)}`); }
  browser.check(`${label}: explicit deterministic F=32 POST produced actual input trace`, await browser.evaluate("app.trace.input.sample_count===256 && app.trace.input.rng_used===false && app.trace.input.information_bits.join('')===document.getElementById('interactive-bits').value.replace(/\\s/g,'')"));
  await browser.click(".nav-item[data-view='samples']");
  await browser.until("document.getElementById('view-signal').classList.contains('active')");
  browser.check(`${label}: 17 views sourced from runtime trace`, await browser.evaluate("document.querySelectorAll('#signal-chart-type option').length===17 && app.trace.transmitter.received_samples.length===256"));
  await browser.evaluate("(()=>{const e=document.getElementById('signal-chart-type');e.value='constellation';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  browser.check(`${label}: constellation highlights selected symbol and 20-symbol window`, await browser.evaluate("document.querySelectorAll('#signal-chart .signal-window-point').length===19 && document.querySelectorAll('#signal-chart .signal-selected-point').length===1"));
  await browser.evaluate("(()=>{const e=document.getElementById('signal-chart-type');e.value='input_bits';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  const chartTypes = await browser.evaluate("[...document.querySelectorAll('#signal-chart-type option')].map(option=>option.value)");
  for (const chartType of chartTypes) {
    await browser.evaluate(`(()=>{const e=document.getElementById('signal-chart-type');e.value=${JSON.stringify(chartType)};e.dispatchEvent(new Event('change',{bubbles:true}))})()`);
    const chart = await browser.evaluate("(()=>{const svg=document.querySelector('#signal-chart svg[role=img]'),ticks=[...(svg?.querySelectorAll('text')||[])].map(e=>e.textContent.trim()).filter(s=>/^-?\\d+(\\.\\d+)?$/.test(s));return{svg:!!svg,text:document.getElementById('signal-chart').innerText,detail:document.getElementById('signal-stage-detail').innerText,ticks,maxTickLength:Math.max(0,...ticks.map(s=>s.length))}})()");
    browser.check(`${label}: chart ${chartType} renders finite data and concise axis ticks`, chart.svg && !/undefined|NaN/.test(chart.text + chart.detail) && chart.maxTickLength<=10, chart);
  }
  await browser.evaluate("(()=>{const e=document.getElementById('signal-chart-type');e.value='input_bits';e.dispatchEvent(new Event('change',{bubbles:true}))})()");
  const expected = [{ name: "first", start: 0, firstSymbol: 0, lastSymbol: 19 }, { name: "middle", start: 48, firstSymbol: 6, lastSymbol: 25 }, { name: "last", start: 96, firstSymbol: 12, lastSymbol: 31 }];
  for (const win of expected) {
    await browser.typeRange("#signal-sample-offset", win.start);
    const snapshot = await browser.evaluate(`(()=>({start:Number(document.getElementById('signal-sample-offset').value),end:window.HFTCMSignalExplorerState.endSample,first:window.HFTCMSignalExplorerState.startSymbol,last:window.HFTCMSignalExplorerState.endSymbol-1,path:document.getElementById('signal-path-summary').textContent,chart:document.getElementById('signal-chart').innerText,selected:app.symbol}))()`);
    browser.check(`${label}: ${win.name} visual window sample/symbol indices`, snapshot.start === win.start && snapshot.end === win.start + 160 && snapshot.first === win.firstSymbol && snapshot.last === win.lastSymbol, snapshot);
    browser.check(`${label}: ${win.name} synchronized trace and decoded path`, snapshot.path.includes(`f=${win.firstSymbol}…${win.lastSymbol}`) && !/undefined|NaN/.test(snapshot.path + snapshot.chart), snapshot);
    await browser.screenshot(win.name, label);
    await browser.click("#signal-to-trellis");
    const trellis = await browser.evaluate("({active:document.getElementById('view-trellis').classList.contains('active'),uxView:document.body.dataset.uxView,current:window.HFTCMMinimalistUIState?.activeView,classes:document.getElementById('view-trellis').className,highlight:!!document.querySelector('.trellis-window-highlight'),rect:document.querySelector('.trellis-window-highlight')?.getAttribute('width'),offset:Number(document.getElementById('trellis-offset').value),decoded:document.querySelector('#trellis-canvas .decoded')!==null})");
    browser.check(`${label}: ${win.name} trellis window synchronized`, trellis.active && trellis.highlight && trellis.decoded && trellis.offset === win.firstSymbol, trellis);
    await browser.click(".nav-item[data-view='samples']");
  }
  await browser.typeRange("#signal-symbol", 31);
  browser.check(`${label}: selected symbol shows its eight samples and centers safely`, await browser.evaluate("app.symbol===31 && Number(document.getElementById('signal-sample-offset').value)===96 && document.getElementById('signal-stage-detail').textContent.includes('248')"));
  await browser.screenshot("selected-symbol", label);
  await browser.click("#signal-zoom-symbol");
  browser.check(`${label}: selected-symbol zoom shows 8 samples`, await browser.evaluate("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===8"));
  await browser.click("#signal-zoom-20");
  browser.check(`${label}: 20-sample zoom is separate from decoder depth`, await browser.evaluate("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===20 && document.getElementById('signal-path-summary').textContent.includes('decoder')"));
  await browser.click("#signal-window-reset");
  browser.check(`${label}: 20-symbol x 8-sample window restored`, await browser.evaluate("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===160"));
  await browser.evaluate("document.getElementById('projector-toggle').click()");
  const projector = await browser.evaluate("({active:document.body.classList.contains('projector-mode'),minHeight:getComputedStyle(document.querySelector('.signal-main-card')).minHeight,overflow:document.documentElement.scrollWidth>innerWidth,offenders:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).slice(0,8).map(e=>({tag:e.tagName,id:e.id,class:e.className,right:Math.round(e.getBoundingClientRect().right),width:Math.round(e.getBoundingClientRect().width)}))})");
  browser.check(`${label}: projector mode styles and responsive width`, projector.active && !projector.overflow && (label !== '1920x1080' || parseInt(projector.minHeight) >= 500), projector);
  await browser.evaluate("document.getElementById('projector-theme').value='dark';document.getElementById('projector-theme').dispatchEvent(new Event('change',{bubbles:true}))");
  browser.check(`${label}: projector dark theme selectable`, await browser.evaluate("document.body.dataset.projectorTheme==='dark'"));
  browser.check(`${label}: dark projector SVG labels have high-contrast foreground`, await browser.evaluate("getComputedStyle(document.querySelector('#signal-chart svg text')).fill==='rgb(245, 247, 250)'"));
  await browser.evaluate("document.getElementById('projector-sidebar').click()");
  browser.check(`${label}: projector sidebar can collapse`, await browser.evaluate("document.body.classList.contains('projector-sidebar-collapsed') && getComputedStyle(document.querySelector('.sidebar')).display==='none'"));
  await browser.evaluate("document.getElementById('projector-sidebar').click()");
  browser.check(`${label}: presenter notes remain collapsed by default`, await browser.evaluate("!document.getElementById('presenter-notes').open"));
  await browser.screenshot("projector", label);
  await browser.evaluate("document.getElementById('projector-toggle').click();document.getElementById('interactive-encoder').value='B';document.getElementById('interactive-encoder').dispatchEvent(new Event('change',{bubbles:true}))");
  browser.check(`${label}: encoder B disables receiver execution and retains the prior trace as stale`, await browser.evaluate("document.getElementById('run-demo').disabled && document.getElementById('receiver-mode').disabled && app.trace!==null && window.HFTCMMinimalistUIState.stale"));
  await browser.evaluate("document.getElementById('encoder-b-preview').onclick()");
  try { await browser.until("document.querySelectorAll('#encoder-b-transition-table tbody tr').length===64"); } catch (error) { const state = await browser.evaluate("({warning:document.getElementById('interactive-warning').innerText,result:document.getElementById('encoder-b-result').innerText,handler:String(document.getElementById('encoder-b-preview').onclick),bits:document.getElementById('interactive-bits').value,encoder:document.getElementById('interactive-encoder').value})"); throw Error(`${error.message}; B preview state=${JSON.stringify(state)}`); }
  browser.check(`${label}: encoder B renders source trellis only without receiver`, await browser.evaluate("document.getElementById('encoder-b-result').innerText.includes('64') && !/undefined|NaN/.test(document.getElementById('encoder-b-result').innerText)"));
  await browser.evaluate("document.getElementById('interactive-encoder').value='A';document.getElementById('interactive-encoder').dispatchEvent(new Event('change',{bubbles:true}))");
  browser.check(`${label}: no runtime exceptions`, report.exceptions.filter(item => item.viewport === label).length === 0, report.exceptions.filter(item => item.viewport === label));
  browser.socket.close();
}

(async () => {
  try {
    await viewport(1366, 768);
    await viewport(1920, 1080);
    report.passed = true;
  } catch (error) { report.error = error.stack || String(error); }
  const reportPath = path.join(ROOT, "tmp", "m11g-edge-interactive-qa.json");
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, failed: report.checks.filter(item => !item.ok), viewports: report.viewports, screenshots: report.screenshots, report: reportPath, error: report.error || null }, null, 2));
  if (!report.passed) process.exitCode = 1;
})();
