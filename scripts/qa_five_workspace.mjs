import assert from 'node:assert/strict';
import {send,js,until,errors,close} from './stage4_cdp.mjs';
try{
 await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific'});
 await until('window.systemResults && window.systemSignal && window.systemDecoding && window.systemStudies');
 await js('document.querySelector("[name=frame_symbols]").value=32;document.getElementById("run-form").requestSubmit()');
 await until('systemResults.single && systemSignal.data && systemDecoding.traces',30000);
 for(const width of [1366,1920,2560]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
  for(const key of ['parameters','transmitter','viterbi','metric','saved']){
   await js(`document.querySelector('.tabs [data-view=${key}]').click()`);
   assert.equal(await js('document.querySelectorAll(".view.active").length'),1);
   assert.equal(await js('document.querySelector(".view.active").id'),'view-'+key);
   assert.ok(await js('document.querySelector("main").getBoundingClientRect().width>=innerWidth-20'));
   assert.ok(await js('document.documentElement.scrollWidth<=innerWidth+1'));
   assert.ok(await js('parseFloat(getComputedStyle(document.body).fontSize)>=16'));
  }
  assert.equal(await js('document.querySelectorAll(".tabs button").length'),5);
  assert.equal(await js('document.querySelectorAll(".sync-toolbar").length'),1);
  assert.equal(await js('document.querySelectorAll("#metric-study-form,#received-cloud,#live-wave,#trellis-svg").length'),0);
  assert.equal(await js('(()=>{const ids=[...document.querySelectorAll("[id]")].map(n=>n.id);return ids.length-new Set(ids).size;})()'),0);
  console.log('PASS desktop',width);
 }
 await js('document.querySelector(".tabs [data-view=transmitter]").click();document.getElementById("system-signal-mode").value="cloud";document.getElementById("system-signal-mode").dispatchEvent(new Event("change"))');
 for(const mode of ['hard','joint']){
  await js(`document.getElementById('system-cloud-mode').value='${mode}';document.getElementById('system-cloud-mode').dispatchEvent(new Event('change'))`);
  const scale=await js('systemSignal.axisScale');assert.equal(scale.x,scale.y);
 }
 for(const [domain,index]of [['symbol',31],['sample',255],['information',63],['coded',95]]){
  await js(`var d=document.querySelector('[aria-label="Одиниця навігації"]');d.value='${domain}';d.dispatchEvent(new Event('change'));var n=document.querySelector('[aria-label="Позиція"]');n.value=${index};n.dispatchEvent(new Event('change'))`);
  await until('systemSignal.data?.selected.start_symbol===31 && systemDecoding.traces?.joint.symbol_index===31');
  assert.equal(await js('Number(document.querySelector("[aria-label=Позиція]").value)'),index);
  await js('document.getElementById("symbol-previous").click()');
  assert.equal(await js('Number(document.querySelector("[aria-label=Позиція]").value)'),index-1);
  await js('document.getElementById("symbol-next").click()');
  assert.equal(await js('Number(document.querySelector("[aria-label=Позиція]").value)'),index);
 }
 assert.deepEqual(errors.filter(e=>!String(e.url||'').startsWith('chrome-extension://')),[]);
 console.log('PASS: five routes, two technologies, hard/Euclidean cloud, four navigation domains');
}finally{close();}
