import fs from 'node:fs';
import {send,js,until,close} from './stage4_cdp.mjs';
try{
await send('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});
await until('window.sequenceNavigator?.data?.series&&!sequenceNavigator.pending&&!window.metricTracePending');
const result=await js(`(async()=>{
 const measured=async action=>new Promise((resolve,reject)=>{const began=performance.now();let timeout;const handler=()=>requestAnimationFrame(()=>{if(window.metricTracePending||sequenceNavigator.pending||metricLiveTrace.start>sequenceNavigator.symbol_index||metricLiveTrace.stop<=sequenceNavigator.symbol_index)return;clearTimeout(timeout);window.removeEventListener('metric-trace-loaded',handler);resolve(performance.now()-began);});timeout=setTimeout(()=>{window.removeEventListener('metric-trace-loaded',handler);reject(Error('measurement timeout'));},20000);window.addEventListener('metric-trace-loaded',handler);action();});
 document.querySelector('[data-view=transmitter]').click();
 const window_ms=await measured(()=>sequenceNavigator.setRange(40000,6400));
 const zoom=[];for(let i=0;i<3;i++){const before=[...sequenceNavigator.visible_range],ms=await measured(()=>sequenceNavigator.zoom(.7,.6));zoom.push({before,after:[...sequenceNavigator.visible_range],ms});}
 const panBefore=[...sequenceNavigator.visible_range],pan_ms=await measured(()=>sequenceNavigator.setRange(panBefore[0]-200,panBefore[1]-panBefore[0]));const pan={before:panBefore,after:[...sequenceNavigator.visible_range],ms:pan_ms,method:'window pan API; mouse/touch gestures tested separately'};
 sequenceNavigator.domain='sample';const first_ms=await measured(()=>sequenceNavigator.go(0));const first=sequenceNavigator.data.inspector.sample;const last_ms=await measured(()=>sequenceNavigator.go(159999));const last=sequenceNavigator.data.inspector.sample;
 const tabs=[];for(const view of ['constellation','viterbi','transmitter']){const begin=performance.now();document.querySelector('[data-view="'+view+'"]').click();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));tabs.push({view,ms:performance.now()-begin});}
 return{window_ms,zoom,pan,first_to_last:{first,last,first_ms,last_ms},tabs,definition:'warm component action to completed trace plus animation frame; warm tab action to two animation frames'};
})()`);
result.heap=await send('Runtime.getHeapUsage');fs.writeFileSync((process.env.HF_TCM_QA_OUTPUT||'outputs/ui_interactivity_stage4')+'/browser_performance.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{close();}
