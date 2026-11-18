/* One waveform/constellation surface for actual B0/Joint system traces. */
(() => {
 'use strict';
 document.addEventListener('DOMContentLoaded',()=>{
  const view=document.getElementById('view-transmitter'),stash=window.systemArchive;
  stash.append(...view.childNodes);
  view.innerHTML='<h1>Сигнал і канал</h1><div class="system-signal-tools"><select id="system-signal-mode" aria-label="Графік"><option value="txrx">TX/RX</option><option value="iq">I/Q</option><option value="cloud">Сузір’я 8PSK</option><option value="noise">Шум</option><option value="paths">Промені</option></select><select id="system-cloud-mode" aria-label="Оцінювання"><option value="hard">Жорстке рішення</option><option value="joint">Евклідове оцінювання</option></select><button id="system-fit">Fit</button><span id="system-hover"></span></div><canvas id="system-signal-canvas" tabindex="0" aria-label="Сигнал поточного запуску"></canvas><div id="system-symbol-inspector"></div>';
  const $=id=>document.getElementById(id),canvas=$('system-signal-canvas'),mode=$('system-signal-mode'),cloudMode=$('system-cloud-mode');
  const state={summary:null,data:null,start:0,count:160,symbol:0,request:0,controller:null,scale:1,cx:0,cy:0,points:[]};window.systemSignal=state;
  const symbolField=window.systemNodes.get('#global-symbol'),sampleField=window.systemNodes.get('#global-sample');
  function select(k){if(!state.summary)return;k=Math.max(0,Math.min(state.summary.frame_symbols-1,Math.floor(k)));symbolField.value=k;symbolField.dispatchEvent(new Event('change'));window.dispatchEvent(new CustomEvent('system-position',{detail:{symbol:k,sample:k*8}}));}
  async function load(){if(!state.summary)return;const key=JSON.stringify([state.summary.run_id,state.start,state.count,state.symbol]);if(state.pendingKey===key)return;state.pendingKey=key;const version=++state.request;state.controller?.abort();state.controller=new AbortController();
   try{const q=new URLSearchParams({run_id:state.summary.run_id,overview:1,start:state.start,count:state.count,symbol:state.symbol});const r=await fetch('/api/scientific/traces?'+q,{signal:state.controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error);if(version!==state.request)return;state.data=d;inspect();draw();}
   catch(e){if(e.name!=='AbortError')$('system-symbol-inspector').textContent='Не вдалося отримати сигнал: '+e.message;}finally{if(version===state.request)state.pendingKey=null;}}
  function inspect(){if(!state.data)return;const t=state.data.selected;const f=v=>Number.isFinite(v)?v.toPrecision(5):'—';const chosen=t.joint_decoded_edges?.[0];
   $('system-symbol-inspector').textContent=`Елемент ${state.symbol} · біти ${t.input_pairs[0].join('')} → ${t.coded_triples[0].join('')} · TX (${f(t.tx_i[0])}; ${f(t.tx_q[0])}) · RX (${f(t.received_i[0])}; ${f(t.received_q[0])}) · жорсткий фазовий індекс ${t.hard_phase_indices[0]} · B0 перехід ${t.separate_decoded_edges[0]} · Joint перехід ${chosen}`;
   if(mode.value==='cloud'&&cloudMode.value==='joint')$('system-symbol-inspector').textContent+=' · фактичні кандидатні метрики: '+t.joint_metrics[0].map((v,i)=>`${i}: ${f(v)}`).join(' · ');
  }
  function draw(){if(!state.data)return;const d=state.data;const w=Math.max(320,canvas.clientWidth||800),h=500,dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.fillStyle='#fff';c.fillRect(0,0,w,h);c.font='14px Segoe UI';state.points=[];
   if(mode.value==='cloud'){
    const t=d.selected;const amplitude=state.summary.configuration?.amplitude||1;const range=Math.max(amplitude*1.3,...d.cloud.flatMap(p=>p.slice(1).map(Math.abs)))*state.scale;
    const plotH=h-60,scale=Math.min(w-100,plotH-40)/(2*range);state.axisScale={x:scale,y:scale};const x=v=>w/2+(v-state.cx)*scale,y=v=>plotH/2-(v-state.cy)*scale;
    c.strokeStyle='#ddd';c.beginPath();c.moveTo(50,y(0));c.lineTo(w-20,y(0));c.moveTo(x(0),20);c.lineTo(x(0),plotH-10);c.stroke();c.fillStyle='#334';c.fillStyle='#334';c.fillText('I',w-35,y(0)-8);c.fillText('Q',x(0)+8,30);
    for(let k=0;k<8;k++){const a=k*Math.PI/4;c.strokeStyle='#778';c.beginPath();c.arc(x(amplitude*Math.cos(a)),y(amplitude*Math.sin(a)),6,0,Math.PI*2);c.stroke();c.fillText([(k>>2)&1,(k>>1)&1,k&1].join(''),x(amplitude*Math.cos(a))+9,y(amplitude*Math.sin(a)));}
    for(const p of d.cloud){c.fillStyle='#087f8c80';c.fillRect(x(p[1])-2,y(p[2])-2,4,4);state.points.push({x:x(p[1]),y:y(p[2]),sample:p[0],i:p[1],q:p[2]});}
    c.strokeStyle='#111';c.beginPath();c.arc(x(t.received_i[0]),y(t.received_q[0]),8,0,7);c.stroke();
    c.fillStyle='#fff';c.fillRect(0,plotH,w,h-plotH);c.strokeStyle='#e3e9ec';c.beginPath();c.moveTo(0,plotH);c.lineTo(w,plotH);c.stroke();c.fillStyle='#334';c.fillText('Точки — сирі відліки RX до комбайнера (8 на елемент); коло — перший відлік вибраного елемента.',50,h-34);
    if(cloudMode.value==='hard'){const a=t.hard_phase_indices[0]*Math.PI/4;c.strokeStyle='#bb6518';c.lineWidth=3;c.beginPath();c.arc(x(amplitude*Math.cos(a)),y(amplitude*Math.sin(a)),10,0,7);c.stroke();c.lineWidth=1;c.fillStyle='#bb6518';c.fillText('Помаранчеве коло — жорстке рішення B0 на виході його фронтенду (не по сирому відліку).',50,h-15);}
    else{c.fillStyle='#334';c.fillText('Joint оцінює канал окремо для кожного шляху Вітербі — єдиної точки z немає. Відстані Евкліда: вкладка «Етапи обробки».',50,h-15);}
    state.transform={scale,x,y};return;
   }
   const entries=Object.entries(d.series).filter(([k])=>mode.value==='noise'?k.startsWith('Шум'):mode.value==='paths'?k.startsWith('Промінь'):k.startsWith('TX')||k.startsWith('RX'));
   const max=Math.max(1,...entries.flatMap(([,p])=>p.flatMap(v=>v.slice(1).map(Math.abs))));const colors=['#087f8c','#bb6518','#7163a5','#407caa','#a34c63','#6d8341'];
   c.strokeStyle='#ddd';c.strokeRect(55,35,w-80,h-80);c.fillStyle='#334';c.fillText('Відліки',w/2,h-10);c.fillText('I/Q',5,25);
   entries.forEach(([name,points],j)=>{const lanes=mode.value==='iq',height=lanes?(h-80)/entries.length:h-80,center=lanes?35+height*(j+.5):35+height/2;const y=v=>center-v/max*height*.45,x=v=>55+(v-d.start)/(d.stop-d.start)*(w-80);c.strokeStyle=colors[j%colors.length];c.beginPath();for(const [i,lo,hi]of points){c.moveTo(x(i),y(lo));c.lineTo(x(i),y(hi));if(d.raw)c.lineTo(x(i+1),y(lo));}c.stroke();c.fillStyle=colors[j%colors.length];c.fillText(name,65+j*130,25);});
   c.fillStyle='#334';c.fillText(String(d.start),55,h-25);c.fillText(String(d.stop-1),w-95,h-25);
  }
  function position(){if(!state.summary)return;state.symbol=Number(symbolField.value);const sample=Number(sampleField.value)||state.symbol*8;if(sample<state.start||sample>=state.start+state.count)state.start=Math.max(0,Math.min(state.summary.sample_count-state.count,sample));if(state.data?.selected.start_symbol===state.symbol&&state.data.start===state.start&&state.data.stop===Math.min(state.summary.sample_count,state.start+state.count))return;load();}
  symbolField.addEventListener('change',()=>{sampleField.value=Number(symbolField.value)*8;position();});sampleField.addEventListener('change',()=>{symbolField.value=Math.floor(Number(sampleField.value)/8);position();});
  window.addEventListener('system-position',position);
  function clear(){state.pendingKey=null;++state.request;state.controller?.abort();state.summary=null;state.data=null;canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);$('system-symbol-inspector').textContent='Сигнал у цьому архіві відсутній.';}
  window.addEventListener('system-context-cleared',clear);
  window.addEventListener('scientific-summary',e=>{if(e.detail.trace_available===false){clear();return;}state.summary=e.detail;state.symbol=0;state.start=0;state.count=Math.min(160,e.detail.sample_count);load();});
  mode.onchange=()=>{cloudMode.hidden=mode.value!=='cloud';if(state.data)inspect();draw();};cloudMode.onchange=()=>{inspect();draw();};cloudMode.hidden=true;
  $('system-fit').onclick=()=>{state.scale=1;state.cx=state.cy=0;if(state.summary){state.start=0;state.count=state.summary.sample_count;load();}};
  canvas.onwheel=e=>{e.preventDefault();if(mode.value==='cloud'){state.scale*=e.deltaY>0?1.2:.8;draw();}else if(state.summary){const size=Math.max(8,Math.min(state.summary.sample_count,Math.round(state.count*(e.deltaY>0?1.5:.65))));state.start=Math.max(0,Math.min(state.summary.sample_count-size,Math.round(state.start+(state.count-size)/2)));state.count=size;load();}};
  document.getElementById('zoom-20-samples').onclick=()=>{if(!state.summary)return;state.count=Math.min(20,state.summary.sample_count);state.start=Math.max(0,Math.min(state.summary.sample_count-state.count,Number(sampleField.value)-9));load();};
  let drag=null;canvas.onpointerdown=e=>{drag={x:e.offsetX,y:e.offsetY,moved:false};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(drag){const dx=e.offsetX-drag.x,dy=e.offsetY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)drag.moved=true;if(mode.value==='cloud'&&state.transform){state.cx-=dx/state.transform.scale;state.cy+=dy/state.transform.scale;draw();}else if(state.summary)state.start=Math.max(0,Math.min(state.summary.sample_count-state.count,Math.round(state.start-dx/canvas.clientWidth*state.count)));drag.x=e.offsetX;drag.y=e.offsetY;}
   else if(state.data){const p=state.points.reduce((best,p)=>!best||Math.hypot(p.x-e.offsetX,p.y-e.offsetY)<Math.hypot(best.x-e.offsetX,best.y-e.offsetY)?p:best,null);$('system-hover').textContent=p?`Відлік ${p.sample} · I ${p.i} · Q ${p.q}`:`Відлік ${Math.floor(state.start+e.offsetX/canvas.clientWidth*state.count)}`;}};
  canvas.onpointerup=e=>{if(!drag)return;const moved=drag.moved;drag=null;if(moved){if(mode.value!=='cloud')load();return;}const point=state.points.reduce((best,p)=>!best||Math.hypot(p.x-e.offsetX,p.y-e.offsetY)<Math.hypot(best.x-e.offsetX,best.y-e.offsetY)?p:best,null);if(point)select(Math.floor(point.sample/8));};canvas.onpointercancel=()=>{drag=null;};
  window.addEventListener('resize',draw);
 });
})();
