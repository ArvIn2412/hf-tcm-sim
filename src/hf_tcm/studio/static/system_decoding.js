/* B0 and Joint finite-depth traces: decisions are never inferred from local paths. */
(() => {
 'use strict';
 document.addEventListener('DOMContentLoaded',()=>{
  const view=document.getElementById('view-viterbi');window.systemArchive.append(...view.childNodes);
  view.innerHTML='<h1>Декодування</h1><div class="system-trellises"></div><div id="system-edge-inspector" aria-live="polite">Оберіть перехід.</div>';
  const state={summary:null,tick:0,traces:null,selection:null,version:0,controller:null};window.systemDecoding=state;
  const symbol=window.systemNodes.get('#global-symbol'),receiver=document.getElementById('global-receiver');
  const arms=[['b0','Роздільне приймання — Хемінг','#bb6518'],['joint','Спільне приймання — Евклід','#087f8c']];
  const surfaces={};let scrolling=false;
  for(const [arm,title]of arms){const section=document.createElement('section'),h=document.createElement('h2'),scroll=document.createElement('div'),svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),decision=document.createElement('p');h.textContent=title;scroll.className='system-trellis-scroll';svg.id='system-trellis-'+arm;svg.setAttribute('aria-label',title);scroll.append(svg);section.append(h,scroll,decision);view.querySelector('.system-trellises').append(section);surfaces[arm]={svg,scroll,decision};scroll.onscroll=()=>{if(scrolling)return;scrolling=true;for(const [key,s]of Object.entries(surfaces))if(key!==arm)s.scroll.scrollLeft=scroll.scrollLeft;scrolling=false;};}
  const node=(edge,side,arm)=>Number(edge[arm==='joint'?side+'_node_id':side+'_state_id']);
  const fmt=v=>v===null?'∞':typeof v==='number'?Number.isFinite(v)?v.toLocaleString('uk-UA',{maximumSignificantDigits:7}):'∞':'—';
  function pick(arm,edge,tick){state.selection={arm,edge:edge.edge_id,base:edge.base_edge_id??edge.edge_id};receiver.value=arm;receiver.dispatchEvent(new Event('change'));symbol.value=tick;symbol.dispatchEvent(new Event('change'));window.dispatchEvent(new CustomEvent('system-position',{detail:{symbol:tick,sample:tick*8}}));if(tick===state.tick&&state.traces)render();}
  function render(){if(!state.traces)return;
   const inspector=[];
   for(const [arm,,color]of arms){const trace=state.traces[arm],surface=surfaces[arm];surface.svg.replaceChildren();if(!trace.available){surface.decision.textContent='Діагностика цього приймача відсутня в архіві.';continue;}
    const graph=trace.transitions,steps=trace.traceback_steps,states=trace.state_metrics.length;
    const width=Math.max(900,steps.length*92+90),height=Math.max(320,states*28+60),x=i=>65+i*(width-90)/steps.length,y=i=>35+i*(height-70)/Math.max(1,states-1);
    surface.svg.setAttribute('width',width);surface.svg.setAttribute('height',height);
    function el(tag,attributes,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attributes))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;surface.svg.append(n);return n;}
    const local=new Map(trace.traceback_local_survivor_path.map(e=>[e.symbol_index,e.edge_id]));
    const matching=state.selection?graph.filter(e=>state.selection.arm===arm?e.edge_id===state.selection.edge:(e.base_edge_id??e.edge_id)===state.selection.base):[];const selected=matching.length===1?matching[0]:null;
    for(let i=0;i<steps.length;i++){
     const step=steps[i],survivors=new Set(step.survivor_edge_ids_by_destination);
     for(const edge of graph){const onPath=local.get(step.symbol_index)===edge.edge_id,survivor=survivors.has(edge.edge_id),active=selected?.edge_id===edge.edge_id&&step.symbol_index===state.tick;
      const path=el('path',{d:`M${x(i)} ${y(node(edge,'source',arm))} L${x(i+1)} ${y(node(edge,'target',arm))}`,stroke:onPath?color:active?'#222':survivor?'#899ba5':'#dce3e7','stroke-width':active?4:onPath?3:survivor?1.5:1,opacity:onPath||survivor||active?1:.35,fill:'none','data-edge':edge.edge_id,'data-tick':step.symbol_index,'data-survivor':survivor,'data-path':onPath,'data-selected':active,tabindex:0,role:'button','aria-label':`Такт ${step.symbol_index}, перехід ${edge.edge_id}`});
      const title=document.createElementNS(path.namespaceURI,'title');title.textContent=`${step.symbol_index}: ${node(edge,'source',arm)} → ${node(edge,'target',arm)} · branch ${fmt(step.branch_metrics[edge.edge_id])}`;path.append(title);path.onclick=()=>pick(arm,edge,step.symbol_index);path.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(arm,edge,step.symbol_index);}};
     }
     el('text',{x:x(i),y:height-8,'font-size':14,fill:'#334'},String(step.symbol_index));
    }
    for(let i=0;i<=steps.length;i++)for(let j=0;j<states;j++)el('circle',{cx:x(i),cy:y(j),r:3,fill:'#435b69'});
    for(let j=0;j<states;j++){const n=state.summary.trellises?.[arm==='joint'?'joint':'encoder_a']?.nodes?.[j];const encoder=n?.encoder_state??graph.find(e=>e.source_state_id===j)?.source_state;el('text',{x:2,y:y(j)+4,'font-size':14,fill:'#334'},`S${j}${encoder?' '+encoder.join(''):''}`);}
    const decision=trace.emitted_decision_for_selected_symbol,arrival=trace.emitted_decision_on_this_arrival;
    const edge=decision?graph.find(e=>e.edge_id===decision.edge_id):null;
    surface.decision.textContent=decision?`Збережені декодовані біти для k=${decision.symbol_index}: ${edge?.input_pair?.join('')??'—'} · ${decision.decision_available_at>trace.symbol_index?'ще не видано на вибраному такті; ':''}видано при k=${decision.decision_available_at}, глибина ${decision.traceback_depth_used}.`:'Рішення для вибраного символу відсутнє.';
    if(arrival)surface.decision.textContent+=` Запис видачі на цьому такті: символ ${arrival.symbol_index}, перехід ${arrival.edge_id}, глибина ${arrival.traceback_depth_used}.`;
    surface.decision.textContent+=` Traceback: ${trace.traceback_local_survivor_path.map(e=>e.edge_id).join(' → ')}. Кінцевий стан S${trace.endpoint_state_id}, path metric ${fmt(trace.endpoint_metric)}.`;
    if(selected){const step=steps.at(-1),target=node(selected,'target',arm);inspector.push(`${arm==='b0'?'Хемінг':'Евклід'} · ${node(selected,'source',arm)} → ${target} · біти ${selected.input_pair.join('')} → ${selected.coded_triple.join('')} · branch metric ${fmt(step.branch_metrics[selected.edge_id])} · path metric стану S${target} ${fmt(step.state_metrics[target])} · ${step.survivor_edge_ids_by_destination[target]===selected.edge_id?'survivor':'відхилено'}`);}
   }
   document.getElementById('system-edge-inspector').textContent=inspector.join(' | ')||'Оберіть перехід.';
  }
  async function load(){if(!state.summary)return;if(state.traces?.b0.run_id===state.summary.run_id&&state.traces.b0.symbol_index===Number(symbol.value)&&state.traces.joint.symbol_index===Number(symbol.value))return;const version=++state.version;state.controller?.abort();state.controller=new AbortController();state.tick=Number(symbol.value)||0;
   try{const values=await Promise.all(arms.map(async([arm])=>{const q=new URLSearchParams({run_id:state.summary.run_id,receiver:arm,symbol:state.tick,depth:20});const r=await fetch('/api/scientific/viterbi?'+q,{signal:state.controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error);return [arm,d];}));if(version!==state.version)return;state.traces=Object.fromEntries(values);render();}
   catch(e){if(e.name!=='AbortError'){state.traces=null;for(const s of Object.values(surfaces)){s.svg.replaceChildren();s.decision.textContent='Не вдалося завантажити решітку: '+e.message;}}}}
  let timer;const schedule=()=>{clearTimeout(timer);timer=setTimeout(load,30);};
  symbol.addEventListener('change',schedule);window.systemNodes.get('#global-sample').addEventListener('change',schedule);window.addEventListener('system-position',schedule);
  function clear(){++state.version;state.controller?.abort();state.summary=null;state.traces=null;for(const s of Object.values(surfaces)){s.svg.replaceChildren();s.decision.textContent='Решітка у цьому архіві відсутня.';}}
  window.addEventListener('system-context-cleared',clear);
  window.addEventListener('scientific-summary',e=>{if(e.detail.trace_available===false){clear();return;}state.summary=e.detail;state.selection=null;symbol.value=0;schedule();});
 });
})();
