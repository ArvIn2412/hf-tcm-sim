import fs from 'node:fs';
const pages=await(await fetch('http://127.0.0.1:9240/json/list')).json();
const page=pages.find(p=>p.type==='page'); const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));let seq=0;const waiting=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const f=waiting.get(m.id);waiting.delete(m.id);m.error?f.reject(m.error):f.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;waiting.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evalJS=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};

await send('Page.enable');await send('Page.navigate',{url:'http://127.0.0.1:18771/scientific'});await new Promise(r=>setTimeout(r,1500));
await evalJS(`window.dispatchEvent(new CustomEvent('metric-summary',{detail:{configuration:{experiment_id:'stage3-control-20000'}}}))`);
await new Promise(r=>setTimeout(r,1800));
const report=[];
for(const [domain,indices] of [['symbol',[0,999,1000,19998,19999]],['sample',[0,7999,8000,159998,159999]]]){
 await evalJS(`document.getElementById('seq-domain').value='${domain}';document.getElementById('seq-domain').dispatchEvent(new Event('change'))`);
 for(const i of indices){await evalJS(`document.getElementById('seq-index').value=${i};document.getElementById('seq-go').click()`);for(let wait=0;wait<100;wait++){const ready=await evalJS(`(()=>{try{return JSON.parse(document.getElementById('seq-inspector').textContent).${domain==='sample'?'sample':'symbol'}===${i}}catch{return false}})()`);if(ready)break;await new Promise(r=>setTimeout(r,200));}const data=await evalJS(`({domain:sequenceNavigator.domain,index:sequenceNavigator.index,inspector:JSON.parse(document.getElementById('seq-inspector').textContent),pairing:metricLiveTrace.pairing_verified})`);if(data.index!==i||!data.pairing||data.inspector[domain==='sample'?'sample':'symbol']!==i)throw Error('navigation failed');report.push(data);}
}
for(const [w,h] of [[1366,900],[1920,1080],[390,844],[320,640],[834,1112]]){await send('Emulation.setDeviceMetricsOverride',{width:w,height:h,deviceScaleFactor:1,mobile:w<768});for(const view of ['parameters','transmitter','constellation','viterbi','metric','saved']){await evalJS(`document.querySelector('[data-view="${view}"]').click();window.scrollTo(0,0)`);await new Promise(r=>setTimeout(r,120));const {data}=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(`outputs/ui_interactivity_stage3/${view}-${w}.png`,Buffer.from(data,'base64'));}}
fs.writeFileSync('outputs/ui_interactivity_stage3/browser.json',JSON.stringify(report,null,2));console.log('10 navigation cases, 30 screenshots');ws.close();

