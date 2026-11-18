import assert from 'node:assert/strict';
import {send,js,until,errors,close} from './stage4_cdp.mjs';
try {
 await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific'});
 await until('window.systemResults && window.systemExperiment');
 assert.equal(await js('document.querySelectorAll("#system-ber-plot svg").length'),0);
 await js('document.querySelector("[name=frame_symbols]").value=32;document.getElementById("run-form").requestSubmit()');
 await until('systemResults.single?.n===32',30000);
 await js('document.querySelector(".tabs [data-view=metric]").click()');
 const result=await js('systemResults.single');
 assert.equal(result.m,64);assert.deepEqual(Object.keys(result.arms),['b0','joint']);
 for(const arm of Object.values(result.arms)){
  assert.equal(arm.scope,'complete_receiver_call');assert.ok(arm.time>0);
  assert.equal(arm.perElement,arm.time/32);assert.equal(arm.perBit,arm.time/64);
 }
 assert.ok(result.total>=result.arms.b0.time+result.arms.joint.time);
 assert.equal(await js('document.querySelectorAll(".system-result-columns>section").length'),2);
 await js(`window.dispatchEvent(new CustomEvent('system-energy-summary',{detail:{contrast_mode:'metric',receiver_arms:['joint','b0']}}))`);
 assert.equal(await js('document.querySelectorAll("#system-ber-plot svg").length'),0);
 assert.deepEqual(errors.filter(e=>!String(e.url||'').startsWith('chrome-extension://')),[]);
 console.log('PASS: real paired run, receiver timings, T/N, T/M, total and isolated-metric rejection');
}finally{close();}
