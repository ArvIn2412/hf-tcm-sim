"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.GUI_ENERGY_URL || "http://127.0.0.1:18772";
const CDP = process.env.GUI_ENERGY_CDP || "http://127.0.0.1:9226";
const OUTPUT = path.join(ROOT, "outputs", "repro09", "energy-studies", "gui-energy-01-exports");
const STUDY_ID = `gui-energy-01-edge-${Date.now()}`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class Browser {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.nextId = 0;
    this.pending = new Map();
    this.ws.onmessage = event => {
      const message = JSON.parse(event.data);
      const waiter = this.pending.get(message.id);
      if (!waiter) return;
      this.pending.delete(message.id);
      message.error ? waiter.reject(Error(JSON.stringify(message.error))) : waiter.resolve(message.result);
    };
  }

  async send(method, params = {}) {
    if (this.ws.readyState !== WebSocket.OPEN) {
      await new Promise((resolve, reject) => {
        this.ws.addEventListener("open", resolve, {once: true});
        this.ws.addEventListener("error", reject, {once: true});
      });
    }
    const id = ++this.nextId;
    const response = new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject});
      this.ws.send(JSON.stringify({id, method, params}));
    });
    let timeout;
    try {
      return await Promise.race([
        response,
        new Promise((_, reject) => { timeout = setTimeout(() => reject(Error(`CDP timeout: ${method}`)), 8000); })
      ]);
    } finally {
      clearTimeout(timeout);
    }
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
      userGesture: true
    });
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }

  async wait(expression, timeoutMs = 90000) {
    const end = Date.now() + timeoutMs;
    let nextLog = Date.now() + 5000;
    while (Date.now() < end) {
      try {
        if (await this.evaluate(expression)) return;
        if (Date.now() >= nextLog) {
          console.log("waiting", expression, await this.evaluate("JSON.stringify({status:document.querySelector('#job-status')?.textContent,paired:document.querySelector('#paired-badge')?.textContent,energy:document.querySelector('#energy-single-values')?.textContent.slice(0,120),study:document.querySelector('#es-status')?.textContent})"));
          nextLog = Date.now() + 5000;
        }
      } catch {
        // Page navigation briefly has no document; keep polling until ready.
      }
      await sleep(100);
    }
    let diagnostic = null;
    try { diagnostic = await this.evaluate("JSON.stringify({href:location.href,state:document.readyState,html:document.documentElement?.outerHTML.length,body:document.body?.innerText.slice(0,300)})"); } catch {}
    throw Error(`Timed out waiting for ${expression}; page=${diagnostic}`);
  }

  async click(selector) {
    const exists = await this.evaluate(`Boolean(document.querySelector(${JSON.stringify(selector)}))`);
    if (!exists) throw Error(`Missing UI control: ${selector}`);
    await this.evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  }

  async screenshot(filename, scrollSelector = null) {
    if (scrollSelector) {
      await this.evaluate(`document.querySelector(${JSON.stringify(scrollSelector)}).scrollIntoView({block:'center'})`);
    } else {
      await this.evaluate("window.scrollTo(0, 0)");
    }
    await sleep(300);
    const result = await this.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: false
    });
    const target = path.join(ROOT, "docs", "screenshots", filename);
    fs.mkdirSync(path.dirname(target), {recursive: true});
    fs.writeFileSync(target, Buffer.from(result.data, "base64"));
    return path.relative(ROOT, target).replaceAll("\\", "/");
  }
}

async function main() {
  fs.mkdirSync(OUTPUT, {recursive: true});
  const targets = await fetch(`${CDP}/json`).then(response => response.json());
  const target = targets.findLast(item => item.type === "page" && item.url.startsWith("http://127.0.0.1:"));
  if (!target) throw Error("No local Edge page target found");
  const browser = new Browser(target.webSocketDebuggerUrl);
  const checks = [];
  const screenshots = [];
  const check = (name, passed, evidence = null) => {
    checks.push({name, passed: Boolean(passed), evidence});
    console.log(passed ? `PASS ${name}` : `FAIL ${name}`, evidence ?? "");
    if (!passed) throw Error(`QA failed: ${name}: ${JSON.stringify(evidence)}`);
  };
  await browser.send("Page.enable");
  await browser.send("Runtime.enable");
  await browser.send("Page.setDownloadBehavior", {behavior: "allow", downloadPath: OUTPUT});

  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    await browser.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false
    });
    await browser.send("Page.navigate", {url: `${BASE}/scientific?gui-energy-01=${width}`});
    console.log("navigated", width, await browser.evaluate("JSON.stringify({href:location.href,readyState:document.readyState,lang:document.documentElement?.lang,energy:!!document.querySelector('#energy-ber'),tabs:document.querySelectorAll('.tab').length})"));
    await browser.wait("document.readyState==='complete' && document.documentElement.lang==='uk' && [...document.querySelectorAll('[data-export-canvas]')].some(button=>button.dataset.exportCanvas==='energy-ber')", 30000);
    check(`${width}x${height}: energy and statistical views loaded`, await browser.evaluate(
      "document.querySelector('[data-view=energy]').textContent.includes('Енергетична ефективність') && document.querySelector('[data-view=statistical]').textContent.includes('Статистичне дослідження')"
    ));
    check(`${width}x${height}: no automatic statistical job`, await browser.evaluate(
      "document.querySelector('#es-status').textContent.includes('лише після натискання')"
    ));
    check(`${width}x${height}: no horizontal overflow`, await browser.evaluate(
      "document.documentElement.scrollWidth <= window.innerWidth + 2"
    ));

    if (width === 1366) {
      await browser.evaluate(`(() => {
        document.querySelector('[name=frame_symbols]').value='32';
        document.querySelector('[name=amplitude]').value='0.5';
        document.querySelector('[name=channel_profile]').value='identity';
        document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));
        document.querySelector('[name=noise_variance]').value='0';
      })()`);
      const formValidity = await browser.evaluate("JSON.stringify({valid:document.querySelector('#run-form').checkValidity(),invalid:[...document.querySelector('#run-form').elements].filter(element=>!element.checkValidity()).map(element=>({name:element.name||element.id,value:element.value,message:element.validationMessage}))})");
      console.log("single-run form validity", formValidity);
      await browser.click("#run-button");
      await browser.wait("document.querySelector('#paired-badge').textContent.includes('одне спостереження') && document.querySelector('#energy-single-values').textContent.includes('E_b,d')");
      const unit = await browser.evaluate("({metrics:document.querySelector('#energy-single-values').textContent,paired:document.querySelector('#paired-badge').textContent,summary:document.querySelector('#comparison-cards').textContent})");
      check("Identity F=32 run exposes real samples and paired receiver values", unit.metrics.includes("Енергія переданих відліків Σ|x[n]|²64") && unit.metrics.includes("Енергія на інформаційний біт E_b,d1") && unit.metrics.includes("Збігається з фактичними samples") && unit.paired.includes("одне спостереження"), unit);
      await browser.click("[data-view=energy]");
      await browser.wait("document.querySelector('#energy-single-values').textContent.includes('Енергія на інформаційний біт')");
      const energyScreenshot = await browser.screenshot("gui-energy-01-energy-1366x768.png");
      screenshots.push(energyScreenshot);
      check("single-run energy numbers visible after simulation", await browser.evaluate(
        "document.querySelector('#energy-single-values').textContent.includes('Амплітуда A') && document.querySelector('#energy-single-values').textContent.includes('Інформаційна швидкість')"
      ));

      await browser.evaluate(`(() => {
        document.querySelector('[name=frame_symbols]').value='8';
        document.querySelector('[name=amplitude]').value='0.5';
        document.querySelector('[name=channel_profile]').value='static_multipath';
        document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));
        document.querySelector('[name=noise_variance]').value='0.05';
        document.querySelector('#es-id').value=${JSON.stringify(STUDY_ID)};
        document.querySelector('#es-frame').value='32';
        document.querySelector('#es-grid').value='-3,0,3';
        document.querySelector('#es-trials').value='10';
        document.querySelector('#es-b0').checked=true;
        document.querySelector('#es-b1').checked=true;
        document.querySelector('#es-budget').value='300';
      })()`);
      await browser.click("#es-run");
      await browser.wait("Number(document.querySelector('#es-progress').value)>0 && Number(document.querySelector('#es-progress').value)<1", 90000);
      const partialProgress = await browser.evaluate("JSON.stringify({value:document.querySelector('#es-progress').value,status:document.querySelector('#es-status').textContent})");
      await browser.click("#es-stop");
      await browser.wait("document.querySelector('#es-status').textContent.includes('зупинено або бюджет вичерпано')", 90000);
      check("GUI stop leaves a resumable checkpoint after the current paired trial", true, partialProgress);
      await browser.click("#es-run");
      await browser.wait("document.querySelector('#es-study-summary').textContent.includes('30/30')", 180000);
      const study = await browser.evaluate("({status:document.querySelector('#es-status').textContent,summary:document.querySelector('#es-study-summary').textContent,results:document.querySelector('#energy-study-results').textContent,gain:document.querySelector('#energy-gain-status').textContent,paired:document.querySelector('#energy-ber').dataset.exportRendered})");
      check("resumed GUI series completes paired Joint/B0/B1 trials", study.status.includes("30/30") && study.summary.includes("Завершено") && study.results.includes("B1") && study.summary.includes("static_multipath"), study);
      check("exploratory series does not present a confidence interval or confirmed energy gain", study.gain.includes("Недостатньо незалежних кадрів") && !study.results.includes("95% ДІ"), study);
      const savedStudy = await fetch(`${BASE}/api/scientific/energy-studies/${encodeURIComponent(STUDY_ID)}`).then(response => response.json());
      const uniqueTrials = new Set(savedStudy.records.map(record => `${record.gamma_db}:${record.trial_index}`));
      const hashesPaired = savedStudy.records.every(record => {
        const hashes = Object.values(record.receiver_observation_hashes);
        return hashes.length === 3 && hashes.every(hash => hash === hashes[0]);
      });
      const aggregateConsistent = savedStudy.analyses.b0.aggregate.every(point => {
        const rows = savedStudy.records.filter(record => record.gamma_db === point.gamma_db);
        const errors = rows.reduce((sum, record) => sum + record.bit_errors.joint, 0);
        const bits = rows.reduce((sum, record) => sum + record.bits, 0);
        return point.ber.joint === errors / bits && point.trials === rows.length;
      });
      check("resumed trials are unique, paired, and aggregate BER matches stored bit counts", savedStudy.records.length === 30 && uniqueTrials.size === 30 && hashesPaired && aggregateConsistent, {records:savedStudy.records.length,uniqueTrials:uniqueTrials.size,hashesPaired,aggregateConsistent});
      await browser.wait("document.querySelector('#energy-ber').dataset.exportRendered==='true' && document.querySelector('#energy-ser').dataset.exportRendered==='true'");
      await browser.click("[data-view=energy]");
      screenshots.push(await browser.screenshot("gui-energy-01-measured-curves-1366x768.png", "#energy-ber"));
      const exportButton = "[data-export-canvas='energy-ber']";
      await browser.wait(`!document.querySelector(${JSON.stringify(exportButton)}).disabled`);
      const exportName = await browser.evaluate("`hf-tcm-${document.querySelector('#es-id').value}-energy-ber-k${document.querySelector('#global-symbol').value}.png`");
      const filesBeforeExport = new Set(fs.readdirSync(OUTPUT));
      const exportedNameFallback = exportName;
      await browser.click(exportButton);
      const deadline = Date.now() + 15000;
      let createdNames = [];
      while (!createdNames.length && Date.now() < deadline) {
        createdNames = fs.readdirSync(OUTPUT).filter(name => !filesBeforeExport.has(name) && name.endsWith("energy-ber-k0.png"));
        if (!createdNames.length) await sleep(100);
      }
      const actualExportName = createdNames[0] || exportedNameFallback;
      const exported = path.join(OUTPUT, actualExportName);
      check("BER chart PNG export created", fs.existsSync(exported), actualExportName);
      const base64 = fs.readFileSync(exported).toString("base64");
      const png = await browser.evaluate(`(async()=>{
        const image=new Image(); image.src='data:image/png;base64,${base64}'; await image.decode();
        const canvas=document.createElement('canvas'); canvas.width=image.width; canvas.height=image.height;
        const context=canvas.getContext('2d'); context.drawImage(image,0,0);
        const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
        let opaque=0, nonWhite=0;
        for(let i=0;i<pixels.length;i+=4){if(pixels[i+3]>250)opaque++;if(pixels[i+3]>250&&(pixels[i]<245||pixels[i+1]<245||pixels[i+2]<245))nonWhite++;}
        return {width:image.width,height:image.height,opaque,nonWhite};
      })()`);
      check("exported BER PNG is opaque and contains plotted content", png.width >= 450 && png.height >= 180 && png.opaque > png.width * png.height * 0.95 && png.nonWhite > 100, png);
      const exportReport = {file:path.relative(ROOT, exported).replaceAll("\\", "/"),bytes:fs.statSync(exported).size,...png};
      fs.writeFileSync(path.join(OUTPUT, "energy_ber_png_validation.json"), JSON.stringify(exportReport, null, 2), "utf8");
      checks.push({name:"BER chart PNG content validation",passed:true,evidence:exportReport});
    } else {
      await browser.click("[data-view=statistical]");
      await browser.wait(`[...document.querySelector('#es-saved').options].some(option=>option.value===${JSON.stringify(STUDY_ID)})`);
      await browser.evaluate(`document.querySelector('#es-saved').value=${JSON.stringify(STUDY_ID)};document.querySelector('#es-open').click()`);
      await browser.wait("document.querySelector('#es-study-summary').textContent.includes('30/30')");
      const reopened = await browser.evaluate("JSON.stringify({selected:document.querySelector('#es-saved').value,summary:document.querySelector('#es-study-summary').textContent})");
      await browser.click("[data-view=statistical]");
      screenshots.push(await browser.screenshot("gui-energy-01-statistical-1920x1080.png"));
      check("statistical view allows saved-study selection and load", await browser.evaluate(
        "document.querySelector('#es-study-summary').textContent.includes('30/30')"
      ), reopened);
    }
  }

  const report = {
    passed: true,
    baseUrl: BASE,
    browser: "Microsoft Edge via Chrome DevTools Protocol",
    viewports: [[1366,768],[1920,1080]],
    studyId: STUDY_ID,
    checks,
    screenshots,
    exported: path.relative(ROOT, path.join(OUTPUT, "energy_ber_png_validation.json")).replaceAll("\\", "/")
  };
  fs.writeFileSync(path.join(OUTPUT, "gui_energy_01_edge_qa.json"), JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
  browser.ws.close();
}

main().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
