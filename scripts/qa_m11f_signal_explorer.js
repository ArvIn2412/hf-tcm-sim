"use strict";

// Targeted real Microsoft Edge QA for the M11f visual sample window.
// It uses the existing deterministic F=32 demo preset and explicit UI POST.
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.M11F_URL || "http://127.0.0.1:18767";
const CDP = process.env.M11F_CDP || "http://127.0.0.1:9223";
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
  async screenshot(name, viewport) { await this.evaluate("document.getElementById('signal-chart-title')?.scrollIntoView({block:'start'})"); await pause(150); const png = await this.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); const file = `m11f-signal-${name}-${viewport}.png`; fs.writeFileSync(path.join(screenshots, file), Buffer.from(png.data, "base64")); report.screenshots.push(`docs/screenshots/${file}`); }
  check(name, ok, details) { report.checks.push({ name, ok: Boolean(ok), details }); if (!ok) throw Error(`${name}: ${JSON.stringify(details)}`); }
}

async function viewport(width, height) {
  const label = `${width}x${height}`;
  const targets = await fetch(`${CDP}/json`).then(response => response.json());
  const target = targets.find(item => item.type === "page");
  if (!target) throw Error("No Edge page target available");
  const browser = new Browser(target.webSocketDebuggerUrl);
  report.viewports.push(label);
  browser.onEvent = message => { if (message.method === "Runtime.exceptionThrown") report.exceptions.push({ viewport: label, details: message.params.exceptionDetails?.text }); };
  await Promise.all([browser.send("Page.enable"), browser.send("Runtime.enable")]);
  await browser.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await browser.send("Page.navigate", { url: `${BASE}/` });
  await browser.until("window.M11DUX && app.metadata && document.getElementById('signal-chart-type')");
  browser.check(`${label}: GET does not run simulation`, await browser.evaluate("app.trace===null"));
  browser.check(`${label}: source/status caveat visible`, await browser.evaluate("document.getElementById('view-signal').innerText.includes('paper_exact:false') && document.getElementById('view-signal').innerText.includes('receiver_enabled:false')"));
  browser.check(`${label}: initial page fits width`, await browser.evaluate("document.documentElement.scrollWidth<=innerWidth+1"));
  await browser.click("#run-demo");
  await browser.until("app.trace?.input.symbol_count===32 && !document.getElementById('run-demo').disabled");
  browser.check(`${label}: explicit deterministic POST produced F=32 trace`, await browser.evaluate("app.trace.input.sample_count===256 && app.trace.input.rng_used===false"));
  await browser.click(".nav-item[data-view='signal']");
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
    const snapshot = await browser.evaluate(`(()=>({start:Number(document.getElementById('signal-sample-offset').value),end:window.HFTCMSignalExplorerState.endSample,first:window.HFTCMSignalExplorerState.startSymbol,last:window.HFTCMSignalExplorerState.endSymbol-1,path:document.getElementById('signal-path-summary').innerText,chart:document.getElementById('signal-chart').innerText,selected:app.symbol}))()`);
    browser.check(`${label}: ${win.name} visual window sample/symbol indices`, snapshot.start === win.start && snapshot.end === win.start + 160 && snapshot.first === win.firstSymbol && snapshot.last === win.lastSymbol, snapshot);
    browser.check(`${label}: ${win.name} synchronized trace and decoded path`, snapshot.path.includes(`f=${win.firstSymbol}…${win.lastSymbol}`) && !/undefined|NaN/.test(snapshot.path + snapshot.chart), snapshot);
    await browser.screenshot(win.name, label);
    await browser.click("#signal-to-trellis");
    const trellis = await browser.evaluate("({active:document.getElementById('view-trellis').classList.contains('active'),highlight:!!document.querySelector('.trellis-window-highlight'),rect:document.querySelector('.trellis-window-highlight')?.getAttribute('width'),offset:Number(document.getElementById('trellis-offset').value),decoded:document.querySelector('#trellis-canvas .decoded')!==null})");
    browser.check(`${label}: ${win.name} trellis window synchronized`, trellis.active && trellis.highlight && trellis.decoded && trellis.offset === win.firstSymbol, trellis);
    await browser.click(".nav-item[data-view='signal']");
  }
  await browser.typeRange("#signal-symbol", 31);
  browser.check(`${label}: selected symbol shows its eight samples and centers safely`, await browser.evaluate("app.symbol===31 && Number(document.getElementById('signal-sample-offset').value)===96 && document.getElementById('signal-stage-detail').innerText.includes('248')"));
  await browser.screenshot("selected-symbol", label);
  browser.check(`${label}: no runtime exceptions`, report.exceptions.filter(item => item.viewport === label).length === 0, report.exceptions.filter(item => item.viewport === label));
  browser.socket.close();
}

(async () => {
  try {
    await viewport(1366, 768);
    await viewport(1920, 1080);
    report.passed = true;
  } catch (error) { report.error = error.stack || String(error); }
  const reportPath = path.join(ROOT, "tmp", "m11f-edge-signal-qa.json");
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, failed: report.checks.filter(item => !item.ok), viewports: report.viewports, screenshots: report.screenshots, report: reportPath, error: report.error || null }, null, 2));
  if (!report.passed) process.exitCode = 1;
})();
