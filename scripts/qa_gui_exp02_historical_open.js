import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const debugUrl = process.env.HF_TCM_EDGE_CDP || "http://127.0.0.1:9224";
const baseUrl = process.env.HF_TCM_STUDIO_URL || "http://127.0.0.1:18770";
const screenshotDir = path.join(root, "docs", "screenshots");
fs.mkdirSync(screenshotDir, {recursive: true});

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(predicate, label, timeoutMs = 30000) {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    const result = await predicate();
    if (result) return result;
    await sleep(150);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

const pages = await (await fetch(`${debugUrl}/json/list`)).json();
const page = pages.find(item => item.type === "page" && item.url.includes("/scientific"));
if (!page) throw new Error("Scientific Workspace is not open in Edge");
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
async function screenshot(width, height, file, fullPage = false) {
  await send("Page.setDeviceMetricsOverride", {width, height, deviceScaleFactor: 1, mobile: false, screenWidth: width, screenHeight: height});
  await sleep(500);
  const {data} = await send("Page.captureScreenshot", {format: "png", captureBeyondViewport: fullPage});
  fs.writeFileSync(path.join(screenshotDir, file), Buffer.from(data, "base64"));
}

const report = {browser: "Microsoft Edge via DevTools Protocol", checks: []};
try {
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Page.navigate", {url: `${baseUrl}/scientific`});
  await waitFor(() => evaluate("document.readyState==='complete' && Boolean(document.querySelector('#es-saved'))"), "Scientific Workspace", 30000);
  await evaluate(`(()=>{const tab=document.querySelector('.tab[data-view="statistical"]');if(!tab)throw new Error('saved studies tab missing');tab.click()})()`);
  await waitFor(() => evaluate("[...document.querySelector('#es-saved').options].some(option=>option.value==='historical:exp01b-static')"), "EXP-01B saved-study option", 30000);
  await evaluate(`(()=>{
    const select=document.querySelector('#es-saved');
    select.value='historical:exp01b-static';select.dispatchEvent(new Event('change',{bubbles:true}));
    document.querySelector('#es-open').click();
  })()`);
  await waitFor(() => evaluate("document.querySelector('#es-status').innerText.includes('Відкрито') || document.querySelector('#es-study-summary').innerText.includes('не відкрито')"), "EXP-01B saved-study response", 60000);
  const view = await evaluate(`(()=>{
    const canvases=['energy-ber','energy-ser','energy-gain','energy-efficiency'].map(id=>{const c=document.getElementById(id);const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let ink=0;for(let i=0;i<data.length;i+=4)if(data[i]<245||data[i+1]<245||data[i+2]<245)ink++;return {id,width:c.width,height:c.height,ink,rendered:c.dataset.exportRendered}});
    return {selection:document.querySelector('#es-saved').value,summary:document.querySelector('#es-study-summary').innerText,results:document.querySelector('#energy-study-results').innerText,gain:document.querySelector('#energy-gain-status').innerText,status:document.querySelector('#es-status').innerText,canvases};
  })()`);
  console.log("EXP-01B browser view", JSON.stringify(view));
  if (view.selection !== "historical:exp01b-static") throw new Error("saved study selection changed unexpectedly");
  if (!view.summary.includes("1 160") && !view.summary.includes("1160")) throw new Error("GUI does not show the EXP-01B static frame count");
  if (!view.results.includes("5,78 дБ") && !view.results.includes("5.78 dB")) throw new Error("Joint/B0 gain is missing from GUI");
  if (!view.results.includes("2,4561") && !view.results.includes("2.4561")) throw new Error("Joint/B1 gain is missing from GUI");
  if (!view.results.includes("95% ДІ") || !view.results.includes("4808/5000") || !view.results.includes("4946/5000")) throw new Error("validated confidence intervals are missing from GUI");
  if (!view.summary.includes("Статичний багатопроменевий канал") || view.summary.includes("Райсівський")) throw new Error("EXP-01B static data were mixed with another scenario");
  if (view.canvases.some(item=>item.ink<100||item.rendered!=="true")) throw new Error("an EXP-01B GUI chart is empty");
  report.checks.push({name:"Saved study list opens provenance-verified EXP-01B without rerunning trials",status:"PASS",completedStaticFrames:1160,sourceTotalFrames:2160});
  report.checks.push({name:"BER/SER, required-energy gain and confidence intervals render from stored results",status:"PASS",canvases:view.canvases});
  report.summary=view.summary;
  report.results=view.results;
  await screenshot(1366,768,"scientific-exp02-exp01b-energy-overview-1366x768.png");
  await evaluate("(()=>{const target=document.querySelector('#energy-study-results');window.scrollTo(0,target.getBoundingClientRect().top+window.scrollY-160)})()");
  await screenshot(1366,768,"scientific-exp02-exp01b-energy-results-1366x768.png");
  await screenshot(1920,1080,"scientific-exp02-exp01b-energy-results-1920x1080.png");
  await screenshot(1366,768,"scientific-exp02-exp01b-energy-fullpage.png",true);
  report.screenshots=[
    "docs/screenshots/scientific-exp02-exp01b-energy-overview-1366x768.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-results-1366x768.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-results-1920x1080.png",
    "docs/screenshots/scientific-exp02-exp01b-energy-fullpage.png"
  ];
  fs.mkdirSync(path.join(root,"outputs","scientific_exp_02"),{recursive:true});
  fs.writeFileSync(path.join(root,"outputs","scientific_exp_02","gui_acceptance.json"),JSON.stringify(report,null,2),"utf8");
  console.log(JSON.stringify(report,null,2));
} finally {
  socket.close();
}
