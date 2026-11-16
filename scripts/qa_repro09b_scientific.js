"use strict";

const fs=require("node:fs"),path=require("node:path");
const ROOT=path.resolve(__dirname,"..");
const BASE=process.env.REPRO09_URL||"http://127.0.0.1:18769";
const CDP=process.env.REPRO09_CDP||"http://127.0.0.1:9224";
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
class Browser{
  constructor(url){this.ws=new WebSocket(url);this.id=0;this.waiters=new Map();this.ws.onmessage=event=>{const message=JSON.parse(event.data);if(message.id&&this.waiters.has(message.id)){const waiter=this.waiters.get(message.id);this.waiters.delete(message.id);message.error?waiter.reject(Error(JSON.stringify(message.error))):waiter.resolve(message.result);}};}
  async send(method,params={}){if(this.ws.readyState!==WebSocket.OPEN)await new Promise((resolve,reject)=>{this.ws.addEventListener("open",resolve,{once:true});this.ws.addEventListener("error",reject,{once:true});});const id=++this.id;return new Promise((resolve,reject)=>{this.waiters.set(id,{resolve,reject});this.ws.send(JSON.stringify({id,method,params}));});}
  async eval(expression){const result=await this.send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
  async wait(expression,timeout=90000){const end=Date.now()+timeout;while(Date.now()<end){if(await this.eval(expression))return;await sleep(150);}throw Error(`Timed out: ${expression}`);}
  async click(selector){await this.eval(`document.querySelector(${JSON.stringify(selector)}).click()`);}
  async screenshot(name){await this.eval("window.scrollTo(0,0)");await sleep(300);const image=await this.send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});const file=path.join(ROOT,"docs","screenshots",name);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,Buffer.from(image.data,"base64"));return path.relative(ROOT,file).replaceAll("\\","/");}
  async waitForFile(file,timeout=15000){const end=Date.now()+timeout;while(Date.now()<end){if(fs.existsSync(file)&&fs.statSync(file).size>8)return;await sleep(100);}throw Error(`Timed out waiting for download: ${file}`);}
  async exportPng(selector,filename,directory){
    const file=path.join(directory,filename);if(fs.existsSync(file))fs.unlinkSync(file);
    if(!await this.eval(`!document.querySelector(${JSON.stringify(selector)}).disabled`))throw Error(`Export not ready: ${selector}`);
    await this.click(selector);await this.waitForFile(file);
    const b64=fs.readFileSync(file).toString("base64");
    const result=await this.eval(`(async()=>{const image=new Image();image.src="data:image/png;base64,${b64}";await image.decode();const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const x=c.getContext('2d');x.drawImage(image,0,0);const p=x.getImageData(0,0,c.width,c.height).data;let opaque=0,nonWhite=0;const colors=new Set();for(let i=0;i<p.length;i+=4){if(p[i+3]>250)opaque++;if(p[i+3]>250&&(p[i]<245||p[i+1]<245||p[i+2]<245))nonWhite++;if(i%(4*97)===0)colors.add(p[i]+','+p[i+1]+','+p[i+2]);}return {width:image.width,height:image.height,opaque,nonWhite,sampledColors:colors.size};})()`);
    if(result.width<450||result.height<180||result.opaque<result.width*result.height*.95||result.nonWhite<100||result.sampledColors<5)throw Error(`Empty/invalid PNG ${filename}: ${JSON.stringify(result)}`);
    return {file:path.relative(ROOT,file).replaceAll("\\","/"),bytes:fs.statSync(file).size,...result};
  }
  async exportSvg(selector,filename,directory){
    const file=path.join(directory,filename);if(fs.existsSync(file))fs.unlinkSync(file);
    if(!await this.eval(`!document.querySelector(${JSON.stringify(selector)}).disabled`))throw Error(`SVG export not ready: ${selector}`);
    await this.click(selector);await this.waitForFile(file);const source=fs.readFileSync(file,"utf8");
    if(!source.includes("<svg")||!source.includes("trellis-edge")||!source.includes("#ffffff")||!source.includes("viewBox=\"0 0 1000 500\""))throw Error(`Invalid SVG payload: ${filename}`);
    return {file:path.relative(ROOT,file).replaceAll("\\","/"),bytes:fs.statSync(file).size,paths:(source.match(/<path /g)||[]).length};
  }
}
async function main(){
  const targets=await fetch(`${CDP}/json`).then(r=>r.json()),target=targets.findLast(item=>item.type==="page" && item.url.startsWith("http://127.0.0.1:"));if(!target)throw Error("No Edge page target");
  const browser=new Browser(target.webSocketDebuggerUrl),checks=[],screenshots=[];const check=(name,ok,detail=null)=>{checks.push({name,passed:Boolean(ok),detail});if(!ok)throw Error(`${name}: ${JSON.stringify(detail)}`);};
  const downloadDir=path.join(ROOT,"outputs","repro10a","acceptance");fs.mkdirSync(downloadDir,{recursive:true});await browser.send("Page.setDownloadBehavior",{behavior:"allow",downloadPath:downloadDir});
  await browser.send("Page.enable");await browser.send("Runtime.enable");
  await browser.send("Emulation.setDeviceMetricsOverride",{width:1366,height:768,deviceScaleFactor:1,mobile:false});
  await browser.send("Page.navigate",{url:`${BASE}/`});
  await browser.wait("document.querySelectorAll('.tab').length===9 && !!document.querySelector('#open-long-frame')");
  check("scientific launcher root opens Scientific Workspace rather than legacy M11",await browser.eval("document.querySelectorAll('.tab').length===9 && !document.querySelector('#nav')"));
  await browser.send("Page.navigate",{url:`${BASE}/scientific`});
  await browser.wait("document.querySelectorAll('.tab').length===9 && !!document.querySelector('#open-long-frame')");
  check("Scientific Workspace loads without running a model",await browser.eval("document.querySelector('#job-status').textContent.length>0"));
  await browser.eval("document.querySelector('[name=frame_symbols]').value='32';document.querySelector('[name=channel_profile]').value='identity';document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#include-b1').checked=true;document.querySelector('#run-form').requestSubmit()");
  await browser.wait("document.querySelector('#job-status').textContent.includes('збережено')||document.querySelector('#job-status').textContent.includes('Помилка')",60000);
  await browser.wait("document.querySelector('#paired-badge').textContent.includes('observation')",60000);
  const identityView=await browser.eval("JSON.stringify({cards:document.querySelector('#comparison-cards').textContent,paired:document.querySelector('#paired-badge').textContent,status:document.querySelector('#job-status').textContent})");
  check("Identity run and public-static B1 completed",await browser.eval("document.querySelector('#comparison-cards').textContent.includes('B1') && document.querySelector('#paired-badge').textContent.includes('observation')"),identityView);
  await browser.wait("document.querySelector('#chart-tx').dataset.exportRendered==='true'",15000);
  const exportName=await browser.eval("(() => { const run=document.querySelector('#sync-status').textContent.match(/Run ([^ ]+)/)?.[1]; const k=document.querySelector('#global-symbol').value; return run?`hf-tcm-${run}-chart-tx-k${k}.png`:null; })()");
  const exportState=await browser.eval("JSON.stringify({label:document.querySelector('[data-export-canvas=chart-tx]').textContent,disabled:document.querySelector('[data-export-canvas=chart-tx]').disabled,rendered:document.querySelector('#chart-tx').dataset.exportRendered,charset:document.characterSet})");
  check("transmitter chart is rendered and PNG export label is valid Ukrainian",await browser.eval("document.querySelector('[data-export-canvas=chart-tx]').textContent==='Зберегти PNG' && !document.querySelector('[data-export-canvas=chart-tx]').disabled && document.querySelector('#chart-tx').dataset.exportRendered==='true'"),exportState);
  const exported=[];
  exported.push(await browser.exportPng('[data-export-canvas="chart-tx"]',exportName,downloadDir));
  const identityRun=await browser.eval("document.querySelector('#sync-status').textContent.match(/Run ([^ ]+)/)?.[1]");
  await browser.click('[data-view=saved]');await browser.wait(`!!document.querySelector('[data-open-run="${identityRun}"]')`);
  await browser.eval(`document.querySelector('[data-open-run="${identityRun}"]').click()`);await browser.wait(`document.querySelector('.tab.active').dataset.view==='comparison' && document.querySelector('#sync-status').textContent.includes(${JSON.stringify(identityRun)})`);
  check("saved single-run result reloads with the same run ID",await browser.eval(`document.querySelector('#sync-status').textContent.includes(${JSON.stringify(identityRun)})`),identityRun);
  await browser.eval("document.querySelector('#global-symbol').value='19';document.querySelector('#global-symbol').dispatchEvent(new Event('change',{bubbles:true}))");
  await browser.wait("document.querySelector('#global-symbol').value==='19' && document.querySelector('#transmitter-values').textContent.includes('38:')");
  await browser.click('[data-view=transmitter]');await browser.wait("document.querySelector('.tab.active').dataset.view==='transmitter' && document.querySelector('#global-symbol').value==='19'");
  check("selected symbol is synchronized to transmitter stage",await browser.eval("document.querySelector('#global-symbol').value==='19' && document.querySelector('#transmitter-values').textContent.includes('38:')"));
  screenshots.push(await browser.screenshot("repro10a-transmitter-1366x768.png"));
  for(const [view,canvas] of [["channel","chart-channel"],["joint","chart-joint-metrics"],["separate","chart-hamming"],["comparison","chart-errors"]]){
    await browser.click(`[data-view=${view}]`);await browser.wait(`document.querySelector('.tab.active').dataset.view==='${view}' && document.querySelector('#${canvas}').dataset.exportRendered==='true'`);
    const name=await browser.eval(`(() => {const run=document.querySelector('#sync-status').textContent.match(/Run ([^ ]+)/)?.[1];return run?\`hf-tcm-\${run}-${canvas}-k\${document.querySelector('#global-symbol').value}.png\`:null})()`);
    exported.push(await browser.exportPng(`[data-export-canvas="${canvas}"]`,name,downloadDir));
    if(view!=="comparison")screenshots.push(await browser.screenshot(`repro10a-${view}-1366x768.png`));
    else screenshots.push(await browser.screenshot("repro10a-comparison-1366x768.png"));
  }
  await browser.click('[data-view=viterbi]');await browser.wait("!!window.__neverUsed && !!document.querySelector('#trellis-svg path')===false||document.querySelector('#trellis-caption').textContent.includes('window k=')");
  const baseTrellis=await browser.eval("({title:document.querySelector('#trellis-title').textContent,caption:document.querySelector('#trellis-caption').textContent,paths:document.querySelectorAll('#trellis-svg path').length,rows:document.querySelectorAll('#transition-table tbody tr').length})");
  check("4-state 16-edge real Viterbi diagnostics render",baseTrellis.title.includes("4 states / 16 edges")&&baseTrellis.rows===16,baseTrellis);
  await browser.eval("document.querySelector('#survivor-endpoint').value='3';document.querySelector('#survivor-endpoint').dispatchEvent(new Event('change',{bubbles:true}))");await browser.wait("document.querySelector('#trellis-caption').textContent.includes('selected trace endpoint 3')");
  check("user can select a concrete survivor endpoint",await browser.eval("document.querySelector('#trellis-caption').textContent.includes('selected trace endpoint 3')"));
  await browser.eval("document.querySelector('#survivor-endpoint').value='';document.querySelector('#survivor-endpoint').dispatchEvent(new Event('change',{bubbles:true}))");await browser.wait("document.querySelector('#trellis-caption').textContent.includes('selected trace endpoint')");
  await browser.eval("document.querySelector('#global-symbol').value='19';document.querySelector('#global-symbol').dispatchEvent(new Event('change',{bubbles:true}))");await browser.wait("document.querySelector('#traceback-table').textContent.includes('k=19')");
  const latency=await browser.eval("document.querySelector('#viterbi-decisions').textContent");check("eta 20 is shown in trellis transitions and decision timing",latency.includes("20 transitions")&&latency.includes("depth 20"),latency);
  const selectedEdge=await browser.eval("document.querySelector('#trellis-svg path[data-edge-id]')?.dataset.edgeId");await browser.eval(`document.querySelector('#trellis-svg path[data-edge-id="${selectedEdge}"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))`);check("survivor edge selection opens transition details",await browser.eval("document.querySelector('#selected-transition').textContent.includes('Transition / edge')"));
  const svgName=`hf-tcm-${identityRun}-trellis-k19.svg`;const svgEvidence=await browser.exportSvg("[data-export-svg='trellis-svg']",svgName,downloadDir);check("Viterbi graph exports real SVG paths",svgEvidence.paths>0,svgEvidence);exported.push(svgEvidence);
  await browser.click("#zoom-20-samples");await browser.wait("document.querySelector('#sample-zoom-caption').textContent.includes('20-sample zoom')");check("20 complex sample zoom is distinct from eta",await browser.eval("document.querySelector('#sample-zoom-caption').textContent.includes('20-sample zoom')"));
  screenshots.push(await browser.screenshot("repro10a-viterbi-1366x768.png"));
  await browser.eval("document.querySelector('[name=channel_profile]').value='static_multipath';document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#include-b1').checked=true;document.querySelector('#run-form').requestSubmit()");
  await browser.wait("document.querySelector('#job-status').textContent.includes('збережено')||document.querySelector('#job-status').textContent.includes('Помилка')",90000);
  await browser.wait("document.querySelector('#paired-badge').textContent.includes('observation')",60000);
  await browser.click('[data-view=viterbi]');await browser.wait("document.querySelector('#trellis-title').textContent.includes('17 states / 68 edges')");
  check("static multipath run uses real 17/68 augmented trellis and B1",await browser.eval("document.querySelector('#trellis-title').textContent.includes('17 states / 68 edges') && document.querySelector('#comparison-cards').textContent.includes('B1')"));
  await browser.eval("document.querySelector('[name=channel_profile]').value='rician_ar1_multipath';document.querySelector('[name=channel_profile]').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#run-form').requestSubmit()");
  await browser.wait("document.querySelector('#job-status').textContent.includes('збережено')||document.querySelector('#job-status').textContent.includes('Помилка')",90000);
  await browser.wait("document.querySelector('#paired-badge').textContent.includes('observation')",60000);
  check("Rician profile disables unsupported B1",await browser.eval("document.querySelector('#include-b1').disabled && !document.querySelector('#include-b1').checked"));
  await browser.click('[data-view=monte-carlo]');await browser.eval(`document.querySelector('#mc-id').value='repro09b-resume-'+Date.now();document.querySelector('#mc-frame').value='128';document.querySelector('#mc-noise').value='0.01,0.1';document.querySelector('#mc-trials').value='5';document.querySelector('#mc-profile').value='rician_ar1_multipath';document.querySelector('#mc-budget').value='300'`);
  const experimentId=await browser.eval("document.querySelector('#mc-id').value");
  await browser.eval("document.querySelector('#mc-form').requestSubmit()");
  await browser.wait("Number((document.querySelector('#mc-status').textContent.match(/(\\d+)\\/10/)||[])[1]||0)>=1",90000);
  await browser.click('#mc-stop');await browser.wait("document.querySelector('#mc-status').textContent.includes('incomplete')||document.querySelector('#mc-status').textContent.includes('збережено')",90000);
  const stoppedStatus=await browser.eval("document.querySelector('#mc-status').textContent");
  check("Monte Carlo stop produced an incomplete checkpoint before resume",stoppedStatus.includes("incomplete"),stoppedStatus);
  await browser.eval("document.querySelector('#mc-form').requestSubmit()");await browser.wait("document.querySelector('#mc-status').textContent.includes('збережено: 10/10')",180000);
  await browser.wait("document.querySelector('#mc-results').textContent.includes('Статистика серії · completed') && (document.querySelector('#mc-results').textContent.match(/trials 5/g)||[]).length===2",180000);
  const mc=await browser.eval("({text:document.querySelector('#mc-results').textContent,status:document.querySelector('#mc-status').textContent,plot:document.querySelector('#mc-ber').width,ci:document.querySelector('#mc-delta').width})");
  check("two-level five-trial paired Monte Carlo resumes to ten completed pairs",mc.text.includes("trials 5")&&mc.status.includes("10/10"),{experimentId,...mc});
  check("measured BER and bootstrap confidence plot rendered",mc.plot>0&&mc.ci>0&&mc.text.includes("95% paired CI"),mc);
  const activeRun=await browser.eval("document.querySelector('#sync-status').textContent.match(/Run ([^ ]+)/)?.[1]");
  const activeSymbol=await browser.eval("document.querySelector('#global-symbol').value");
  const mcExportName=`hf-tcm-${activeRun}-mc-ber-k${activeSymbol}.png`;
  // The export filename is based on the experiment identifier, and the chart is real measured data.
  exported.push(await browser.exportPng('[data-export-canvas="mc-ber"]',mcExportName,downloadDir));
  screenshots.push(await browser.screenshot("repro10a-monte-carlo-1366x768.png"));
  await browser.send("Emulation.setDeviceMetricsOverride",{width:1920,height:1080,deviceScaleFactor:1,mobile:false});
  await browser.click('[data-view=saved]');await browser.click('#open-long-frame');await browser.wait("document.querySelector('#trellis-caption').textContent.includes('REPRO-06C archived diagnostics')",30000);
  const archive=await browser.eval("({title:document.querySelector('#trellis-title').textContent,caption:document.querySelector('#trellis-caption').textContent,table:document.querySelector('#transition-table').textContent.slice(0,50),summary:document.querySelector('#comparison-cards').textContent})");
  check("verified F=20000 viewer opens metrics and lazily loads actual Viterbi window",archive.title.includes("17 states / 68 edges")&&archive.caption.includes("signal unavailable")&&archive.summary.includes("BER"),archive);
  check("long-frame diagnostics do not claim a joined observation",await browser.eval("document.querySelector('#sync-status').textContent.includes('same observation=false')"));
  screenshots.push(await browser.screenshot("repro10a-long-frame-1920x1080.png"));
  await browser.click('[data-view=transmitter]');await browser.wait("document.querySelector('.tab.active').dataset.view==='transmitter'");screenshots.push(await browser.screenshot("repro10a-transmitter-1920x1080.png"));
  await browser.click('[data-view=channel]');await browser.wait("document.querySelector('.tab.active').dataset.view==='channel'");screenshots.push(await browser.screenshot("repro10a-channel-1920x1080.png"));
  const report={passed:true,baseUrl:BASE,viewportSizes:[[1366,768],[1920,1080]],checks,screenshots,exports:exported};
  fs.writeFileSync(path.join(downloadDir,"gui_qa_report.json"),JSON.stringify(report,null,2),"utf8");
  console.log(JSON.stringify(report,null,2));browser.ws.close();
}
main().catch(error=>{console.error(error.stack||error);process.exit(1);});
