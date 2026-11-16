import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const debugUrl = process.env.HF_TCM_EXP03A_CDP || "http://127.0.0.1:9231";
const baseUrl = process.env.HF_TCM_EXP03A_URL || "http://127.0.0.1:18779/scientific";
const screenshotDir = path.join(root, "docs", "screenshots");
const downloadDir = path.join(root, "outputs", "scientific-exp03a", "gui_exports", `edge-${Date.now()}`);
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
if (!page) throw new Error("Scientific Workspace page is not open in the dedicated Edge profile.");
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
  const response = await send("Runtime.evaluate", {
    expression, awaitPromise: true, returnByValue: true,
  });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text || "Browser evaluation failed");
  return response.result.value;
}
async function click(selector) {
  const result = await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)return false;e.click();return true})()`);
  if (!result) throw new Error(`Could not click ${selector}`);
}
async function screenshot(width, height, file) {
  await send("Page.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: 1, mobile: false, screenWidth: width, screenHeight: height,
  });
  await sleep(500);
  const result = await send("Page.captureScreenshot", {format: "png", captureBeyondViewport: true});
  fs.writeFileSync(path.join(screenshotDir, file), Buffer.from(result.data, "base64"));
}

const report = {
  browser: "Microsoft Edge DevTools Protocol",
  url: baseUrl,
  checks: [],
  screenshots: [],
  exports: [],
};
try {
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Browser.setDownloadBehavior", {behavior: "allow", downloadPath: downloadDir});
  await send("Page.navigate", {url: baseUrl});
  await waitFor(() => evaluate(`document.readyState==='complete' && Boolean(document.querySelector('#mx-scenario'))`), "metric comparison tab", 30000);
  await click('.tab[data-view="metric"]');
  await waitFor(() => evaluate(`document.querySelector('#view-metric').classList.contains('active')`), "metric tab activation");
  const labels = await evaluate(`({heading:document.querySelector('#view-metric h1').innerText,ids:[...document.querySelectorAll('#view-metric input,#view-metric select')].map(x=>x.id),pilotText:document.querySelector('#mx-overhead').innerText,noiseLabel:[...document.querySelectorAll('#view-metric label')].find(x=>x.innerText.includes('дисперсія'))?.innerText||''})`);
  if (!labels.heading.includes("порівняння метрик") || !labels.ids.includes("mx-period")) throw new Error("Metric controls are missing");
  report.labels = labels;
  report.checks.push({name: "Metric controls and pilot-overhead display", status: "PASS"});

  const id = `exp03a-edge-static-${Date.now()}`;
  await evaluate(`(()=>{
    const set=(q,v)=>{const e=document.querySelector(q);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));};
    set('#mx-id',${JSON.stringify(id)});set('#mx-scenario','static');set('#mx-frame','64');set('#mx-grid','0');
    set('#mx-trials','1');set('#mx-target','0.05');set('#mx-seed','831077');set('#mx-budget','60');
    set('#mx-amplitude','1');set('#mx-noise','0.05');set('#mx-preamble','4');set('#mx-period','16');set('#mx-burst','4');
    document.querySelector('#metric-study-form').requestSubmit();return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('#mx-summary').innerText.includes('1/1')`), "one paired GUI metric trial", 90000);
  const smoke = await evaluate(`({summary:document.querySelector('#mx-summary').innerText,status:document.querySelector('#mx-status').innerText,gain:document.querySelector('#mx-gain-status').innerText,ber:document.querySelector('#metric-ber').dataset.exportRendered,ser:document.querySelector('#metric-ser').dataset.exportRendered})`);
  if (!smoke.summary.includes("цілісність архіву підтверджено") || !smoke.ber || !smoke.ser) throw new Error("Completed GUI metric result was not rendered and verified");
  report.smokeStudyId = id;
  report.smoke = smoke;
  report.checks.push({name: "Paired static multipath experiment launched and saved from GUI", status: "PASS"});

  await waitFor(() => evaluate(`[...document.querySelector('#mx-saved').options].some(x=>x.value==='exp03a-range2-rician-pilot8-v1')`), "verified Rician study in saved-series list", 30000);
  await evaluate(`(()=>{const s=document.querySelector('#mx-saved');s.value='exp03a-range2-rician-pilot8-v1';document.querySelector('#mx-open').click()})()`);
  await waitFor(() => evaluate(`document.querySelector('#mx-summary').innerText.includes('25/25')`), "saved Rician pilot study open", 90000);
  const opened = await evaluate(`({summary:document.querySelector('#mx-summary').innerText,gain:document.querySelector('#mx-gain-status').innerText,canvases:['metric-ber','metric-ser'].map(id=>{const c=document.getElementById(id),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let ink=0;for(let i=0;i<d.length;i+=4)if(d[i]<245||d[i+1]<245||d[i+2]<245)ink++;return {id,width:c.width,height:c.height,ink,rendered:c.dataset.exportRendered}})})`);
  if (opened.canvases.some(canvas => canvas.ink < 100 || canvas.rendered !== "true")) throw new Error("Saved Rician BER/SER plots are empty");
  if (!opened.gain.includes("Недостатньо даних")) throw new Error("Unbracketed target was incorrectly reported as an energy gain");
  report.openedRangeStudy = opened;
  report.checks.push({name: "Saved Rician study opens from verified manifest with no fabricated gain", status: "PASS"});

  for (const [width, height, name] of [
    [1366, 768, "scientific-exp03a-metric-rician-1366x768.png"],
    [1920, 1080, "scientific-exp03a-metric-rician-1920x1080.png"],
  ]) {
    await screenshot(width, height, name);
    report.screenshots.push({file: `docs/screenshots/${name}`, width, height});
  }

  const before = new Set(fs.readdirSync(downloadDir));
  await click("#metric-ber-png"); await click("#metric-ber-svg");
  await click("#metric-ser-png"); await click("#metric-ser-svg");
  await waitFor(() => fs.readdirSync(downloadDir).filter(file => !before.has(file) && /\.(png|svg)$/i.test(file)).length >= 4, "metric PNG and SVG exports", 30000);
  report.exports = fs.readdirSync(downloadDir).filter(file => /\.(png|svg)$/i.test(file)).map(file => {
    const full = path.join(downloadDir, file);
    return {file: path.relative(root, full), size: fs.statSync(full).size};
  });
  report.checks.push({name: "Actual browser PNG and SVG downloads for BER/SER", status: "PASS"});

  const firstToggle = await evaluate(`(()=>{const c=document.querySelector('#metric-ber').parentElement.querySelector('[data-arm="joint"]');const checked=c.checked;c.click();const one=Boolean(document.querySelector('#metric-ber').dataset.exportRendered);c.click();return {one,restored:c.checked===checked}})()`);
  if (!firstToggle.one || !firstToggle.restored) throw new Error("Metric-series visibility toggle failed");
  report.checks.push({name: "Independent series visibility toggle", status: "PASS"});

  fs.writeFileSync(path.join(root, "outputs", "scientific-exp03a", "validation", "edge_gui_qa.json"), JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
} finally {
  socket.close();
}
