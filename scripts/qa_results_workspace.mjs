import assert from 'node:assert/strict';
import {send, js, until, pause, errors, close} from './stage4_cdp.mjs';

try {
  const width=Number(process.env.HF_TCM_QA_WIDTH||1366);
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<768});
  errors.length=0;
  await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific'});
  await until('window.energyInteractive && document.querySelector("#view-metric .results-chart")');
  assert.equal(await js('document.querySelectorAll(".tabs > .tab").length'),3);
  assert.equal(await js('document.querySelectorAll("#view-metric canvas").length'),0);
  assert.match(await js('document.querySelector("#view-metric").textContent'),/Енергетичне дослідження ще не виконано/);
  await js(`document.getElementById('mx-frame').value=32;document.getElementById('mx-seed').value=86573;document.getElementById('article-sweep').checked=false;document.getElementById('metric-study-form').requestSubmit()`);
  await until('window.metricLiveTrace?.total_symbols === 32',30000);
  await js('document.querySelector("[data-view=metric]").click()');
  assert.match(await js('document.querySelector(".results-comparison").textContent'),/Хемінг[\s\S]*Бітові помилки[\s\S]*Евклід/);
  assert.equal(await js('document.querySelectorAll("#view-metric canvas").length'),0);
  await js('[...document.querySelectorAll(".results-actions button")].find(b=>b.textContent==="Декодування").click()');
  assert.equal(await js('document.querySelector(".tab.active").dataset.view'),'viterbi');
  assert.ok(await js('document.querySelectorAll("#live-hamming path").length > 0 && document.querySelectorAll("#live-euclidean path").length > 0'));
  await js('document.getElementById("live-k").value=5; document.getElementById("live-k").dispatchEvent(new Event("change"))');
  await until('window.sequenceNavigator?.symbol_index === 5 && !sequenceNavigator.pending');
  assert.ok(await js('["hamming","euclidean"].every(a=>document.getElementById("live-bits-"+a).textContent.includes("k=5"))'));
  await js('document.querySelector("[data-view=metric]").click(); [...document.querySelectorAll(".results-actions button")].find(b=>b.textContent==="Відкрити збережене дослідження").click(); document.getElementById("catalog-q").value="ui-acceptance-1794819536746-sweep";document.getElementById("catalog-filters").requestSubmit()');
  await until('window.studyCatalog?.state?.q === "ui-acceptance-1794819536746-sweep" && studyCatalog.state.response?.items?.length === 1',15000);
  await js('document.querySelector("[data-catalog-open]").click()');
  await until('window.energyInteractive?.summary?.configuration?.experiment_id === "ui-acceptance-1794819536746-sweep"',20000);
  await js('document.querySelector("[data-view=metric]").click()');
  await pause(200);
  assert.equal(await js('document.querySelectorAll("#view-metric canvas").length'),1);
  assert.ok(await js('energyInteractive.charts.ber.points.length > 0'));
  assert.equal(await js('document.querySelectorAll("#view-metric table, #view-metric form").length'),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: empty state, paired frame, synchronized trellises, saved series and BER');
} finally { close(); }
