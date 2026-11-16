"use strict";
const fs = require("node:fs");
const path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const BASE = process.env.M11J_URL || "http://127.0.0.1:18768";
const CDP = process.env.M11J_CDP || "http://127.0.0.1:9224";
const sleep = ms => new Promise(r => setTimeout(r, ms));
class Browser {
  constructor(url) { this.ws = new WebSocket(url); this.id = 0; this.waiters = new Map(); this.ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && this.waiters.has(m.id)) { const w = this.waiters.get(m.id); this.waiters.delete(m.id); m.error ? w.reject(Error(JSON.stringify(m.error))) : w.resolve(m.result); } }; }
  async send(method, params={}) { if (this.ws.readyState !== WebSocket.OPEN) await new Promise((resolve,reject)=>{this.ws.addEventListener("open",resolve,{once:true});this.ws.addEventListener("error",reject,{once:true});}); const id=++this.id; return new Promise((resolve,reject)=>{this.waiters.set(id,{resolve,reject});this.ws.send(JSON.stringify({id,method,params}));}); }
  async eval(expression) { const r=await this.send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true,userGesture:true}); if(r.exceptionDetails) throw Error(JSON.stringify(r.exceptionDetails)); return r.result.value; }
  async until(expression, ms=20000) { const end=Date.now()+ms; while(Date.now()<end){if(await this.eval(expression)) return; await sleep(100);} throw Error(`Timeout: ${expression}`); }
  async click(selector) { await this.eval(`document.querySelector(${JSON.stringify(selector)})?.click()`); }
 async shot(name,label,selector) { if(selector) await this.eval(`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({block:'center'})`);else await this.eval("window.scrollTo(0,0)"); await sleep(180); const r=await this.send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false}); const file=`m11j-${name}-${label}.png`; fs.mkdirSync(path.join(ROOT,"docs","screenshots"),{recursive:true}); fs.writeFileSync(path.join(ROOT,"docs","screenshots",file),Buffer.from(r.data,"base64")); return `docs/screenshots/${file}`; }
}
async function main(){
 const targets=await fetch(`${CDP}/json`).then(r=>r.json()),target=targets.find(x=>x.type==="page"); if(!target) throw Error("No Edge page target");
 const b=new Browser(target.webSocketDebuggerUrl),report={viewports:[],screenshots:[],checks:[]}; const check=(name,ok,detail)=>{report.checks.push({name,ok:Boolean(ok),detail});if(!ok)throw Error(`${name}: ${JSON.stringify(detail)}`)};
 for(const [width,height] of [[1366,768],[1920,1080]]){
  const label=`${width}x${height}`;report.viewports.push(label);
  await b.send("Page.enable");await b.send("Runtime.enable");await b.send("Network.enable");await b.send("Network.setCacheDisabled",{cacheDisabled:true});await b.send("Emulation.setDeviceMetricsOverride",{width,height,deviceScaleFactor:1,mobile:false});await b.send("Page.navigate",{url:`${BASE}/`});
  await b.until("window.HFTCMMinimalistState && app.metadata && document.querySelectorAll('.nav-item').length===6");
  check(`${label}: initial GET does not execute receiver`,await b.eval("app.trace===null"));
  check(`${label}: six views and Ukrainian primary nav`,await b.eval("[...document.querySelectorAll('.nav-item')].map(x=>x.dataset.view).join(',')==='simulation,stages,samples,hidden,decoding,results'"));
  check(`${label}: Simulation is the initial page`,await b.eval("document.body.dataset.uxView==='simulation'"));
  await b.click("[data-m11j-step='1']");check(`${label}: Next navigates without running a receiver`,await b.eval("document.body.dataset.uxView==='stages' && app.trace===null"));await b.click("[data-m11j-step='-1']");check(`${label}: Previous returns to Simulation`,await b.eval("document.body.dataset.uxView==='simulation'"));
  await b.click("#view-demo .m11j-page-header [data-help]");check(`${label}: contextual help opens`,await b.eval("document.querySelector('#help-dialog').open"));await b.click("#help-close");
  await b.click("#m11j-projector");check(`${label}: Simulation projector control toggles projector layout`,await b.eval("document.body.classList.contains('projector-mode')"));await b.click("#m11j-projector");
  await b.eval("document.querySelector('#interactive-bits').value='10'.repeat(32);document.querySelector('#interactive-bits').dispatchEvent(new Event('input',{bubbles:true}))");
  await b.click("#run-demo");await b.until("app.trace?.input.symbol_count===32 && !!document.querySelector('#m11j-run-confirmation') && !document.querySelector('#m11j-run-confirmation').hidden");
  check(`${label}: explicit POST commits one actual run`,await b.eval("window.HFTCMMinimalistUIState.activeRunId==='demo-1' && !window.HFTCMMinimalistUIState.stale && app.trace.input.sample_count===256"));
  await b.click("#m11j-view-signal");
  check(`${label}: samples view has frame/window actual chart`,await b.eval("document.body.dataset.uxView==='samples' && !!document.querySelector('#signal-chart') && !!document.querySelector('#m11j-exact-samples')"));
  report.screenshots.push(await b.shot("simulation",label,"#m11j-run-confirmation"));
  await b.click("#signal-to-trellis");check(`${label}: selected signal segment opens the synchronized TCM view`,await b.eval("document.body.dataset.uxView==='hidden' && document.querySelector('#view-trellis').classList.contains('active')"));await b.click("[data-view='samples']");
  await b.click("#signal-window-reset");
  check(`${label}: 20-symbol window is 160 samples in F=32`,await b.eval("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===160"));
  check(`${label}: F=32 window starts cover first/middle/last positions 0..12 symbols`,await b.eval("document.querySelector('#signal-sample-offset').max==='96'"));
  await b.click("#signal-middle");check(`${label}: middle window is synchronized`,await b.eval("window.HFTCMSignalExplorerState.startSample===48 && window.HFTCMSignalExplorerState.endSample===208"));
  await b.click("#signal-last");check(`${label}: last window ends on final sample`,await b.eval("window.HFTCMSignalExplorerState.startSample===96 && window.HFTCMSignalExplorerState.endSample===256"));
  await b.click("#signal-first");await b.eval("document.body.classList.add('projector-mode','projector-sidebar-collapsed')");report.screenshots.push(await b.shot("samples-projector",label,"#signal-chart"));await b.eval("document.body.classList.remove('projector-mode','projector-sidebar-collapsed')");
  await b.click("#signal-zoom-20");
  check(`${label}: 20-sample detail mode`,await b.eval("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===20"));
  check(`${label}: visual window is described separately from Viterbi depth`,await b.eval("document.querySelector('.signal-path-card').textContent.includes('η=20')"));
  await b.click("[data-view='stages']");
  check(`${label}: ten trace-backed stage choices`,await b.eval("document.querySelectorAll('[data-stage-key]').length===10 && document.querySelector('#m11j-stage-graph svg')!==null"));
  report.screenshots.push(await b.shot("signal-stages",label,"#m11j-stage-graph"));
  await b.click("[data-view='hidden']");await b.click("[data-hidden-tab='channel']");
  check(`${label}: channel hidden-state view labels unavailable data honestly`,await b.eval("document.querySelector('#m11j-channel-states').textContent.includes('UNAVAILABLE') && document.querySelector('#m11j-channel-states').textContent.includes('transition probabilities')"));
  report.screenshots.push(await b.shot("hidden-channel-unavailable",label,"#m11j-channel-states"));
  await b.click("[data-view='decoding']");
  for(const tab of ["metrics","estimation","viterbi"]){await b.click(`[data-decode-tab='${tab}']`);check(`${label}: decoding tab ${tab} renders a chart`,await b.eval("document.querySelector('#m11j-decode-view svg')!==null"));}
  report.screenshots.push(await b.shot("decoding-viterbi",label,"#m11j-decode-view"));
  await b.click("[data-view='results']");check(`${label}: current run results and archives are separate`,await b.eval("document.querySelector('#m11j-current-run-values').textContent.includes('BER') && !!document.querySelector('#m11j-archive-focus')"));
  report.screenshots.push(await b.shot("results",label,"#m11j-current-run-values"));
  await b.eval("document.querySelector('#alpha').value=String(Number(document.querySelector('#alpha').value)+0.01);document.querySelector('#alpha').dispatchEvent(new Event('change',{bubbles:true}))");
  const staleState=await b.eval("({trace:app.trace!==null,stale:window.HFTCMMinimalistUIState?.stale,banners:[...document.querySelectorAll('#m11j-stale-banner')].map(x=>({text:x.textContent,hidden:x.hidden})),dataset:document.body.dataset.traceStale})");
  check(`${label}: editing config preserves old trace and marks stale`,staleState.trace&&staleState.stale&&staleState.banners.some(x=>x.text.includes("STALE")),staleState);
  await b.click("[data-view='samples']");await b.eval("document.body.classList.add('projector-mode');document.body.classList.add('projector-sidebar-collapsed')");
  check(`${label}: projector has one large active signal view without overflow`,await b.eval("document.body.classList.contains('projector-mode') && document.documentElement.scrollWidth<=document.documentElement.clientWidth+2 && getComputedStyle(document.querySelector('.signal-main-card')).minHeight==='600px'"));
  await b.eval("document.body.classList.remove('projector-mode','projector-sidebar-collapsed')");
  await b.click("[data-view='simulation']");await b.eval("document.querySelector('#interactive-bits').value='10110010';document.querySelector('#interactive-bits').dispatchEvent(new Event('input',{bubbles:true}))");await b.click("#run-demo");await b.until("app.trace?.input.symbol_count===4 && app.trace.input.sample_count===32 && !document.querySelector('#run-demo').disabled");await b.click("#m11j-view-signal");await b.click("#signal-window-reset");check(`${label}: short frame F<20 clamps to its 32 real samples`,await b.eval("window.HFTCMSignalExplorerState.startSample===0 && window.HFTCMSignalExplorerState.endSample===32"));await b.click("#signal-zoom-20");check(`${label}: short-frame detail remains unpadded and has 20 samples`,await b.eval("window.HFTCMSignalExplorerState.endSample-window.HFTCMSignalExplorerState.startSample===20"));
 }
 console.log(JSON.stringify({...report,passed:true},null,2));b.ws.close();
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1});
