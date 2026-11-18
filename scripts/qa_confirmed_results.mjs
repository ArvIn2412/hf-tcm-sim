import assert from 'node:assert/strict';
import fs from 'node:fs';
import {send,js,until,errors,close} from './stage4_cdp.mjs';
const source=JSON.parse(fs.readFileSync('outputs/scientific_exp03b/analysis/independent_analysis.json','utf8'));
try {
  if(process.env.HF_TCM_QA_USE_OPEN_PAGE!=='1') await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific'});
  await until('window.energyInteractive && document.querySelector(".results-actions select")');
  // Explicit UI-only mode: real saved aggregates, mocked transport/provenance.
  // This does not verify the HTTP loader or historical integrity.
  if(process.env.HF_TCM_QA_ARCHIVE_FIXTURE==='1') await js(`{
    const original=window.fetch.bind(window);
    window.fetch=(url,...args)=>String(url)==='/api/scientific/exp03b-results'
      ? Promise.resolve(new Response(JSON.stringify(${JSON.stringify({...source,provenance_verified:true})}),{status:200}))
      : original(url,...args);
  }`);
  await js('document.querySelector(".tabs [data-view=metric]").click()');
  for(const key of ['awgn_direct','awgn_pilot','static_pilot','rician_period32']) {
    const started=performance.now();
    await js(`document.querySelector('.results-actions select').value=${JSON.stringify(key)};document.querySelector('.results-actions button:last-child').click()`);
    await until('!document.querySelector(".results-actions button:last-child").disabled',900000);
    const actual=await js('energyInteractive.summary');
    assert.ok(actual,await js('document.querySelector("#view-metric").innerText'));
    const expected=source.metric_isolation[key].amplitude_fixed_noise;
    assert.equal(actual.confirmed_archive,true);
    assert.deepEqual(actual.aggregates.map(r=>r.ber.hamming),expected.point_summaries.map(r=>r.ber.hamming));
    assert.deepEqual(actual.aggregates.map(r=>r.bit_errors.joint),expected.point_summaries.map(r=>r.bit_errors.euclidean));
    assert.deepEqual(actual.aggregates.map(r=>r.ber_ci.hamming),expected.point_summaries.map(r=>r.bootstrap_95ci.ber.hamming));
    assert.deepEqual(actual.aggregates.map(r=>r.bits),expected.point_summaries.map(r=>r.bits));
    for(const [target,original] of [['hamming','hamming'],['joint','euclidean']]) {
      for(const field of ['pair_errors','frame_errors']) assert.deepEqual(actual.aggregates.map(r=>r[field][target]),expected.point_summaries.map(r=>r[field][original]));
      assert.deepEqual(actual.aggregates.map(r=>r.ser_ci[target]),expected.point_summaries.map(r=>r.bootstrap_95ci.ser_information_pairs[original]));
      assert.deepEqual(actual.aggregates.map(r=>r.fer_ci[target]),expected.point_summaries.map(r=>r.bootstrap_95ci.fer[original]));
    }
    assert.deepEqual(actual.archive_gains,expected.metric_gain);
    assert.equal(await js('document.querySelectorAll("#view-metric canvas").length'),1);
    assert.ok(await js('document.querySelector(".results-comparison").textContent.includes("95%")'));
    const shown=await js('document.querySelector(".results-comparison").textContent');
    for(const arm of ['hamming','euclidean']) {
      const first=expected.point_summaries[0];
      assert.ok(shown.includes(first.bit_errors[arm].toLocaleString('uk-UA')));
      assert.ok(shown.includes(first.pair_errors[arm].toLocaleString('uk-UA')));
    }
    const zero=expected.point_summaries.findIndex(r=>r.bit_errors.euclidean===0||r.bit_errors.hamming===0);
    if(zero>=0){
      await js(`var point=document.querySelector('[aria-label="Енергетична точка"]');point.value=${zero};point.dispatchEvent(new Event('change'))`);
      assert.ok(await js('document.querySelector(".results-comparison").textContent.includes("це не доводить нульову ймовірність")'));
    }
    await js('document.querySelector(".results-chart details").open=true;var s=document.querySelector(".results-chart [data-action=scale]");s.value="log";s.dispatchEvent(new Event("change"))');
    assert.ok(await js('energyInteractive.charts.ber.points.every(p=>p.y>0)'));
    assert.ok(await js('document.querySelector(".results-gain").textContent.length>30'));
    const gainText=await js('document.querySelector(".results-gain").textContent');
    const estimate=expected.metric_gain['0.05'];
    if(estimate.precision_assessment.status==='PRECISION_CRITERIA_MET') {
      assert.ok(gainText.includes(estimate.gain_db_log_ber.toLocaleString('uk-UA',{maximumSignificantDigits:5})));
      assert.ok(gainText.includes('95%'));
    } else assert.ok(gainText.includes('не оцінено'));
    console.log('PASS',key,process.env.HF_TCM_QA_ARCHIVE_FIXTURE==='1'?'UI fixture transport':'verified HTTP',Math.round(performance.now()-started)+'ms');
  }
  console.log('HTTP timings',await js(`performance.getEntriesByType('resource').filter(r=>r.name.endsWith('/exp03b-results')).map(r=>({ms:Math.round(r.duration),bytes:r.decodedBodySize}))`));
  await js(`window.exportChecks=[];HTMLAnchorElement.prototype.click=function(){
    if(this.download)window.exportChecks.push({name:this.download,data:fetch(this.href).then(r=>r.blob()).then(b=>b.size)});
  };for(const action of ['csv','png','svg'])document.querySelector('.results-chart [data-action='+action+']').click();
  [...document.querySelectorAll('.results-chart button')].find(b=>b.textContent==='JSON').click()`);
  const exports=await js('Promise.all(exportChecks.map(async x=>({name:x.name,size:await x.data})))');
  assert.equal(exports.length,4);
  assert.ok(exports.every(x=>x.size>100));
  await js(`window.dispatchEvent(new CustomEvent('metric-summary',{detail:{contrast_mode:'system',configuration:{}}}))`);
  assert.equal(await js('document.querySelectorAll("#view-metric canvas").length'),0);
  assert.equal(await js('document.querySelector(".results-comparison").children.length'),0);
  // Optional timing probe: the normal scientific E2E reuses the verified response.
  if(process.env.HF_TCM_QA_ARCHIVE_FIXTURE!=='1'&&process.env.HF_TCM_QA_MEASURE_WARM==='1') {
    await js(`window.warmResult=null;window.warmError=null;(async()=>{try{const started=performance.now();const r=await fetch('/api/scientific/exp03b-results',{signal:AbortSignal.timeout(600000)});const d=await r.json();window.warmResult={ms:Math.round(performance.now()-started),status:r.status,verified:d.provenance_verified};}catch(e){window.warmError=e.message;}})();void 0`);
    await until('window.warmResult || window.warmError',610000);
    assert.equal(await js('window.warmError'),null);
    const warm=await js('window.warmResult');
    assert.equal(warm.status,200);assert.equal(warm.verified,true);
    console.log('Warm HTTP',warm);
  }
  const extensionErrors=errors.filter(e=>String(e.url||'').startsWith('chrome-extension://'));
  if(extensionErrors.length)console.log('External extension exceptions',extensionErrors.map(e=>e.url));
  assert.deepEqual(errors.filter(e=>!String(e.url||'').startsWith('chrome-extension://')),[]);
} finally {close();}

