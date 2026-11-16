import assert from 'node:assert/strict';
import fs from 'node:fs';
import {send,js,until,pause,close,errors} from './stage4_cdp.mjs';
const checks=[];
try{
await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific?run_id=stage3-control-20000'});errors.length=0;
await until('window.sequenceNavigator?.data?.run_id==="stage3-control-20000"&&!window.metricTracePending');
await js('sequenceNavigator.domain="sample";sequenceNavigator.go(159999)');
await until('sequenceNavigator.data?.inspector.sample===159999&&!window.metricTracePending&&!sequenceNavigator.pending');
const short='ui-acceptance-1794819536746-sweep';
await js(`studyCatalog.open({kind:'metric',id:'${short}'})`);
await pause(1800);
assert.equal(await js('sequenceNavigator.run'),short);
await until(`sequenceNavigator.data?.run_id==='${short}'&&!window.metricTracePending&&!sequenceNavigator.pending`);
assert.equal(await js('metricLiveTrace.study_id'),short);
assert.ok(await js('sequenceNavigator.symbol_index<metricLiveTrace.total_symbols'));
checks.push({name:'long_end_to_short_study',status:'PASS'});
const other='exp03a-pilot-awgn-pilot-v1';
await js(`studyCatalog.open({kind:'metric',id:'${other}'});studyCatalog.open({kind:'metric',id:'${short}'})`);
await until(`sequenceNavigator.data?.run_id==='${short}'&&!sequenceNavigator.pending&&!window.metricTracePending`);await pause(400);
assert.equal(await js('metricLiveTrace.study_id'),short);checks.push({name:'rapid_study_switch_latest_wins',status:'PASS'});
}catch(e){checks.push({name:'study_switch',status:'FAIL',error:String(e)});}finally{fs.writeFileSync((process.env.HF_TCM_QA_OUTPUT||'outputs/ui_interactivity_stage4')+'/browser_run_switch.json',JSON.stringify({checks,errors},null,2));console.log(JSON.stringify(checks));close();}
