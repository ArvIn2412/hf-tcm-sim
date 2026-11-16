/* Shared navigation over persisted metric trials. No simulation calls. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {run:null, domain:'symbol', index:0, width:20, trace:null, timer:null};
  window.sequenceNavigator = state;
  const nav = document.createElement('section');
  nav.className='card sequence-navigator';
  nav.innerHTML=`<h2>Навігатор послідовності</h2><div class="live-controls">
    <label>Одиниця індексації<select id="seq-domain"><option value="symbol">Символ</option><option value="sample">Комплексний відлік</option><option value="information">Інформаційний біт</option><option value="coded">Кодовий біт</option><option value="trellis">Такт решітки</option></select></label>
    <label>Перейти до №<input id="seq-index" type="number" min="0" value="0"></label>
    <button id="seq-go">Перейти</button><button id="seq-first">На початок</button><button id="seq-prev">Попередній</button><button id="seq-next">Наступний</button><button id="seq-last">У кінець</button>
    <button id="seq-error-prev">Попередня помилка</button><button id="seq-error-next">Наступна помилка</button>
    <button id="seq-play">Програти / пауза</button><label>Інтервал, мс<input id="seq-speed" type="number" min="100" max="5000" value="800"></label>
    <button id="seq-in">Zoom +</button><button id="seq-out">Zoom −</button><button id="seq-reset">Скинути</button><button id="seq-export">Експорт фрагмента JSON</button>
    </div><p id="seq-status" role="status">Виконайте або відкрийте metric-дослідження.</p><input id="seq-map" type="range" min="0" max="0" value="0" aria-label="Позиція у повному кадрі"><details><summary>Інспектор точних значень</summary><pre id="seq-inspector"></pre></details>`;
  $('view-transmitter').prepend(nav);
  const style=document.createElement('style');style.textContent=`.sequence-navigator{position:sticky;top:0;z-index:8;background:var(--surface,#fff)}.sequence-navigator input[type=range]{width:100%}.sequence-navigator pre{white-space:pre-wrap;overflow-wrap:anywhere}.sequence-navigator button{min-height:36px}main{max-width:100%;width:auto}.article-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}@media(max-width:767px){.article-pair{grid-template-columns:1fr}.sequence-navigator{position:relative}.sequence-navigator .live-controls{gap:4px}.sequence-navigator h2{font-size:16px}}`;
  document.head.append(style);
  function maximum(){const t=state.trace;if(!t)return 0;return (({sample:t.total_symbols*8,information:t.payload_positions.length*2,coded:t.total_symbols*3})[state.domain]??t.total_symbols)-1;}
  function symbol(){if(state.domain==='sample')return Math.floor(state.index/8);if(state.domain==='coded')return Math.floor(state.index/3);if(state.domain==='information')return state.trace.payload_positions[Math.floor(state.index/2)];return state.index;}
  function indexFromSymbol(k){if(state.domain==='sample')return k*8;if(state.domain==='coded')return k*3;if(state.domain==='information'){const p=state.trace.payload_positions.indexOf(k);return p<0?null:p*2;}return k;}
  function update(){
    const t=state.trace;if(!t)return;
    $('seq-index').max=maximum();$('seq-index').value=state.index;
    $('seq-map').max=maximum();$('seq-map').value=state.index;
    const k=symbol(),row=k-t.start,offset=state.domain==='sample'?state.index%8:0;
    $('seq-status').textContent=`${state.run}; ${state.domain}: ${state.index} / ${maximum()}; символ ${k}; вікно ${t.start}…${t.stop-1}. Спільні observation/frontend SHA для Хемінга й Евкліда.`;
    if(row>=0&&row<t.stop-t.start){const tx=t.transmitter,s=row*8+offset,pair=t.payload_pair_indices[row];
      $('seq-inspector').textContent=JSON.stringify({symbol:k,sample:k*8+offset,kind:t.payload_mask[row]?'data':'pilot (немає інформаційного біта)',information_bits:pair<0?null:[pair*2,pair*2+1],coded_bits:tx.coded_triples[row],input:tx.input_pairs[row],tx_I:tx.tx_i[s],tx_Q:tx.tx_q[s],rx_I:tx.rx_i[s],rx_Q:tx.rx_q[s],hamming:t.arms.hamming.bits[row],euclidean:t.arms.euclidean.bits[row]},null,2);
    }
    drawWave();
  }
  function go(index){
    if(!state.trace)return;index=Number(index);
    if(!Number.isInteger(index)||index<0||index>maximum()){ $('seq-status').textContent=`Неприпустимий індекс. Допустимо 0…${maximum()}`;return; }
    state.index=index;const k=symbol(),n=state.trace.total_symbols;
    const start=Math.max(0,Math.min(n-state.width,k-Math.floor(state.width/2)));
    $('live-start').value=start;$('live-end').value=Math.min(n-1,start+state.width-1);$('live-k').value=k;
    if(k>=state.trace.start&&k<state.trace.stop&&state.trace.stop-state.trace.start===state.width){$('live-k').dispatchEvent(new Event('change'));update();}
    else $('live-update').click();
    const url=new URL(location.href);url.searchParams.set('run_id',state.run);url.searchParams.set('domain',state.domain);url.searchParams.set('index',index);url.searchParams.set('span',state.width);history.replaceState(null,'',url);
  }
  window.addEventListener('metric-trace-loaded',e=>{
    if(window.stage4){const t=e.detail,changed=state.run!==t.study_id;state.trace=t;state.run=t.study_id;if(changed){state.index=0;const u=new URL(location.href);if(u.searchParams.get('run_id')===state.run){state.domain=u.searchParams.get('domain')||'symbol';state.index=Number(u.searchParams.get('index'))||0;$('seq-domain').value=state.domain;}}return;}
    const t=e.detail,changed=state.run!==t.study_id;state.trace=t;
    if(changed){state.run=t.study_id;state.index=0;state.width=20;if(state.timer)clearInterval(state.timer);state.timer=null;const url=new URL(location.href);if(url.searchParams.get('run_id')===state.run){state.domain=url.searchParams.get('domain')||'symbol';if(!['symbol','sample','information','coded','trellis'].includes(state.domain))state.domain='symbol';state.width=Math.max(1,Math.min(80,Number(url.searchParams.get('span'))||20));state.index=Math.max(0,Math.min(maximum(),Number(url.searchParams.get('index'))||0));$('seq-domain').value=state.domain;setTimeout(()=>go(state.index),0);}}
    setTimeout(update,0);
  });
  $('seq-domain').onchange=()=>{const k=state.trace?symbol():0;state.domain=$('seq-domain').value;state.index=indexFromSymbol(k)??0;go(state.index);};
  $('seq-go').onclick=()=>go($('seq-index').value);$('seq-index').onkeydown=e=>{if(e.key==='Enter')go(e.target.value);};
  for(const [id,delta] of [['seq-prev',-1],['seq-next',1]])$(id).onclick=()=>go(Math.max(0,Math.min(maximum(),state.index+delta)));
  $('seq-first').onclick=()=>go(0);$('seq-last').onclick=()=>go(maximum());
  for(const [id,d] of [['seq-in',.5],['seq-out',2]])$(id).onclick=()=>{state.width=Math.max(1,Math.min(80,Math.round(state.width*d)));go(state.index);};
  $('seq-reset').onclick=()=>{state.width=20;go(0);};
  $('seq-play').onclick=()=>{if(state.timer){clearInterval(state.timer);state.timer=null;}else state.timer=setInterval(()=>{if(state.index>=maximum()){$('seq-play').click();return;}go(state.index+1);},Math.max(100,Number($('seq-speed').value)||800));};
  for(const [id,direction] of [['seq-error-prev',-1],['seq-error-next',1]])$(id).onclick=()=>{if(!state.trace)return;for(let k=symbol()+direction;k>=0&&k<state.trace.total_symbols;k+=direction){if(state.trace.arms.hamming.pair_error_mask[k]||state.trace.arms.euclidean.pair_error_mask[k]){const i=indexFromSymbol(k);if(i!==null){go(i);return;}}}$('seq-status').textContent='У цьому напрямку більше помилок немає.';};
  let debounce; $('seq-map').oninput=e=>{clearTimeout(debounce);debounce=setTimeout(()=>go(e.target.value),120);};
  $('seq-export').onclick=()=>{if(!state.trace)return;const u=URL.createObjectURL(new Blob([JSON.stringify({navigation:{run:state.run,domain:state.domain,index:state.index},trace:state.trace})],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=`${state.run}-${state.trace.start}-${state.trace.stop-1}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
  window.addEventListener('article-view',e=>{const target=['transmitter','constellation','viterbi'].map(v=>$('view-'+v)).find(el=>el?.classList.contains('active'));if(target)target.prepend(nav);});
  const wave=$('live-wave');let drag=null;
  function drawWave(cursor=null){
    const t=state.trace;if(!t)return;wave.height=440;const ctx=wave.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,wave.width,wave.height);
    const keys=['tx_i','tx_q','rx_i','rx_q'], colors=['#176f91','#14804a','#b33646','#7747b8'];
    const range=Math.max(1,...keys.flatMap(key=>t.transmitter[key].map(Math.abs)));
    keys.forEach((key,lane)=>{const values=t.transmitter[key],base=55+lane*100;ctx.strokeStyle=colors[lane];ctx.fillStyle=colors[lane];ctx.fillText(key.toUpperCase()+' · амплітуда',8,base-35);ctx.beginPath();values.forEach((v,i)=>{const x=35+i*(wave.width-65)/Math.max(1,values.length-1),y=base-v*32/range;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();ctx.fillStyle='#333';ctx.fillText(`${t.start*8} … ${t.stop*8-1} комплексні відліки`,wave.width-300,base+43);});
    if(cursor!==null){ctx.strokeStyle='#222';ctx.beginPath();ctx.moveTo(cursor,0);ctx.lineTo(cursor,wave.height);ctx.stroke();}
  }
  wave.addEventListener('pointermove',e=>{if(!state.trace)return;const r=wave.getBoundingClientRect(),x=(e.clientX-r.left)*wave.width/r.width;drawWave(x);const local=Math.max(0,Math.min(state.trace.transmitter.rx_i.length-1,Math.round((x-35)/(wave.width-65)*(state.trace.transmitter.rx_i.length-1))));wave.title=`відлік ${state.trace.start*8+local}; RX I=${state.trace.transmitter.rx_i[local]}; RX Q=${state.trace.transmitter.rx_q[local]}`;});
  wave.addEventListener('pointerdown',e=>{drag=e.clientX;wave.setPointerCapture(e.pointerId);});
  wave.addEventListener('pointerup',e=>{if(!state.trace||drag===null)return;const r=wave.getBoundingClientRect(),dx=e.clientX-drag;drag=null;const k=Math.abs(dx)>8?Math.round(symbol()-dx/r.width*state.width):Math.floor(state.trace.start+(e.clientX-r.left)/r.width*(state.trace.stop-state.trace.start));const i=indexFromSymbol(Math.max(0,Math.min(state.trace.total_symbols-1,k)));if(i!==null)go(i);});
  wave.addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.shiftKey)return;e.preventDefault();$(e.deltaY<0?'seq-in':'seq-out').click();},{passive:false});
})();
