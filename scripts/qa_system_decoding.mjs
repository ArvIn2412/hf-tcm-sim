import assert from 'node:assert/strict';
import {send,js,until,errors,close} from './stage4_cdp.mjs';
try {
  await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific'});
  await until('window.systemExperiment && window.systemDecoding');
  await js(`document.querySelector('[name=frame_symbols]').value=32;
    document.getElementById('exp-rays').value=2;document.getElementById('exp-rays').dispatchEvent(new Event('change'));
    document.getElementById('run-form').requestSubmit()`);
  await until('systemDecoding.traces?.joint.available && systemDecoding.traces?.b0.available',30000);
  await js('document.querySelector(".tabs [data-view=viterbi]").click()');
  assert.equal(await js('document.querySelectorAll("#view-viterbi svg").length'),2);
  assert.equal(await js('document.querySelectorAll("#view-viterbi table,#view-viterbi input,#view-viterbi select").length'),0);
  for(const tick of [18,19,31]){
    await js(`systemNodes.get('#global-symbol').value=${tick};systemNodes.get('#global-symbol').dispatchEvent(new Event('change'))`);
    await until(`systemDecoding.traces?.joint.symbol_index===${tick}&&systemDecoding.traces?.b0.symbol_index===${tick}`);
    for(const arm of ['b0','joint']){
      const t=await js(`systemDecoding.traces.${arm}`);
      assert.equal(t.traceback_steps.length,Math.min(tick+1,20));
      if(tick===18)assert.equal(t.emitted_decision_on_this_arrival,null);
      if(tick===19){assert.equal(t.emitted_decision_on_this_arrival.symbol_index,0);assert.equal(t.emitted_decision_on_this_arrival.traceback_depth_used,20);}
      if(tick===31)assert.equal(t.emitted_decision_for_selected_symbol.decision_available_at,31);
      const paths=await js(`[...document.querySelectorAll('#system-trellis-${arm} path[data-path=true]')].map(p=>[Number(p.dataset.tick),Number(p.dataset.edge)])`);
      assert.deepEqual(paths,t.traceback_local_survivor_path.map(e=>[e.symbol_index,e.edge_id]));
    }
  }
  await js(`document.querySelector('#system-trellis-joint path[data-tick="20"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))`);
  await until('systemDecoding.traces?.joint.symbol_index===20&&systemDecoding.traces?.b0.symbol_index===20');
  assert.equal(await js('systemNodes.get("#global-symbol").value'),'20');
  assert.ok(await js('document.getElementById("system-edge-inspector").textContent.includes("branch metric")'));
  assert.ok(await js('document.getElementById("system-edge-inspector").textContent.includes("path metric")'));
  for(const width of [1366,2560]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await js('document.querySelector(".system-trellis-scroll").scrollLeft=200');
    await until('document.querySelectorAll(".system-trellis-scroll")[1].scrollLeft===document.querySelectorAll(".system-trellis-scroll")[0].scrollLeft');
    assert.ok(await js('document.getElementById("system-trellis-joint").getAttribute("height")>=320'));
  }
  assert.deepEqual(errors.filter(e=>!String(e.url||'').startsWith('chrome-extension://')),[]);
  console.log('PASS: paired system trellises, finite-depth timing, survivor paths, edge selection and navigator');
}finally{close();}
