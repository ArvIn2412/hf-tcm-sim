import assert from 'node:assert/strict';
import {send, js, until, pause, errors, close} from './stage4_cdp.mjs';

try {
  const width=Number(process.env.HF_TCM_QA_WIDTH||1366);
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<768});
  errors.length = 0;
  await send('Page.navigate', {url: 'http://127.0.0.1:18772/scientific'});
  await until('window.energyInteractive && document.getElementById("signal-mode")');
  await js('document.querySelector("[data-view=transmitter]").click(); [...document.querySelectorAll(".signal-bar button")].find(b => b.textContent === "Fit").click()');
  assert.equal(await js('document.querySelectorAll("#view-transmitter .signal-plot canvas").length'), 1);
  assert.equal(await js('document.querySelectorAll("#view-transmitter #lab-overview, #view-transmitter #live-source, #view-transmitter #xy-inspector").length'), 0);
  await js(`(() => {
    document.getElementById('mx-frame').value = 32;
    document.getElementById('mx-seed').value = 85731;
    document.getElementById('article-sweep').checked = false;
    document.getElementById('metric-study-form').requestSubmit();
  })()`);
  await until('sequenceNavigator.data?.total_symbols === 32 && !sequenceNavigator.pending', 30000);
  await js('document.querySelector("[data-view=transmitter]").click()');
  await js(`sequenceNavigator.domain='symbol'; document.getElementById('seq-domain').value='symbol'; sequenceNavigator.go(31)`);
  await until('sequenceNavigator.symbol_index === 31 && !sequenceNavigator.pending');
  assert.match(await js('document.querySelector(".signal-inspector").textContent'), /Символ 31.*TX I\/Q.*RX I\/Q.*Хемінг.*Евклід/);
  for (const [mode, id] of [['overlay', 'live-wave'], ['lanes', 'live-wave'], ['cloud', 'received-cloud']]) {
    await js(`document.getElementById('signal-mode').value='${mode}'; document.getElementById('signal-mode').dispatchEvent(new Event('change'))`);
    assert.equal(await js('document.querySelectorAll("#view-transmitter canvas").length'), 1);
    assert.equal(await js('document.querySelector("#view-transmitter canvas").id'), id);
  }
  const bounds = await js('JSON.parse(document.getElementById("received-cloud").dataset.bounds)');
  assert.equal(bounds.scaleX, bounds.scaleY);
  await until('constellationView.points.length > 0');
  const target = await js(`(() => { const c=document.getElementById('received-cloud');c.scrollIntoView({block:'center'});const r=c.getBoundingClientRect(),p=constellationView.points.find(v=>v.symbol>=2 && v.x>10 && v.x<c.width-10 && v.y>10 && v.y<c.height-10); return p && {x:r.x+p.x*r.width/c.width,y:r.y+p.y*r.height/c.height}; })()`);
  assert.ok(target, 'No real selectable 8PSK point in current window');
  await send('Input.dispatchMouseEvent',{type:'mousePressed',...target,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',...target,button:'left',clickCount:1});
  await until('constellationView.selected && !sequenceNavigator.pending && sequenceNavigator.symbol_index === constellationView.selected.symbol');
  assert.equal(await js('Number(document.getElementById("seq-index").value)'), await js('constellationView.selected.symbol'));
  assert.match(await js('document.querySelector(".signal-inspector").textContent'), new RegExp(`Символ ${await js('constellationView.selected.symbol')}\\b`));
  console.log('PASS: real 8PSK point synchronizes symbol and inspector');
  await send('Page.navigate',{url:'http://127.0.0.1:18772/scientific?run_id=stage3-control-20000'});
  try {
    await until('window.sequenceNavigator?.data?.total_symbols === 20000 && !sequenceNavigator.pending',30000);
  } catch(error) {
    const detail=await js('document.getElementById("live-provenance")?.textContent');
    throw new Error(`${error.message}; trace status: ${detail}`);
  }
  await js('document.querySelector("[data-view=transmitter]").click()');
  for (const [domain,index] of [['symbol',19999],['sample',159999]]) {
    await js(`sequenceNavigator.domain='${domain}'; document.getElementById('seq-domain').value='${domain}'; sequenceNavigator.go(${index})`);
    await until(`!sequenceNavigator.pending && sequenceNavigator.index === ${index}`,30000);
    assert.equal(await js('sequenceNavigator.data.inspector.sample'), domain==='sample'?159999:159992);
  }
  await js('sequenceNavigator.setRange(40000,8000,44000)');
  await until('!sequenceNavigator.pending && sequenceNavigator.data.start === 40000');
  const rect = await js(`(() => {const c=document.getElementById('live-wave');c.scrollIntoView({block:'center'});const r=c.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()`);
  const range = () => js('sequenceNavigator.visible_range.slice()');
  const before = await range();
  await send('Input.dispatchMouseEvent',{type:'mouseWheel',x:rect.x+rect.w*.5,y:rect.y+rect.h*.4,deltaY:-100,deltaX:0});
  await until('!sequenceNavigator.pending');
  const zoomed = await range(); assert.ok(zoomed[1]-zoomed[0] < before[1]-before[0]);
  const x=rect.x+rect.w*.4,y=rect.y+rect.h*.4;
  await send('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:x+rect.w*.15,y,buttons:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:x+rect.w*.15,y,button:'left',clickCount:1});
  await until('!sequenceNavigator.pending');
  assert.notEqual((await range())[0],zoomed[0]);
  await js('[...document.querySelectorAll(".signal-bar button")].find(b=>b.textContent==="Fit").click()');
  await until('!sequenceNavigator.pending && sequenceNavigator.visible_range[1] === 160000');
  assert.deepEqual(await range(),[0,160000]);
  assert.equal(await js('sequenceNavigator.data.series["RX I"].raw'),false);
  await pause(200);
  assert.deepEqual(errors, []);
  console.log('PASS: N=32 modes and I/Q scale; N=20000 last symbol/sample, zoom, pan, Fit and LOD');
} finally { close(); }
