/* System B0/Joint results only. Historical values are read, never re-estimated. */
(() => {
 'use strict';
 document.addEventListener('DOMContentLoaded',()=>{
  const view=document.getElementById('view-metric');window.systemArchive.append(...view.childNodes);
  view.innerHTML='<h1>Результати та ефективність</h1><div id="system-run-results"></div><section><h2>Статистична серія</h2><div class="system-signal-tools"><select id="system-results-scenario" aria-label="Сценарій"><option value="awgn">AWGN</option><option value="static">Статична багатопроменевість</option><option value="rician">Rician</option></select><select id="system-results-target" aria-label="Ціль BER"><option>0.05</option><option>0.01</option><option>0.001</option></select><button id="system-results-open">Відкрити збережену серію</button><label>Шкала BER<select id="system-results-scale"><option value="log">Логарифмічна</option><option value="linear">Лінійна</option></select></label></div><div id="system-series-status" role="status">Статистичні результати не відкрито.</div><div id="system-ber-plot"></div><div id="system-gain"></div></section>';
  const $=id=>document.getElementById(id),model=window.systemResultsModel;
  const labels={b0:'Роздільне приймання — Хемінг',joint:'Спільне приймання — Евклід'},colors={b0:'#bb6518',joint:'#087f8c'};
  const fmt=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('uk-UA',{maximumSignificantDigits:7}):'—';
  const count=v=>Number.isSafeInteger(v)?v.toLocaleString('uk-UA'):'—';
  const state={single:null,series:null,archive:null};window.systemResults=state;
  $('system-run-results').textContent='Запуск ще не виконано.';
  function renderRun(summary){
   const result=model.single(summary);state.single=result;const parent=$('system-run-results');parent.replaceChildren();
   const columns=document.createElement('div');columns.className='system-result-columns';
   for(const key of ['b0','joint']){const r=result.arms[key],section=document.createElement('section'),h=document.createElement('h2'),ber=document.createElement('strong'),counts=document.createElement('div'),dl=document.createElement('dl');h.textContent=labels[key];ber.textContent='BER '+fmt(r.ber);ber.className='system-ber-number';counts.textContent=`${count(r.errors)} із ${count(r.bits)} інформаційних бітів`;
    for(const [title,value]of [['Час приймання всієї послідовності, с',r.time],['Час на елемент T/N, с',r.perElement],['Час на інформаційний біт T/M, с',r.perBit]]){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=title;dd.textContent=fmt(value);dl.append(dt,dd);}
    section.append(h,ber,counts,dl);if(r.errors===0){const zero=document.createElement('div');zero.textContent='Помилок не спостережено; нульова ймовірність не доведена.';section.append(zero);}
    if(r.scope!=='complete_receiver_call'){const tag=document.createElement('div');tag.textContent='Архівне вимірювання часу';section.append(tag);}columns.append(section);
   }
   const total=document.createElement('div');total.textContent=`N=${count(result.n)} · M=${count(result.m)} · Загальний час симуляції, с: ${fmt(result.total)}`;parent.append(columns,total);if(summary.trace_available===false){const note=document.createElement('div');note.textContent='Архів містить лише числові результати; сигнал і решітки відсутні.';parent.append(note);}
  }
  function draw(){if(!state.series)return;const d=model.series(state.series);const rows=d.rows.filter(r=>Number.isFinite(r.gamma_db)&&['b0','joint'].every(k=>Number.isFinite(r.ber?.[k]))).slice().sort((a,b)=>a.gamma_db-b.gamma_db);const slot=$('system-ber-plot');slot.replaceChildren();
   $('system-gain').textContent=d.gain?`Системний виграш Joint/B0 · ціль BER ${fmt(d.target)} · ${fmt(d.gain.value)} дБ · 95% ДІ [${d.gain.ci.map(fmt).join('; ')}]`:`Виграш не оцінено: ${d.reason}.`;
   if(new Set(rows.map(r=>r.gamma_db)).size<2){$('system-series-status').textContent='Недостатньо виміряних енергетичних точок.';return;}
   const log=$('system-results-scale').value==='log',ys=rows.flatMap(r=>['b0','joint'].flatMap(k=>[r.ber[k],...(r.bootstrap_95ci?.ber?.[k]||[])]));if(Number.isFinite(d.target))ys.push(d.target);const valid=ys.filter(y=>Number.isFinite(y)&&(!log||y>0));
   if(!valid.length){$('system-series-status').textContent='Нульові оцінки не відображаються на логарифмічній осі.';return;}
   const transform=v=>log?Math.log10(v):v,lo=transform(Math.min(...valid)),hi=transform(Math.max(...valid)),span=hi-lo||1,x0=rows[0].gamma_db,x1=rows.at(-1).gamma_db;
   const x=v=>75+(v-x0)/(x1-x0)*1050,y=v=>430-(transform(v)-lo)/span*380;
   const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 1200 500');svg.setAttribute('aria-label','BER Joint/B0');svg.style.width='100%';svg.style.minHeight='400px';slot.append(svg);
   function el(tag,attrs,text){const n=document.createElementNS(svg.namespaceURI,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n;}
   for(let i=0;i<=4;i++){const v=lo+span*i/4;el('text',{x:2,y:430-380*i/4,'font-size':14},fmt(log?10**v:v));el('line',{x1:75,x2:1125,y1:430-380*i/4,y2:430-380*i/4,stroke:'#ddd'});const gamma=x0+(x1-x0)*i/4;el('text',{x:x(gamma),y:458,'font-size':14},fmt(gamma));}
   el('text',{x:430,y:490,'font-size':16},'Eb/N0, дБ (дискретна модель, N0 = σ²)');
   if(Number.isFinite(d.target)&&(!log||d.target>0)){el('line',{x1:75,x2:1125,y1:y(d.target),y2:y(d.target),stroke:'#555','stroke-dasharray':'5 5'});el('text',{x:80,y:y(d.target)-8,'font-size':14},'Ціль BER '+fmt(d.target));}
   for(const key of ['b0','joint']){let path='',connected=false;for(const r of rows){const v=r.ber[key];if(log&&v===0){connected=false;continue;}path+=(connected?' L':' M')+x(r.gamma_db)+' '+y(v);connected=true;const ci=r.bootstrap_95ci?.ber?.[key];if(ci?.length===2&&ci.every(Number.isFinite)&&(!log||ci[0]>0))el('line',{x1:x(r.gamma_db),x2:x(r.gamma_db),y1:y(ci[0]),y2:y(ci[1]),stroke:colors[key],'stroke-width':2});const point=el('circle',{cx:x(r.gamma_db),cy:y(v),r:4,fill:colors[key]});const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=`${labels[key]} · BER ${v} · ${r.bit_errors?.[key]} із ${r.bits} · 95% ДІ ${ci?ci.join('…'):'відсутній'}`;point.append(title);}el('path',{d:path.trim(),stroke:colors[key],fill:'none','stroke-width':2});el('text',{x:key==='b0'?90:600,y:25,fill:colors[key],'font-size':16},labels[key]);}
   const zeros=rows.flatMap(r=>['b0','joint'].filter(k=>r.ber[k]===0)).length;$('system-series-status').textContent=`${rows.length} виміряних точок · ціль BER ${fmt(d.target)}${log&&zeros?' · нульові оцінки пропущено на log-осі':''}`;
  }
  $('system-results-open').onclick=async()=>{const button=$('system-results-open');button.disabled=true;$('system-series-status').textContent='Перевіряємо збережені дані…';try{if(!state.archive){const r=await fetch('/api/scientific/exp03b-results',{signal:AbortSignal.timeout(600000)});const d=await r.json();if(!r.ok)throw Error(d.error);state.archive=d;}state.series=model.archive(state.archive,$('system-results-scenario').value,Number($('system-results-target').value));draw();}catch(e){state.series=null;$('system-ber-plot').replaceChildren();$('system-gain').textContent='';$('system-series-status').textContent='Не вдалося відкрити серію: '+e.message;}finally{button.disabled=false;}};
  $('system-results-scale').onchange=draw;
  window.addEventListener('system-context-cleared',()=>{state.single=null;state.series=null;$('system-run-results').textContent='Доступні лише збережені числові результати серії.';$('system-ber-plot').replaceChildren();$('system-gain').textContent='';});
  window.addEventListener('scientific-summary',e=>{try{renderRun(e.detail);}catch(error){state.single=null;$('system-run-results').textContent=error.message;}});
  window.addEventListener('system-energy-summary',e=>{try{model.series(e.detail);state.series=e.detail;draw();}catch(error){state.series=null;$('system-ber-plot').replaceChildren();$('system-gain').textContent='';$('system-series-status').textContent=error.message;}});
 });
})();
