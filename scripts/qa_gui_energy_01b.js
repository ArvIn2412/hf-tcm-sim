import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const debugUrl = process.env.HF_TCM_EDGE_CDP || "http://127.0.0.1:9224";
const screenshotDir = path.join(root, "docs", "screenshots");
const downloadDir = path.join(root, "tmp", "gui-energy-01b-downloads", new Date().toISOString().replace(/[:.]/g, "-"));
fs.mkdirSync(screenshotDir, {recursive: true});
fs.mkdirSync(downloadDir, {recursive: true});

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(predicate, label, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await predicate();
    if (result) return result;
    await sleep(150);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

const pages = await (await fetch(`${debugUrl}/json/list`)).json();
const page = pages.find(item => item.type === "page" && item.url.includes("/scientific"));
if (!page) throw new Error("Open Scientific Workspace in Edge or launch its local server before this QA script.");
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});
let nextId = 1;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  const handler = pending.get(message.id);
  if (!handler) return;
  pending.delete(message.id);
  if (message.error) handler.reject(new Error(message.error.message));
  else handler.resolve(message.result);
});
function send(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {expression, awaitPromise: true, returnByValue: true});
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text || "Browser evaluation failed");
  return response.result.value;
}
async function click(selector) {
  const clicked = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return false;e.click();return true})()`);
  if (!clicked) throw new Error(`Could not click ${selector}`);
}
async function screenshot(width, height, file) {
  await send("Page.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 1, mobile: false, screenWidth: width, screenHeight: height});
  await sleep(600);
  const {data} = await send("Page.captureScreenshot", {format: "png", captureBeyondViewport: true});
  fs.writeFileSync(path.join(screenshotDir, file), Buffer.from(data, "base64"));
}

const report = {browser: "Microsoft Edge via DevTools Protocol", viewport: [], exportDirectory: path.relative(root, downloadDir), checks: []};
try {
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Browser.setDownloadBehavior", {behavior: "allow", downloadPath: downloadDir});
  await send("Page.navigate", {url: "http://127.0.0.1:18771/scientific"});
  await waitFor(() => evaluate(`document.readyState==='complete' && Boolean(document.querySelector('#es-auto-after-run'))`), "updated Scientific Workspace", 30000);

  const singleRun = await evaluate(`(async()=>{
    const set=(q,v)=>{const e=document.querySelector(q);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    const auto=document.querySelector('#es-auto-after-run');auto.checked=false;auto.dispatchEvent(new Event('change',{bubbles:true}));
    set('[name=frame_symbols]','32');set('[name=channel_profile]','identity');set('[name=noise_variance]','0');
    document.querySelector('#run-button').click();return true;
  })()`);
  if (!singleRun) throw new Error("Single-run form did not submit");
  await waitFor(() => evaluate(`document.querySelector('#sync-status').textContent.includes('Моделювання завершено')`), "Identity single run", 90000);
  const singleMetrics = await evaluate(`document.querySelector('#energy-single-values').innerText`);
  if (!singleMetrics.includes("Енергія на інформаційний біт") || !singleMetrics.includes("BER / SER інформаційних пар")) {
    throw new Error("Single-run energy or BER/SER values are missing");
  }
  report.checks.push({name: "Identity single run and immediate energy/BER/SER", status: "PASS"});

  await click('.tab[data-view="energy"]');
  await click("#open-historical-energy");
  await waitFor(() => evaluate(`document.querySelector('#es-study-summary').innerText.includes('140/140')`), "historical gain and CI", 90000);
  const historical = await evaluate(`({summary:document.querySelector('#es-study-summary').innerText,results:document.querySelector('#energy-study-results').innerText,status:document.querySelector('#energy-gain-status').innerText,charts:['energy-ber','energy-ser','energy-gain','energy-efficiency'].map(id=>{const c=document.getElementById(id);let data=c.getContext('2d').getImageData(0,0,c.width,c.height).data,visible=0;for(let i=0;i<data.length;i+=4)if(data[i]<245||data[i+1]<245||data[i+2]<245)visible++;return {id,width:c.width,height:c.height,visible,yMin:c.dataset.yMin,yMax:c.dataset.yMax,rendered:c.dataset.exportRendered}}),berLegend:[...document.querySelectorAll('[data-series-for="energy-ber"] input')].length})`);
  if (!historical.results.includes("6,7678") || !historical.results.includes("2,9641") || !historical.results.includes("95% ДІ")) {
    throw new Error("Historical gain/CI values do not match the verified record analysis");
  }
  if (historical.charts.some(chart => chart.visible < 100 || chart.rendered !== "true")) throw new Error("An energy chart is empty");
  if (historical.charts.slice(0, 2).some(chart => chart.yMin !== "0" || chart.yMax !== "1")) throw new Error("BER/SER axis is not fixed to [0,1]");
  if (historical.berLegend !== 3) throw new Error("Expected three receiver series controls");
  report.historical = historical;
  report.checks.push({name: "Read-only SCIENTIFIC-EXP-01 load; paired gain/CI and [0,1] axes", status: "PASS"});

  await evaluate(`(()=>{const box=document.querySelector('[data-series-for="energy-ber"] input');box.click();box.click()})()`);
  report.checks.push({name: "Energy curve series toggle", status: "PASS"});

  await screenshot(1366, 768, "gui-energy-01b-energy-1366x768.png");
  report.viewport.push("1366x768");
  await screenshot(1920, 1080, "gui-energy-01b-energy-1920x1080.png");
  report.viewport.push("1920x1080");

  for (const id of ["energy-ber", "energy-ser", "energy-gain", "energy-efficiency"]) {
    await click(`[data-export-canvas="${id}"]`);
    await click(`[data-export-svg="${id}"]`);
  }
  await waitFor(() => fs.readdirSync(downloadDir).filter(file => /\.(png|svg)$/i.test(file)).length >= 8, "energy PNG/SVG downloads", 30000);
  report.checks.push({name: "PNG and SVG export for all four energy plots", status: "PASS"});

  await click('.tab[data-view="statistical"]');
  const studyId = `gui-energy-01b-edge-${Date.now()}`;
  await evaluate(`(()=>{
    const set=(q,v)=>{const e=document.querySelector(q);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    set('[name=frame_symbols]','256');set('[name=channel_profile]','awgn');set('[name=noise_variance]','0.1');
    set('#es-id',${JSON.stringify(studyId)});set('#es-frame','256');set('#es-sweep','amplitude');set('#es-grid','0, 3');set('#es-target','0.05');set('#es-trials','4');set('#es-budget','180');set('#es-bootstrap','100');
    document.querySelector('#es-b0').checked=true;document.querySelector('#es-b1').checked=false;
    document.querySelector('#es-run').click();return true;
  })()`);
  await waitFor(() => evaluate(`!document.querySelector('#es-stop').disabled`), "Monte Carlo worker launch", 30000);
  await sleep(120);
  const stopWasEnabled = await evaluate(`!document.querySelector('#es-stop').disabled`);
  if (stopWasEnabled) {
    await click("#es-stop");
    await waitFor(() => evaluate(`document.querySelector('#es-run').disabled===false && document.querySelector('#es-status').innerText.includes('зупинено')`), "Monte Carlo stop checkpoint", 90000);
  }
  const stoppedStatus = await evaluate(`document.querySelector('#es-status').innerText`);
  report.checks.push({name: "Monte Carlo launch and stop control", status: "PASS", detail: stoppedStatus});
  await click("#es-run");
  await waitFor(() => evaluate(`document.querySelector('#es-study-summary').innerText.includes('8/8')`), "Monte Carlo resume and completion", 180000);
  const resumed = await evaluate(`(async()=>{const r=await fetch('/api/scientific/energy-studies/'+encodeURIComponent(${JSON.stringify(studyId)}));const x=await r.json();return {count:x.records.length,planned:x.planned_trials,unique:new Set(x.records.map(v=>v.point_index+':'+v.trial_index)).size,paired:x.records.every(v=>new Set(Object.values(v.receiver_observation_hashes)).size===1),status:x.status}})()`);
  if (resumed.count !== 8 || resumed.unique !== 8 || !resumed.paired || resumed.status !== "completed") throw new Error("Monte Carlo resume duplicated trials or lost paired observations");
  resumed.experimentId = studyId;
  report.monteCarlo = resumed;
  report.checks.push({name: "Monte Carlo stop/resume without duplicate trials", status: "PASS"});
  await click('.tab[data-view="statistical"]');
  await evaluate(`(()=>{const s=document.querySelector('#es-saved');s.value=${JSON.stringify(studyId)};s.dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#es-open').click()})()`);
  await waitFor(() => evaluate(`document.querySelector('#es-study-summary').innerText.includes('8/8')`), "saved series reopen", 30000);
  report.checks.push({name: "Save/load of GUI statistical series", status: "PASS"});

  const autoStudyId = `gui-energy-01b-auto-${Date.now()}`;
  await click('.tab[data-view="statistical"]');
  await evaluate(`(()=>{
    const set=(q,v)=>{const e=document.querySelector(q);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    const auto=document.querySelector('#es-auto-after-run');if(!auto.checked)auto.click();
    set('#es-id',${JSON.stringify(autoStudyId)});set('#es-frame','8');set('#es-grid','0');set('#es-trials','1');set('#es-budget','45');set('#es-bootstrap','100');
    document.querySelector('#es-b0').checked=true;document.querySelector('#es-b1').checked=false;
  })()`);
  await click('.tab[data-view="parameters"]');
  await evaluate(`(()=>{
    const set=(q,v)=>{const e=document.querySelector(q);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    set('[name=frame_symbols]','8');set('[name=channel_profile]','awgn');set('[name=noise_variance]','0.1');
    document.querySelector('#run-button').click();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('#es-study-summary').innerText.includes('1/1')`), "opt-in bounded auto-study after a single run", 120000);
  await evaluate(`(()=>{const e=document.querySelector('#es-auto-after-run');if(e.checked)e.click();localStorage.setItem('hf-tcm-auto-energy-after-run','false')})()`);
  report.autoEnergyExperimentId = autoStudyId;
  report.checks.push({name: "Opt-in bounded energy series after single run", status: "PASS"});

  fs.writeFileSync(path.join(root, "tmp", "gui-energy-01b-edge-qa.json"), JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
} finally {
  socket.close();
}
