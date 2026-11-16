/* Shared presentation controls; decoder values remain unmodified. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), nav=window.sequenceNavigator;
  const bar=document.createElement('div');bar.className='live-controls';
  bar.innerHTML='<label><input id="trellis-numbers" type="checkbox">Числові підписи</label><label>Решітки<select id="trellis-arm"><option value="both">Порівняння</option><option value="hamming">Хемінг</option><option value="euclidean">Евклід</option></select></label><p>Коліщатко — спільний масштаб; drag — спільне горизонтальне переміщення; виберіть ребро для повних чисел.</p>';
  $('live-provenance').after(bar);const inspector=document.createElement('pre');inspector.id='trellis-transition';bar.after(inspector);
  const advanced=document.createElement('details');advanced.className='trellis-advanced';advanced.innerHTML='<summary>Інтервал, масштаб і діагностика решітки</summary>';bar.before(advanced);
  const original=[...bar.parentElement.children].find(e=>e.classList.contains('live-controls')&&e!==bar);
  if(original){const prose=original.nextElementSibling;advanced.append($('live-provenance'),original);if(prose?.tagName==='P')advanced.append(prose);}
  advanced.append(bar.querySelector('p'));
  const containers=['hamming','euclidean'].map(arm=>$('live-'+arm).parentElement);
  const revealed=new Map();
  function decorate(){for(const [j,arm]of ['hamming','euclidean'].entries()){const svg=$('live-'+arm);svg.querySelectorAll('text:not(.trellis-axis)').forEach(t=>{t.style.fontSize='12px';t.style.display=$('trellis-numbers').checked?'':'none';});containers[j].parentElement.hidden=$('trellis-arm').value!=='both'&&$('trellis-arm').value!==arm;
    const t=window.metricLiveTrace;if(!t)continue;svg.querySelectorAll('.trellis-axis,.trellis-selected').forEach(e=>e.remove());const width=Number(svg.getAttribute('viewBox').split(' ')[2]),dx=(width-80)/(t.stop-t.start),k=Number($('live-k').value);
    svg.insertAdjacentHTML('beforeend',Array.from({length:t.stop-t.start},(_,i)=>`<text class="trellis-axis" x="${45+(i+.3)*dx}" y="285" font-size="12">${t.start+i}</text>`).join('')+`<line class="trellis-selected" x1="${45+(k-t.start)*dx}" x2="${45+(k-t.start)*dx}" y1="15" y2="265" stroke="#ba7311" stroke-dasharray="4 3"/>`);
    const signature=[t.study_id,t.start,t.stop,k,width].join(':');if(containers[j].clientWidth&&revealed.get(arm)!==signature){containers[j].scrollLeft=Math.max(0,45+(k-t.start)*dx-containers[j].clientWidth/2);revealed.set(arm,signature);}
  }}
  for(const id of ['trellis-numbers','trellis-arm'])$(id).onchange=decorate;
  for(const [j,el]of containers.entries()){
    const arm=['hamming','euclidean'][j];el.tabIndex=0;el.style.touchAction='pan-y';
    let drag;
    el.addEventListener('wheel',e=>{e.preventDefault();const z=$('live-zoom');z.value=Math.max(.5,Math.min(4,Number(z.value)*(e.deltaY<0?1.25:.8)));z.dispatchEvent(new Event('change'));decorate();},{passive:false});
    el.onpointerdown=e=>{drag={x:e.clientX,left:el.scrollLeft};e.target.setPointerCapture?.(e.pointerId);};
    el.onpointermove=e=>{if(drag)containers.forEach(c=>c.scrollLeft=drag.left+drag.x-e.clientX);};
    el.onpointerup=e=>{if(drag&&Math.abs(e.clientX-drag.x)<5){const r=$('live-'+arm).getBoundingClientRect(),t=window.metricLiveTrace;if(t){const width=Number($('live-'+arm).getAttribute('viewBox').split(' ')[2]);const k=Math.max(t.start,Math.min(t.stop-1,t.start+Math.floor(((e.clientX-r.left)*width/r.width-45)/((width-80)/(t.stop-t.start)))));nav.domain='symbol';$('seq-domain').value='symbol';nav.go(k);}}drag=null;};el.onpointercancel=()=>drag=null;
    el.addEventListener('click',e=>{const path=e.target.closest('path'),t=window.metricLiveTrace;if(!path||!t)return;const title=path.querySelector('title')?.textContent,match=/k=(\d+); edge=(\d+)/.exec(title||'');if(!match)return;const k=Number(match[1]),edge=Number(match[2]),row=k-t.start,transition=t.edges[edge],target=t.states.findIndex(s=>s.join()===transition[4].join());inspector.textContent=JSON.stringify({run_id:t.study_id,arm,k,edge,transition,branch_metric:t.arms[arm].branch_metrics[row][edge],accumulated_target_metric:t.arms[arm].state_metrics[row+1][target],survivor:t.arms[arm].survivors[row][target]===edge,decision:t.arms[arm].decisions[row]},null,2);});
  }
  $('live-k').addEventListener('change',()=>{nav.domain='symbol';$('seq-domain').value='symbol';nav.go(Number($('live-k').value));});
  $('live-update').addEventListener('click',e=>{if(e.isTrusted){const first=Number($('live-start').value),last=Number($('live-end').value);if(Number.isInteger(first)&&Number.isInteger(last)&&last>=first&&last-first<80)nav.setRange(first*8,(last-first+1)*8,Number($('live-k').value)*8);}});
  window.addEventListener('metric-trace-loaded',()=>setTimeout(decorate,0));window.addEventListener('article-view',()=>setTimeout(decorate,0));$('live-zoom').addEventListener('change',decorate);
})();
