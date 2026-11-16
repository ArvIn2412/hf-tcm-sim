import fs from 'node:fs';
const pages=await(await fetch('http://127.0.0.1:9240/json/list')).json();
const page=pages.find(p=>p.type==='page'); const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));let seq=0;const waiting=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const f=waiting.get(m.id);waiting.delete(m.id);m.error?f.reject(m.error):f.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;waiting.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evalJS=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});
const report={};
report.trace=await evalJS(`({loaded:!!window.metricLiveTrace,provenance:document.querySelector('#live-provenance').textContent,pairing:window.metricLiveTrace?.pairing_verified,replay:window.metricLiveTrace?.replay_verified,rx:window.metricLiveTrace?.received.length,panels:document.querySelectorAll('[id^="live-metrics-"]').length})`);
console.log(report.trace);if(!report.trace.loaded||!report.trace.pairing||!report.trace.replay)throw Error('missing live data');
await evalJS(`document.querySelector('#live-k').value=9;document.querySelector('#live-k').dispatchEvent(new Event('change'))`);
report.synchronization=await evalJS(`['hamming','euclidean'].every(a=>document.querySelector('#live-bits-'+a).textContent.includes('k=9'))`);
if(!report.synchronization)throw Error('not synchronized');
report.tooltips=await evalJS(`({groups:document.querySelectorAll('.parameter-group').length,missing:[...document.querySelectorAll('#metric-study-form input,#metric-study-form select')].filter(e=>!e.title).map(e=>e.id)})`);
if(report.tooltips.groups!==5||report.tooltips.missing.length)throw Error('parameter help incomplete');
for(const name of ['parameters','transmitter','constellation','viterbi','metric','saved']){
 await evalJS(`document.querySelector('[data-view="${name}"]').click();window.scrollTo(0,0)`);await new Promise(r=>setTimeout(r,300));
 const {data}=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(`outputs/ui_article_alignment/stage2-${name}.png`,Buffer.from(data,'base64'));
}
await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await evalJS(`document.querySelector('[data-view="viterbi"]').click()`);
report.mobile=await evalJS(`({width:innerWidth,scroll:document.documentElement.scrollWidth,columns:getComputedStyle(document.querySelector('#view-viterbi .article-pair')).gridTemplateColumns})`);
if(report.mobile.scroll>report.mobile.width+1)throw Error('mobile overflow');
for(const view of ['viterbi','constellation']){await evalJS(`document.querySelector('[data-view="${view}"]').click();window.scrollTo(0,0)`);const layout=await send('Page.getLayoutMetrics');const {data}=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:390,height:Math.min(layout.cssContentSize.height,8000),scale:1}});fs.writeFileSync(`outputs/ui_article_alignment/stage2-mobile-${view}.png`,Buffer.from(data,'base64'));}
fs.writeFileSync('outputs/ui_article_alignment/stage2-browser.json',JSON.stringify(report,null,2));
console.log(report);ws.close();
