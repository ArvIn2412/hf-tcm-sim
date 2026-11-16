"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.REPRO09_URL || "http://127.0.0.1:18769";
const CDP = process.env.REPRO09_CDP || "http://127.0.0.1:9224";
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class Browser {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.waiters = new Map();
    this.ws.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.id && this.waiters.has(message.id)) {
        const waiter = this.waiters.get(message.id);
        this.waiters.delete(message.id);
        message.error ? waiter.reject(Error(JSON.stringify(message.error))) : waiter.resolve(message.result);
      }
    };
  }
  async send(method, params = {}) {
    if (this.ws.readyState !== WebSocket.OPEN) await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.waiters.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  async wait(expression, timeout = 30000) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await this.eval(expression)) return;
      await sleep(100);
    }
    throw Error(`Timed out waiting for ${expression}`);
  }
  async screenshot(name) {
    await this.eval("window.scrollTo(0,0)");
    await sleep(300);
    const image = await this.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    const file = path.join(ROOT, "docs", "screenshots", name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, Buffer.from(image.data, "base64"));
    return path.relative(ROOT, file).replaceAll("\\", "/");
  }
}

async function main() {
  const pages = await fetch(`${CDP}/json`).then(response => response.json());
  const page = pages.findLast(target => target.type === "page");
  if (!page) throw Error("No Edge page target found");
  const browser = new Browser(page.webSocketDebuggerUrl);
  const checks = [];
  const screenshots = [];
  const check = (name, ok, evidence = null) => {
    checks.push({ name, passed: Boolean(ok), evidence });
    if (!ok) throw Error(`QA failed: ${name}: ${JSON.stringify(evidence)}`);
  };
  await browser.send("Page.enable");
  await browser.send("Runtime.enable");
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    await browser.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
    await browser.send("Page.navigate", { url: `${BASE}/scientific` });
    await browser.wait("document.querySelectorAll('.tab').length===8 && !!document.querySelector('#run-form')");
    await sleep(300);
    check(`${width}x${height}: scientific workspace loaded`, await browser.eval("document.documentElement.lang==='uk' && !!document.querySelector('#view-parameters')"));
    check(`${width}x${height}: no initial model run`, await browser.eval("document.querySelector('#job-status').textContent.includes('Очікує')"));
    check(`${width}x${height}: no horizontal overflow`, await browser.eval("document.documentElement.scrollWidth<=window.innerWidth+2"));
    if (width === 1366) {
      await browser.eval(`document.querySelector('[name=frame_symbols]').value='32';document.querySelector('[name=channel_profile]').value='identity';document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#run-form').requestSubmit()`);
      await browser.wait("document.querySelector('#paired-badge').textContent.includes('Парний') || document.querySelector('#job-status').textContent.includes('Не вдалося')", 30000);
      const badge = await browser.eval("document.querySelector('#paired-badge')?.outerHTML || document.title");
      const uiState = await browser.eval("({badge:document.querySelector('#paired-badge')?.textContent,status:document.querySelector('#job-status')?.textContent})");
      check("Identity run is actually paired", uiState.badge.includes("Парний observation"), {badge, uiState});
      check("Identity BER values are bound from real backend result", await browser.eval("document.querySelector('#comparison-cards').textContent.includes('BER 0')"));
      check("Joint and Separate receive matching observation hash", await browser.eval("document.querySelector('#paired-badge').textContent.includes('Парний observation')"));
      await browser.eval("document.querySelector('[data-view=transmitter]').click()");
      await browser.wait("document.querySelector('#chart-tx').width>0");
      check("transmitter chart contains frame data", await browser.eval("document.querySelector('#transmitter-values').textContent.includes('Фаза')"));
      await browser.eval("document.querySelector('[data-view=channel]').click()");
      await browser.wait("document.querySelector('#chart-channel').width>0");
      screenshots.push(await browser.screenshot("repro09-scientific-identity-1366x768.png"));
      await browser.eval("document.querySelector('[data-view=comparison]').click()");
    } else {
      await browser.eval("document.querySelector('[data-view=monte-carlo]').click()");
      await browser.eval("document.querySelector('#mc-id').value='qa-edge-'+Date.now();document.querySelector('#mc-frame').value='32';document.querySelector('#mc-noise').value='0.005';document.querySelector('#mc-trials').value='1';document.querySelector('#mc-form').requestSubmit()");
      await browser.wait("document.querySelector('#mc-status').textContent.includes('Серію збережено')", 30000);
      const mcUi = await browser.eval("({status:document.querySelector('#mc-status')?.textContent,results:document.querySelector('#mc-results')?.textContent,html:document.querySelector('#mc-results')?.innerHTML})");
      check("Monte Carlo GUI runs a real paired trial", mcUi.results?.includes("trials 1"), mcUi);
      check("Monte Carlo curve is bound to completed measurement", await browser.eval("document.querySelector('#mc-ber').width>0 && document.querySelector('#mc-results').textContent.includes('Δ')"));
      screenshots.push(await browser.screenshot("repro09-scientific-workspace-1920x1080.png"));
    }
  }
  console.log(JSON.stringify({ passed: true, checks, screenshots }, null, 2));
  browser.ws.close();
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
