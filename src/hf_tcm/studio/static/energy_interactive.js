/* Interactive views of measured energy aggregates. No statistical estimation. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const methods = [
    {key:'hamming',name:'Хемінг',color:'#bb6518'},
    {key:'joint',name:'Евклід',color:'#087f8c'},
  ];
  const state = {summary:null, status:window.metricEnergyStatus || 'NOT_RUN', charts:{}};
  window.energyInteractive = state;
  const dashboard=document.createElement('section');
  dashboard.className='energy-interactive';
  dashboard.id='energy-interactive';
  dashboard.innerHTML='<p id="energy-interactive-state" role="status">NOT_RUN — енергетична серія ще не запускалася.</p><p>Проєктна дискретна енергетична шкала γᵦ,ᵈ, дБ. Коліщатко масштабує навколо курсора; перетягування переміщує графік; Shift + перетягування виділяє прямокутник. Нульові оцінки не відображаються на логарифмічній осі.</p><div class="energy-chart-grid"></div>';
  document.querySelector('#view-metric').append(dashboard);
  const source=document.createElement('p');source.id='energy-current-source';source.textContent='Енергетичний sweep ще не відкрито.';$('energy-interactive-state').after(source);
  // Existing renderer remains available for compatible legacy exports, but the
  // visible metric charts have one owner and one set of interaction controls.
  for(const id of ['metric-ber','metric-ser']) $(id)?.closest('.metric-chart-card')?.setAttribute('hidden','');
  const css=document.createElement('style');
  css.textContent='.energy-chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.energy-chart{min-width:0}.energy-chart:last-child{grid-column:1/-1}.energy-chart canvas{display:block;width:100%;height:320px;touch-action:none;background:white}.energy-chart-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.energy-chart-controls button{min-height:44px}.energy-chart-controls label{display:flex;align-items:center;gap:5px}.energy-chart pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.energy-chart:fullscreen{overflow:auto;background:white;padding:16px}.energy-chart:fullscreen canvas{height:70vh}@media(max-width:1000px){.energy-chart-grid{grid-template-columns:minmax(0,1fr)}}';
  document.head.append(css);
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const download=(name,type,content)=>{const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.download=name;a.href=url;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const isSample=summary=>summary?.ui_run_kind==='sample'||String(summary?.configuration?.experiment_id||summary?.experiment_id||'').endsWith('-sample');
  const rows=()=>isSample(state.summary)?[]:(state.summary?.aggregates||[]).filter(r=>Number.isFinite(r.gamma_db)).slice().sort((a,b)=>a.gamma_db-b.gamma_db);
  function numeric(value){return typeof value==='number'&&Number.isFinite(value)?value:null;}
  function interval(row,kind,key){
    const candidate=row[`${kind}_ci`]?.[key] || row.confidence_intervals?.[kind]?.[key];
    return Array.isArray(candidate)&&candidate.length===2&&candidate.every(v=>numeric(v)!==null)?candidate:null;
  }
  function values(chart){
    return rows().flatMap(row=>methods.filter(m=>chart.visible[m.key]).flatMap(method=>{
      const y=numeric(row[chart.kind]?.[method.key]);
      return y===null?[]:[{x:row.gamma_db,y,row,method,ci:interval(row,chart.kind,method.key)}];
    }));
  }
  function reset(chart){
    const points=values(chart),xs=points.map(p=>p.x),ys=points.flatMap(p=>p.ci?[p.y,...p.ci]:[p.y]);
    const target=numeric(state.summary?.configuration?.target_ber);
    if(chart.kind==='ber'&&target!==null)ys.push(target);
    const valid=chart.log?ys.filter(y=>y>0):ys;
    let x0=xs.length?Math.min(...xs):0,x1=xs.length?Math.max(...xs):1;
    if(x0===x1){x0-=.5;x1+=.5;}else{const pad=(x1-x0)*.06;x0-=pad;x1+=pad;}
    let y0=valid.length?Math.min(...valid):(chart.log?.001:0),y1=valid.length?Math.max(...valid):1;
    if(chart.log){y0=Math.log10(y0);y1=Math.log10(y1);const pad=Math.max(.2,(y1-y0)*.1);y0-=pad;y1+=pad;}
    else{const pad=Math.max(.005,(y1-y0)*.12);y0=Math.max(0,y0-pad);y1=Math.min(1,y1+pad);if(y1<=y0)y1=y0+.01;}
    chart.bounds={x0,x1,y0,y1};chart.hover=null;draw(chart);
  }
  function coordinates(chart){
    const w=Math.max(280,chart.canvas.clientWidth||700),h=Math.max(240,chart.canvas.clientHeight||320);
    const left=62,right=w-18,top=24,bottom=h-48,b=chart.bounds;
    const transform=y=>chart.log?(y>0?Math.log10(y):null):y;
    const px=x=>left+(x-b.x0)/(b.x1-b.x0)*(right-left);
    const py=y=>{const v=transform(y);return v===null?null:bottom-(v-b.y0)/(b.y1-b.y0)*(bottom-top);};
    const xvalue=x=>b.x0+(x-left)/(right-left)*(b.x1-b.x0);
    const yvalue=y=>b.y0+(bottom-y)/(bottom-top)*(b.y1-b.y0);
    return {w,h,left,right,top,bottom,px,py,xvalue,yvalue};
  }
  function draw(chart){
    if(!chart.bounds)return;const c=coordinates(chart),canvas=chart.canvas,ratio=window.devicePixelRatio||1;
    canvas.width=Math.round(c.w*ratio);canvas.height=Math.round(c.h*ratio);const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);
    ctx.fillStyle='#fff';ctx.fillRect(0,0,c.w,c.h);ctx.font='12px Segoe UI, sans-serif';ctx.lineWidth=1;
    const data=values(chart);chart.points=[];
    for(let i=0;i<=4;i++){const f=i/4,y=c.top+f*(c.bottom-c.top),v=chart.bounds.y1-f*(chart.bounds.y1-chart.bounds.y0);ctx.strokeStyle='#dde6ea';ctx.beginPath();ctx.moveTo(c.left,y);ctx.lineTo(c.right,y);ctx.stroke();ctx.textAlign='right';ctx.fillStyle='#243a47';ctx.fillText(chart.log?Math.pow(10,v).toExponential(1):v.toPrecision(3),c.left-7,y+4);ctx.textAlign='center';const x=chart.bounds.x0+f*(chart.bounds.x1-chart.bounds.x0);ctx.fillText(x.toFixed(2),c.px(x),c.h-27);}
    ctx.fillText('Проєктна γᵦ,ᵈ, дБ',(c.left+c.right)/2,c.h-6);ctx.save();ctx.translate(14,(c.top+c.bottom)/2);ctx.rotate(-Math.PI/2);ctx.fillText(chart.kind.toUpperCase()+(chart.log?' · log₁₀':' · частка'),0,0);ctx.restore();
    ctx.save();ctx.beginPath();ctx.rect(c.left,c.top,c.right-c.left,c.bottom-c.top);ctx.clip();
    const target=numeric(state.summary?.configuration?.target_ber);
    if(chart.kind==='ber'&&target!==null&&c.py(target)!==null){ctx.strokeStyle='#7455a3';ctx.setLineDash([6,4]);ctx.beginPath();ctx.moveTo(c.left,c.py(target));ctx.lineTo(c.right,c.py(target));ctx.stroke();ctx.setLineDash([]);}
    for(const method of methods){if(!chart.visible[method.key])continue;ctx.strokeStyle=method.color;ctx.fillStyle=method.color;ctx.lineWidth=2;ctx.beginPath();let begun=false;for(const point of data.filter(p=>p.method.key===method.key)){const x=c.px(point.x),y=c.py(point.y);if(y===null){begun=false;continue;}begun?ctx.lineTo(x,y):ctx.moveTo(x,y);begun=true;}ctx.stroke();for(const point of data.filter(p=>p.method.key===method.key)){const x=c.px(point.x),y=c.py(point.y);if(y===null)continue;if(point.ci){const lo=c.py(point.ci[0]),hi=c.py(point.ci[1]);if(lo!==null&&hi!==null){ctx.beginPath();ctx.moveTo(x,lo);ctx.lineTo(x,hi);ctx.moveTo(x-4,lo);ctx.lineTo(x+4,lo);ctx.moveTo(x-4,hi);ctx.lineTo(x+4,hi);ctx.stroke();}}ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();if(x>=c.left&&x<=c.right&&y>=c.top&&y<=c.bottom)chart.points.push({...point,px:x,py:y});}}
    const analysis=state.summary?.gain_analysis;
    if(chart.kind==='ber'&&analysis?.observed_crossing&&target!==null){for(const method of methods){const x=numeric(analysis.required_gamma_db?.[method.key==='joint'?'joint':'separate']);if(x===null||!chart.visible[method.key]||c.py(target)===null)continue;ctx.strokeStyle=method.color;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(c.px(x),c.top);ctx.lineTo(c.px(x),c.bottom);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=method.color;ctx.beginPath();ctx.arc(c.px(x),c.py(target),6,0,Math.PI*2);ctx.fill();}}
    if(chart.brush){const [a,b]=chart.brush;ctx.fillStyle='rgba(8,127,140,.15)';ctx.fillRect(Math.min(a.x,b.x),Math.min(a.y,b.y),Math.abs(a.x-b.x),Math.abs(a.y-b.y));}
    if(chart.hover){ctx.strokeStyle='#687e8a';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(chart.hover.px,c.top);ctx.lineTo(chart.hover.px,c.bottom);ctx.moveTo(c.left,chart.hover.py);ctx.lineTo(c.right,chart.hover.py);ctx.stroke();ctx.setLineDash([]);}ctx.restore();
    if(!data.length){ctx.textAlign='left';ctx.fillStyle='#243a47';const label=isSample(state.summary)?'NOT_RUN — потрібна окрема енергетична серія.':chart.kind==='fer'?'Немає збережених FER за енергетичними точками.':'Немає виміряних точок.';ctx.fillText(label, c.left,c.top+35);}
    const zero=data.filter(p=>p.y===0).length;chart.note.textContent=`${data.length} виміряних значень; ${rows().length} енергетичних точок. ${chart.log&&zero?`${zero} нульових оцінок не можна показати на log-осі; вони збережені в таблиці/CSV.`:''} ДІ показані лише коли вони наявні у джерелі. Масштабування не змінює статистику.`;
    canvas.dataset.bounds=JSON.stringify(chart.bounds);canvas.dataset.points=String(chart.points.length);
  }
  function pointAt(chart,event){const r=chart.canvas.getBoundingClientRect();return {x:event.clientX-r.left,y:event.clientY-r.top};}
  function zoom(chart,factor,point){const c=coordinates(chart),b=chart.bounds,x=c.xvalue(point.x),y=c.yvalue(point.y);chart.bounds={x0:x+(b.x0-x)*factor,x1:x+(b.x1-x)*factor,y0:y+(b.y0-y)*factor,y1:y+(b.y1-y)*factor};draw(chart);}
  function inspector(chart,point){
    const nearest=chart.points.reduce((best,p)=>!best||Math.hypot(p.px-point.x,p.py-point.y)<Math.hypot(best.px-point.x,best.py-point.y)?p:best,null);
    if(!nearest)return;chart.hover=nearest;const {row,method}=nearest;
    const errors=chart.kind==='ber'?row.bit_errors?.[method.key]:chart.kind==='ser'?row.pair_errors?.[method.key]:row.frame_errors?.[method.key];
    const total=chart.kind==='ber'?row.bits:chart.kind==='ser'?row.pairs:row.trials;
    chart.inspector.textContent=`${method.name}: ${chart.kind.toUpperCase()} = ${nearest.y}; γᵦ,ᵈ = ${nearest.x} дБ; trials = ${row.trials ?? 'немає даних'}; помилки = ${errors ?? 'немає даних'} / ${total ?? 'немає даних'}; 95% ДІ = ${nearest.ci?JSON.stringify(nearest.ci):'не оцінено'}.`;
    draw(chart);
  }
  function csv(chart){
    const header=['gamma_project_db','metric','arm','value','errors','denominator','trials','ci_low','ci_high'];
    const lines=values(chart).map(p=>[p.x,chart.kind,p.method.name,p.y,chart.kind==='ber'?p.row.bit_errors?.[p.method.key]:chart.kind==='ser'?p.row.pair_errors?.[p.method.key]:p.row.frame_errors?.[p.method.key],chart.kind==='ber'?p.row.bits:chart.kind==='ser'?p.row.pairs:p.row.trials,p.row.trials,...(p.ci||['',''])].map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(','));
    return '\ufeff'+[header.join(','),...lines].join('\r\n');
  }
  function svg(chart){
    const c=coordinates(chart),pieces=[`<svg xmlns="http://www.w3.org/2000/svg" width="${c.w}" height="${c.h}" viewBox="0 0 ${c.w} ${c.h}"><rect width="100%" height="100%" fill="white"/><defs><clipPath id="plot"><rect x="${c.left}" y="${c.top}" width="${c.right-c.left}" height="${c.bottom-c.top}"/></clipPath></defs>`];
    pieces.push(`<text x="${c.left}" y="16" font-family="sans-serif" font-size="14">${chart.kind.toUpperCase()} · проєктна γᵦ,ᵈ, дБ · ${chart.log?'log Y':'linear Y'}</text>`);
    for(let i=0;i<=4;i++){const f=i/4,y=c.top+f*(c.bottom-c.top),v=chart.bounds.y1-f*(chart.bounds.y1-chart.bounds.y0),x=chart.bounds.x0+f*(chart.bounds.x1-chart.bounds.x0);pieces.push(`<path d="M${c.left} ${y}H${c.right}" stroke="#dde6ea"/><text x="${c.left-6}" y="${y+4}" text-anchor="end" font-size="11">${chart.log?Math.pow(10,v).toExponential(1):v.toPrecision(3)}</text><text x="${c.px(x)}" y="${c.h-25}" text-anchor="middle" font-size="11">${x.toFixed(2)}</text>`);}
    pieces.push('<g clip-path="url(#plot)">');const data=values(chart);
    const target=numeric(state.summary?.configuration?.target_ber);if(chart.kind==='ber'&&target!==null&&c.py(target)!==null)pieces.push(`<path d="M${c.left} ${c.py(target)}H${c.right}" stroke="#7455a3" stroke-dasharray="6 4"/>`);
    for(const method of methods){let d='',begun=false;for(const point of data.filter(p=>p.method.key===method.key)){const y=c.py(point.y),x=c.px(point.x);if(y===null){begun=false;continue;}d+=`${begun?'L':'M'}${x},${y}`;begun=true;pieces.push(`<circle cx="${x}" cy="${y}" r="4" fill="${method.color}"/>`);if(point.ci&&c.py(point.ci[0])!==null&&c.py(point.ci[1])!==null)pieces.push(`<path d="M${x},${c.py(point.ci[0])}V${c.py(point.ci[1])}" stroke="${method.color}"/>`);}pieces.push(`<path d="${d}" fill="none" stroke="${method.color}" stroke-width="2"/>`);}
    pieces.push('</g>');pieces.push(`<text x="${c.left}" y="${c.h-5}" font-size="12">${escape(methods.filter(m=>chart.visible[m.key]).map(m=>m.name).join(' / '))}</text></svg>`);return pieces.join('');
  }
  for(const kind of ['ber','ser','fer']){
    const card=document.createElement('article');card.className='card energy-chart';card.id=`energy-${kind}-card`;
    card.innerHTML=`<h2>${kind.toUpperCase()} — Хемінг / Евклід</h2><div class="energy-chart-controls"><label>Вісь Y<select aria-label="Шкала ${kind.toUpperCase()}" data-action="scale"><option value="linear">Лінійна</option><option value="log">Логарифмічна</option></select></label><button type="button" data-action="in">Zoom +</button><button type="button" data-action="out">Zoom −</button><button type="button" data-action="fit">Fit / Reset</button><button type="button" data-action="full">Повний екран</button>${methods.map(m=>`<label><input type="checkbox" data-method="${m.key}" checked>${m.name}</label>`).join('')}<button type="button" data-action="png">PNG</button><button type="button" data-action="svg">SVG</button><button type="button" data-action="csv">CSV</button></div><canvas id="energy-${kind}" tabindex="0" aria-label="Інтерактивний графік ${kind.toUpperCase()}"></canvas><p data-note></p><pre data-inspector aria-live="polite">Наведіть або оберіть виміряну точку.</pre>`;
    dashboard.querySelector('.energy-chart-grid').append(card);
    const chart={kind,canvas:card.querySelector('canvas'),visible:{hamming:true,joint:true},log:false,bounds:null,note:card.querySelector('[data-note]'),inspector:card.querySelector('[data-inspector]'),points:[],hover:null,pointers:new Map()};chart.canvas.id=`energy-live-${kind}`;state.charts[kind]=chart;
    card.querySelector('[data-action="scale"]').onchange=e=>{chart.log=e.target.value==='log';reset(chart);};
    for(const m of methods)card.querySelector(`[data-method="${m.key}"]`).onchange=e=>{chart.visible[m.key]=e.target.checked;draw(chart);};
    for(const [action,factor] of [['in',.65],['out',1.5]])card.querySelector(`[data-action="${action}"]`).onclick=()=>{const c=coordinates(chart);zoom(chart,factor,{x:(c.left+c.right)/2,y:(c.top+c.bottom)/2});};
    card.querySelector('[data-action="fit"]').onclick=()=>reset(chart);
    card.querySelector('[data-action="full"]').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else card.requestFullscreen?.();};
    card.querySelector('[data-action="png"]').onclick=()=>{const a=document.createElement('a');a.download=`${state.summary?.experiment_id||'energy'}-${kind}.png`;a.href=chart.canvas.toDataURL('image/png');a.click();};
    card.querySelector('[data-action="svg"]').onclick=()=>download(`${state.summary?.experiment_id||'energy'}-${kind}.svg`,'image/svg+xml;charset=utf-8',svg(chart));
    card.querySelector('[data-action="csv"]').onclick=()=>download(`${state.summary?.experiment_id||'energy'}-${kind}.csv`,'text/csv;charset=utf-8',csv(chart));
    chart.canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(chart,e.deltaY<0?.8:1.25,pointAt(chart,e));},{passive:false});
    chart.canvas.addEventListener('pointerdown',e=>{const p=pointAt(chart,e);chart.canvas.setPointerCapture(e.pointerId);chart.pointers.set(e.pointerId,p);chart.drag={origin:p,last:p,shift:e.shiftKey};});
    chart.canvas.addEventListener('pointermove',e=>{const p=pointAt(chart,e);if(!chart.pointers.has(e.pointerId)){inspector(chart,p);return;}const old=[...chart.pointers.values()];chart.pointers.set(e.pointerId,p);const now=[...chart.pointers.values()];if(now.length===2){const a=Math.hypot(old[0].x-old[1].x,old[0].y-old[1].y),b=Math.hypot(now[0].x-now[1].x,now[0].y-now[1].y);if(a>0&&b>0)zoom(chart,a/b,{x:(now[0].x+now[1].x)/2,y:(now[0].y+now[1].y)/2});return;}if(chart.drag?.shift){chart.brush=[chart.drag.origin,p];draw(chart);return;}const c=coordinates(chart),b=chart.bounds,dx=(p.x-chart.drag.last.x)/(c.right-c.left)*(b.x1-b.x0),dy=(p.y-chart.drag.last.y)/(c.bottom-c.top)*(b.y1-b.y0);chart.bounds={x0:b.x0-dx,x1:b.x1-dx,y0:b.y0+dy,y1:b.y1+dy};chart.drag.last=p;draw(chart);});
    const release=e=>{const p=pointAt(chart,e);if(chart.brush){const [a,b]=chart.brush,c=coordinates(chart);if(Math.abs(a.x-b.x)>8&&Math.abs(a.y-b.y)>8)chart.bounds={x0:c.xvalue(Math.min(a.x,b.x)),x1:c.xvalue(Math.max(a.x,b.x)),y0:c.yvalue(Math.max(a.y,b.y)),y1:c.yvalue(Math.min(a.y,b.y))};chart.brush=null;}else inspector(chart,p);chart.pointers.delete(e.pointerId);const remaining=[...chart.pointers.values()][0];chart.drag=remaining?{origin:remaining,last:remaining,shift:false}:null;draw(chart);};
    chart.canvas.addEventListener('pointerup',release);chart.canvas.addEventListener('pointercancel',()=>{chart.pointers.clear();chart.drag=null;chart.brush=null;});
    chart.canvas.onkeydown=e=>{if(e.key==='+'||e.key==='='){e.preventDefault();card.querySelector('[data-action="in"]').click();}if(e.key==='-'){e.preventDefault();card.querySelector('[data-action="out"]').click();}if(e.key==='Home'){e.preventDefault();reset(chart);}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const b=chart.bounds,dx=(b.x1-b.x0)*.1,dy=(b.y1-b.y0)*.1;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){const d=e.key==='ArrowLeft'?-dx:dx;b.x0+=d;b.x1+=d;}else{const d=e.key==='ArrowDown'?-dy:dy;b.y0+=d;b.y1+=d;}draw(chart);}};
    reset(chart);
  }
  let requestId=0,controller=null;
  window.addEventListener('metric-context-cleared',()=>{++requestId;controller?.abort();state.summary=null;state.status='NOT_RUN';source.textContent='Енергетичний sweep ще не відкрито.';$('energy-interactive-state').textContent='NOT_RUN — metric sweep для цього архівного контексту не відкрито. Сумісні архівні результати наведені окремо.';for(const chart of Object.values(state.charts))reset(chart);});
  window.addEventListener('metric-summary',async e=>{
    source.textContent=`Джерело енергетичних графіків: ${e.detail.configuration?.experiment_id||e.detail.experiment_id}; seed=${e.detail.configuration?.root_seed}; ${isSample(e.detail)?'демонстраційний кадр — sweep NOT_RUN':'збережена енергетична серія'}.`;
    state.summary=e.detail;for(const chart of Object.values(state.charts))reset(chart);
    const id=e.detail.configuration?.experiment_id||e.detail.experiment_id;
    const version=++requestId;controller?.abort();
    if(!id||isSample(e.detail))return;
    controller=new AbortController();
    try{
      const response=await fetch('/api/scientific/energy-view?'+new URLSearchParams({study_id:id}),{signal:controller.signal});
      const enriched=await response.json();if(!response.ok)throw Error(enriched.error||`HTTP ${response.status}`);
      if(version!==requestId)return;state.summary=enriched;for(const chart of Object.values(state.charts))reset(chart);
    }catch(error){if(error.name!=='AbortError'&&version===requestId)state.charts.fer.note.textContent=`FER недоступний: ${error.message}. Виміряні BER/SER залишаються доступними.`;}
  });
  window.addEventListener('metric-energy-status',e=>{state.status=e.detail.status;$('energy-interactive-state').textContent=`${e.detail.status} — ${e.detail.reason || ''}`;$('energy-interactive-state').dataset.status=state.status;});
  window.addEventListener('resize',()=>Object.values(state.charts).forEach(draw));
  document.addEventListener('fullscreenchange',()=>Object.values(state.charts).forEach(draw));
  window.addEventListener('article-view',()=>requestAnimationFrame(()=>Object.values(state.charts).forEach(draw)));
  $('mx-gain-status').textContent='NOT_RUN — енергетична серія ще не запускалася. Виконайте окремий energy sweep для побудови кривих.';
})();
