/* XY presentation over the same persisted window as the signal inspector. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), nav=window.sequenceNavigator;
  const old=$('received-cloud'), canvas=old.cloneNode(true);old.replaceWith(canvas);
  $('cloud-zoom').closest('.live-controls').hidden=true;
  canvas.tabIndex=0;canvas.setAttribute('aria-label','Сузір’я I/Q: коліщатко, drag, Shift+drag, стрілки, +/−');
  const controls=document.createElement('details');controls.className='cloud-tools';
  controls.innerHTML='<summary>Фільтри та керування сузір’ям</summary><div class="live-controls"><label>Передана фаза<select id="xy-phase"><option value="">Усі фази</option>'+Array.from({length:8},(_,i)=>`<option value="${i}">${i}π/4</option>`).join('')+'</select></label><label><input type="checkbox" id="xy-ideal" checked>Ідеальні точки</label><label><input type="checkbox" id="xy-errors" checked>Помилки рішення</label><label><input type="checkbox" id="xy-vectors" checked>Вектори зміщення</label><button id="xy-in">Zoom +</button><button id="xy-out">Zoom −</button><button id="xy-fit">Fit / Reset</button><button id="xy-full">Повний екран</button></div>';
  canvas.before(controls);const inspector=document.createElement('pre');inspector.id='xy-inspector';inspector.setAttribute('aria-live','polite');canvas.after(inspector);
  const state={cx:0,cy:0,span:3,points:[],selected:null,brush:null,pointers:new Map()};window.constellationView=state;
  let geometry;
  function draw(){
    const w=Math.max(250,Math.round(canvas.clientWidth||700)),h=Math.round(Math.min(w*.8,620));canvas.width=w;canvas.height=h;
    const ctx=canvas.getContext('2d'), scale=(Math.min(w,h)-70)/state.span,x=v=>w/2+(v-state.cx)*scale,y=v=>h/2-(v-state.cy)*scale;
    geometry={w,h,scale,x,y};ctx.fillStyle='white';ctx.fillRect(0,0,w,h);ctx.font='12px sans-serif';
    ctx.strokeStyle='#b4c2c8';ctx.beginPath();ctx.moveTo(0,y(0));ctx.lineTo(w,y(0));ctx.moveTo(x(0),0);ctx.lineTo(x(0),h);ctx.stroke();
    ctx.fillStyle='#203645';ctx.fillText('I',w-20,Math.max(15,Math.min(h-5,y(0)-6)));ctx.fillText('Q',Math.max(10,Math.min(w-15,x(0)+6)),15);
    for(let i=0;i<=4;i++){const v=state.cx+(i/4-.5)*state.span;ctx.fillText(v.toPrecision(3),x(v),h-10);const q=state.cy+(i/4-.5)*state.span;ctx.fillText(q.toPrecision(3),4,y(q));}
    const d=nav.data,A=d?.amplitude??window.metricLiveTrace?.amplitude??1;
    if($('xy-ideal').checked)for(let phase=0;phase<8;phase++){const a=phase*Math.PI/4;ctx.strokeStyle='#243b4a';ctx.beginPath();ctx.arc(x(A*Math.cos(a)),y(A*Math.sin(a)),5,0,7);ctx.stroke();ctx.fillText(String(phase),x(A*Math.cos(a))+7,y(A*Math.sin(a))-7);}
    state.points=[];const mode=$('cloud-mode').value,filter=$('xy-phase').value;
    const processedSymbols=new Set();
    const layers=mode==='both'?[false,true]:mode==='ideal'?[]:[mode==='processed'];
    for(const processed of layers)for(const p of d?.cloud||[]){if(filter!==''&&p.phase!==Number(filter))continue;if(processed){if(processedSymbols.has(p.symbol))continue;processedSymbols.add(p.symbol);}const i=processed?p.fi:p.i,q=processed?p.fq:p.q,px=x(i),py=y(q);if(px<0||px>w||py<0||py>h)continue;
      if($('xy-vectors').checked&&state.points.length<100){ctx.strokeStyle='#64748b30';ctx.beginPath();ctx.moveTo(x(A*Math.cos(p.phase*Math.PI/4)),y(A*Math.sin(p.phase*Math.PI/4)));ctx.lineTo(px,py);ctx.stroke();}
      ctx.fillStyle=`hsl(${p.phase*45},70%,40%)`;if(processed){ctx.strokeStyle=ctx.fillStyle;ctx.strokeRect(px-3,py-3,6,6);}else{ctx.beginPath();ctx.arc(px,py,2,0,7);ctx.fill();}if(processed&&$('xy-errors').checked&&p.hard_error){ctx.strokeStyle='#d92336';ctx.strokeRect(px-4,py-4,8,8);}state.points.push({...p,sample:processed?p.symbol*8:p.sample,i,q,x:px,y:py,processed});
    }
    if(state.brush){const[a,b]=state.brush;ctx.fillStyle='#087f8c30';ctx.fillRect(Math.min(a.x,b.x),Math.min(a.y,b.y),Math.abs(a.x-b.x),Math.abs(a.y-b.y));}
    $('cloud-info').textContent=d?.cloud?`${d.run_id}; seed=${d.seed}; ${state.points.length} точок поточного інтервалу. I/Q мають однаковий масштаб. Кружки — RX, квадрати — frontend; колір — TX фаза; червоне — hard-decision error frontend. Виберіть точку для переходу до інспектора.`:'Ідеальні точки. Відкрийте запуск із фактичними I/Q.';
    canvas.dataset.bounds=JSON.stringify({cx:state.cx,cy:state.cy,span:state.span,scaleX:scale,scaleY:scale});canvas.dataset.exportRendered='true';
  }
  const point=e=>{const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height};};
  function zoom(f,p={x:canvas.width/2,y:canvas.height/2}){const g=geometry;if(!g)return;const i=state.cx+(p.x-g.w/2)/g.scale,q=state.cy-(p.y-g.h/2)/g.scale;state.cx=i+(state.cx-i)*f;state.cy=q+(state.cy-q)*f;state.span=Math.max(.0001,Math.min(1e6,state.span*f));draw();}
  function fit(){state.cx=state.cy=0;state.span=Math.max(2.8,...(nav.data?.cloud||[]).flatMap(p=>[Math.abs(p.i)*2.3,Math.abs(p.q)*2.3,Math.abs(p.fi)*2.3,Math.abs(p.fq)*2.3]));draw();}
  function nearest(p){return state.points.reduce((best,v)=>!best||Math.hypot(v.x-p.x,v.y-p.y)<Math.hypot(best.x-p.x,best.y-p.y)?v:best,null);}
  function inspect(p){const v=nearest(p);if(v)inspector.textContent=`Відлік ${v.sample}; символ ${v.symbol}; I=${v.i}; Q=${v.q}; TX фаза=${v.phase}π/4; pilot=${v.pilot}; hard error=${v.hard_error}; Хемінг=${v.hamming}; Евклід=${v.euclidean}`;return v;}
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY<0?.8:1.25,point(e));},{passive:false});
  canvas.onpointerdown=e=>{const p=point(e);canvas.setPointerCapture(e.pointerId);state.pointers.set(e.pointerId,p);state.drag={origin:p,last:p,shift:e.shiftKey,moved:false};};
  canvas.onpointermove=e=>{const p=point(e);if(!state.pointers.has(e.pointerId)){inspect(p);return;}const old=[...state.pointers.values()];state.pointers.set(e.pointerId,p);const now=[...state.pointers.values()];if(now.length===2){const a=Math.hypot(old[0].x-old[1].x,old[0].y-old[1].y),b=Math.hypot(now[0].x-now[1].x,now[0].y-now[1].y);if(a&&b)zoom(a/b,{x:(now[0].x+now[1].x)/2,y:(now[0].y+now[1].y)/2});state.drag.moved=true;return;}const drag=state.drag;if(!drag)return;drag.moved ||= Math.hypot(p.x-drag.origin.x,p.y-drag.origin.y)>5;if(drag.shift)state.brush=[drag.origin,p];else{state.cx-=(p.x-drag.last.x)/geometry.scale;state.cy+=(p.y-drag.last.y)/geometry.scale;}drag.last=p;draw();};
  canvas.onpointerup=e=>{const p=point(e),drag=state.drag;if(state.brush){const[a,b]=state.brush;if(Math.abs(a.x-b.x)>5&&Math.abs(a.y-b.y)>5){state.cx+=((a.x+b.x)/2-geometry.w/2)/geometry.scale;state.cy-=((a.y+b.y)/2-geometry.h/2)/geometry.scale;state.span=Math.max(Math.abs(a.x-b.x),Math.abs(a.y-b.y))/geometry.scale;}state.brush=null;}else if(drag&&!drag.moved){const v=inspect(p);if(v){state.selected=v;nav.domain='sample';$('seq-domain').value='sample';nav.go(v.sample);}}state.pointers.delete(e.pointerId);const remaining=[...state.pointers.values()][0];state.drag=remaining?{origin:remaining,last:remaining,shift:false,moved:true}:null;draw();};
  canvas.onpointercancel=()=>{state.pointers.clear();state.drag=null;state.brush=null;};
  $('xy-in').onclick=()=>zoom(.5);$('xy-out').onclick=()=>zoom(2);$('xy-fit').onclick=fit;$('xy-full').onclick=()=>document.fullscreenElement?document.exitFullscreen():$('view-constellation').requestFullscreen?.();
  for(const id of ['xy-phase','xy-ideal','xy-errors','xy-vectors','cloud-mode'])$(id).addEventListener('change',draw);
  canvas.onkeydown=e=>{if(['+','-','Home','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='+')zoom(.5);else if(e.key==='-')zoom(2);else if(e.key==='Home')fit();else{state.cx+=e.key==='ArrowLeft'?-state.span*.1:e.key==='ArrowRight'?state.span*.1:0;state.cy+=e.key==='ArrowDown'?-state.span*.1:e.key==='ArrowUp'?state.span*.1:0;draw();}}};
  let run=null;window.addEventListener('lab-window',()=>{if(run!==nav.run){run=nav.run;fit();}else draw();});
  window.addEventListener('metric-trace-loaded',()=>setTimeout(draw,0));window.addEventListener('article-view',()=>requestAnimationFrame(draw));window.addEventListener('resize',draw);document.addEventListener('fullscreenchange',draw);draw();
  window.addEventListener('metric-context-cleared',()=>{run=null;state.selected=null;inspector.textContent='Для цього архіву metric I/Q не завантажені.';setTimeout(fit,0);});
})();
