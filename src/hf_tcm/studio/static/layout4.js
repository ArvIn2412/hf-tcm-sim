/* Accessible responsive controls. Data and scientific results stay in their owners. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const topbar=document.querySelector('.topbar');
  const menu=document.createElement('select');menu.className='mobile-view-menu';menu.setAttribute('aria-label','Вкладка лабораторії');
  for(const tab of document.querySelectorAll('.tabs .tab')){const option=document.createElement('option');option.value=tab.dataset.view;option.textContent=tab.textContent;menu.append(option);}
  menu.addEventListener('change',()=>document.querySelector(`.tab[data-view="${menu.value}"]`)?.click());topbar?.append(menu);
  window.addEventListener('article-view',event=>{menu.value=event.detail;});
  menu.value=document.querySelector('.tabs .tab.active')?.dataset.view||'parameters';
  window.addEventListener('metric-context-cleared',e=>{const title=document.querySelector('.source-summary > summary');if(title)title.textContent=`Поточний архів: ${e.detail.id}`;});
  const nav=document.querySelector('.sequence-navigator'), primary=nav.querySelector('.live-controls');
  const more=document.createElement('details');more.className='navigator-more';more.innerHTML='<summary>Додаткові дії та огляд кадру</summary><div class="live-controls"></div>';
  for(const id of ['seq-first','seq-last','seq-error-prev','seq-error-next','seq-play','seq-speed','seq-export','seq-reset']){const el=$(id);more.lastElementChild.append(el.closest('label')||el);}
  primary.after(more);for(const el of [...nav.children])if(el!==more&&el!==primary&&el.tagName!=='H2'&&el.id!=='seq-status')more.append(el);
  const source=$('metric-active-source');if(source){const details=document.createElement('details');details.className='card source-summary';const title=document.createElement('summary');title.textContent='Поточний результат: ще не відкрито';source.before(details);details.append(title,source);source.classList.remove('card');const utility=document.querySelector('.utility-buttons');if(utility)details.append(utility);window.addEventListener('metric-trace-loaded',e=>{title.textContent=`Поточний результат: N=${e.detail.total_symbols}; seed=${e.detail.configuration.root_seed}`;});}
  for(const[id,label]of [['seq-go','↵'],['seq-prev','←'],['seq-next','→'],['seq-in','+'],['seq-out','−'],['seq-reset','↺']]){const b=$(id);b.title=b.textContent;b.setAttribute('aria-label',b.textContent);b.textContent=label;}
  const extension=$('energy-extension');if(extension){const details=document.createElement('details');details.innerHTML='<summary>Додаткова енергетична серія</summary>';extension.before(details);details.append(extension);}
  const intro=$('view-parameters').firstElementChild;
  if(intro){const details=document.createElement('details');details.innerHTML='<summary>Профіль, джерела та методологічні обмеження</summary>';for(const el of [...intro.children])if(el.tagName!=='H1'&&!el.contains($('article-profile')))details.append(el);intro.append(details);}
  const form=$('metric-study-form');
  if(form){
    const runbar=document.createElement('div');runbar.className='stage4-runbar';runbar.setAttribute('aria-label','Керування наступним запуском');
    for(const id of ['article-profile','mx-id','article-mode','mx-trials','article-sweep','mx-run','mx-stop']){const node=$(id);if(node)runbar.append(node.closest('label')||node);}
    // Buttons can be anonymous; move their existing nodes, preserving listeners.
    for(const button of form.querySelectorAll('button[type="submit"],button#mx-stop'))if(!runbar.contains(button))runbar.append(button);
    form.prepend(runbar);
    const summary=document.createElement('p');summary.className='stage4-form-summary';summary.setAttribute('aria-live','polite');runbar.after(summary);
    const refresh=()=>{const n=$('mx-frame')?.value||'—',seed=$('mx-seed')?.value||'—',trials=$('mx-trials')?.value||'1',points=($('mx-grid')?.value||'').split(',').filter(x=>x.trim()).length,sweep=$('article-sweep')?.checked;summary.textContent=`Наступний запуск: N=${n} символів; seed=${seed}; N_trials=${trials}. Кошторис: ${trials} демонстраційних кадрів${sweep?` + ${points} енергетичних точок × ${trials} кадрів`:''}. Поточний результат має власні параметри у шапці джерела.`;};
    const indicate=()=>{refresh();const t=window.metricLiveTrace;if(!t)return;const changed=String(t.configuration.root_seed)!==$('mx-seed').value||String(t.total_symbols)!==$('mx-frame').value||t.configuration.scenario!==$('mx-scenario').value||String(t.amplitude)!==$('mx-amplitude').value;summary.dataset.changed=String(changed);summary.textContent+=changed?' Увага: параметри форми відрізняються від поточного результату.':' Основні параметри збігаються з поточним результатом.';const frames=Number($('mx-trials').value)*(1+($('article-sweep').checked?$('mx-grid').value.split(',').filter(x=>x.trim()).length:0));summary.textContent+=` Усього: ${frames} кадрів, ${frames*Number($('mx-frame').value)} символьних інтервалів.`;};
    form.addEventListener('input',indicate);form.addEventListener('change',indicate);window.addEventListener('metric-trace-loaded',indicate);indicate();
    for(const fieldset of form.querySelectorAll('.parameter-group'))for(const label of fieldset.querySelectorAll('label')){const help=label.querySelector('small');if(help){const details=document.createElement('details');details.className='parameter-explanation';const title=document.createElement('summary');title.textContent='Джерело та допустимі значення';details.append(title,help);label.append(details);}}
    for(const fieldset of [...form.querySelectorAll('.parameter-group')].slice(1)){const details=document.createElement('details');details.className='parameter-section';details.innerHTML='<summary>'+fieldset.querySelector('legend').textContent+'</summary>';details.open=innerWidth>=768;fieldset.before(details);details.append(fieldset);}
    matchMedia('(min-width: 768px)').addEventListener('change',e=>document.querySelectorAll('.parameter-section,.wave-tools,.catalog-filter-more').forEach(d=>d.open=e.matches));
  }
})();
