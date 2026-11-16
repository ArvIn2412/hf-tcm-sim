/* Paged metadata catalog. Numerical content is opened through verified loaders. */
(() => {
  'use strict';
  window.studyCatalogEnabled = true;
  const view = document.getElementById('view-saved');
  if (!view) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const state = {page:1, size:25, q:'', channel:'', status:'', profile:'', metric:'', kind:'', sort:'date_desc', response:null, controller:null};
  let savedScroll=0;
  window.addEventListener('scroll',()=>{if(view.classList.contains('active'))savedScroll=scrollY;},{passive:true});
  const panel = document.createElement('article');
  panel.className = 'card study-catalog';
  panel.id = 'study-catalog';
  panel.innerHTML = `<h2>Каталог збережених досліджень</h2>
    <form id="catalog-filters" class="catalog-filters">
      <label>Пошук ID, дати або seed<input id="catalog-q" type="search" maxlength="200" placeholder="ID / 2026-11 / seed"></label>
      <label>Канал<select id="catalog-channel"><option value="">Усі канали</option></select></label>
      <label>Статус<select id="catalog-status"><option value="">Усі статуси</option></select></label>
      <label>Профіль<select id="catalog-profile"><option value="">Усі профілі</option></select></label>
      <label>Тип<select id="catalog-kind"><option value="">Усі типи</option></select></label>
      <label>Метрика<select id="catalog-metric"><option value="">Усі</option><option value="hamming">Хемінг</option><option value="euclidean">Евклід</option></select></label>
      <label>Сортування<select id="catalog-sort"><option value="date_desc">Спочатку нові</option><option value="date_asc">Спочатку старі</option><option value="trials_desc">Trials за спаданням</option><option value="trials_asc">Trials за зростанням</option><option value="id_asc">ID А–Я</option><option value="id_desc">ID Я–А</option></select></label>
      <button type="submit">Застосувати</button>
    </form>
    <p id="catalog-status-text" role="status">Завантаження метаданих…</p>
    <div class="catalog-table-wrap"><table class="catalog-table"><thead><tr><th>ID / дата</th><th>Сценарій</th><th>N / seed / trials</th><th>Хемінг</th><th>Евклід</th><th>Статус</th><th>Дії</th></tr></thead><tbody id="catalog-rows"></tbody></table></div>
    <nav class="catalog-pages" aria-label="Сторінки каталогу"><button id="catalog-prev" type="button">Попередня сторінка</button><span id="catalog-page" aria-live="polite"></span><button id="catalog-next" type="button">Наступна сторінка</button><label>Записів<select id="catalog-size"><option>20</option><option selected>25</option><option>50</option></select></label></nav>
    <details id="catalog-details"><summary>Параметри вибраного дослідження</summary><pre id="catalog-parameters"></pre></details>
    <p>Каталог читає метадані. При відкритті дані перевіряє штатний manifest/SHA loader. Нульова оцінка BER не є доказом нульової істинної ймовірності помилки.</p>`;
  view.prepend(panel);
  panel.querySelector('.catalog-table-wrap').before(panel.querySelector('.catalog-pages'));
  const filterMore=document.createElement('details');filterMore.className='catalog-filter-more';filterMore.innerHTML='<summary>Фільтри та сортування</summary><div class="catalog-filters"></div>';filterMore.open=innerWidth>=768;
  for(const key of ['channel','status','profile','kind','metric','sort'])filterMore.lastElementChild.append($('catalog-'+key).closest('label'));
  $('catalog-filters').insertBefore(filterMore,$('catalog-filters').lastElementChild);
  const oldList=$('saved-runs'); if(oldList){oldList.replaceChildren();oldList.hidden=true;}
  const compatibility=document.createElement('details');compatibility.className='catalog-compatibility';compatibility.innerHTML='<summary>Додаткові архівні формати й сумісні завантажувачі</summary>';
  for(const id of ['mx-saved','energy-saved-studies']){const card=$(id)?.closest('article');if(card&&view.contains(card))compatibility.append(card);}
  if(compatibility.children.length>1)view.append(compatibility);
  const oldArchive=$('open-long-frame')?.closest('article');
  if(oldArchive){oldArchive.querySelector('h2').textContent='Архів: 20 000 символів';oldArchive.querySelector('p').textContent='Доступні збережені числові BER/SER та окрема decoder trace. Оригінальні I/Q відсутні: сузір’я не відтворюється як архівне спостереження.';}
  const style=document.createElement('style');
  style.textContent=`.catalog-filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;align-items:end}.catalog-filters label{display:flex;flex-direction:column;min-width:0}.catalog-filters input,.catalog-filters select{width:100%;box-sizing:border-box;min-width:0}.catalog-table-wrap{max-width:100%;overflow:auto}.catalog-table{width:100%;font-size:13px}.catalog-table td{overflow-wrap:anywhere;vertical-align:top}.catalog-pages{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.study-catalog button,.study-catalog input,.study-catalog select{min-height:44px}.study-catalog pre{white-space:pre-wrap;overflow-wrap:anywhere}.catalog-id{max-width:250px}.catalog-actions{display:flex;gap:6px;flex-wrap:wrap}@media(max-width:767px){.catalog-table,.catalog-table tbody,.catalog-table tr,.catalog-table td{display:block;box-sizing:border-box;min-width:0;max-width:100%}.catalog-table thead{display:none}.catalog-table tr{border:1px solid #cbd5e1;border-radius:10px;margin:10px 0;padding:10px}.catalog-table td{padding:3px 0}.catalog-table td:before{content:attr(data-label);font-weight:600;margin-right:8px}.catalog-filters{grid-template-columns:1fr}.catalog-id{max-width:100%}.catalog-table-wrap{overflow:visible}}`;
  document.head.append(style);
  function ber(row, arm){const m=row.metrics?.[arm];if(!m||m.ber===null)return 'Немає оцінки';const label=arm==='hamming'?'Хемінг':'Евклід';return `${label}: BER = ${m.ber} (${m.errors} / ${m.bits} біт)`;}
  async function refresh(){
    state.controller?.abort();state.controller=new AbortController();
    $('catalog-status-text').textContent='Завантаження сторінки…';
    try{
      const params=new URLSearchParams(Object.fromEntries(Object.entries(state).filter(([key])=>!['response','controller'].includes(key))));
      const r=await fetch('/api/scientific/study-catalog?'+params,{signal:state.controller.signal});const data=await r.json();if(!r.ok)throw Error(data.error||'Каталог недоступний');state.response=data;
      $('catalog-status-text').textContent=`Знайдено ${data.total}. Показано ${data.items.length}. Відхилено пошкоджених метаданих: ${data.rejected_metadata}. Повний історичний аудит цим списком не підтверджується.`;
      for(const key of ['channel','status','profile','kind']){const el=$('catalog-'+key),value=el.value;el.innerHTML='<option value="">Усі</option>'+data.facets[key].map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');el.value=value;}
      $('catalog-rows').innerHTML=data.items.map((row,i)=>`<tr><td data-label="ID / дата" class="catalog-id"><strong>${esc(row.id)}</strong><br>${esc(row.date)}</td><td data-label="Сценарій">${esc(row.channel)}<br>${esc(row.profile)}<br>${esc(row.kind)}</td><td data-label="Обсяг">N=${esc(row.N)}<br>seed=${esc(row.seed)}<br>trials=${esc(row.trials)}</td><td data-label="Хемінг">${esc(ber(row,'hamming'))}</td><td data-label="Евклід">${esc(ber(row,'euclidean'))}</td><td data-label="Статус">${esc(row.status)}<br>gain: ${esc(row.gain_status)}<br>${row.capabilities.iq?'I/Q доступні':'I/Q не заявлені'}</td><td><div class="catalog-actions"><button type="button" data-catalog-open="${i}">Відкрити</button><button type="button" data-catalog-detail="${i}">Деталі</button></div></td></tr>`).join('')||'<tr><td colspan="7">Збігів немає.</td></tr>';
      $('catalog-page').textContent=`Сторінка ${data.page} / ${data.pages}`;$('catalog-prev').disabled=data.page<=1;$('catalog-next').disabled=data.page>=data.pages;
      panel.querySelectorAll('[data-catalog-detail]').forEach(b=>b.onclick=()=>{const row=data.items[Number(b.dataset.catalogDetail)];$('catalog-parameters').textContent=JSON.stringify(row.parameters,null,2);$('catalog-details').open=true;});
      panel.querySelectorAll('[data-catalog-open]').forEach(b=>b.onclick=()=>open(data.items[Number(b.dataset.catalogOpen)]));
      panel.querySelectorAll('#catalog-rows tr').forEach((tr,i)=>{const row=data.items[i];if(!row)return;const details=document.createElement('details');details.className='catalog-mobile-details';details.innerHTML='<summary>Сценарій, статус і доступні дані</summary>';const p=document.createElement('p');p.textContent=`${row.channel}; ${row.profile}; ${row.status}; gain=${row.gain_status}; ${row.capabilities.iq?'I/Q доступні':'I/Q не заявлені'}`;details.append(p);tr.lastElementChild.append(details);});
    }catch(error){if(error.name!=='AbortError')$('catalog-status-text').textContent=error.message;}
  }
  let openVersion=0,openController;
  async function open(row,restore=false){
    const version=++openVersion;openController?.abort();openController=new AbortController();
    const url=new URL(location.href);if(!restore&&url.searchParams.get('run_id')!==row.id){for(const key of ['domain','index','span','start','count'])url.searchParams.delete(key);}url.searchParams.set('study_id',row.id);url.searchParams.set('study_kind',row.kind);if(row.kind==='metric')url.searchParams.set('run_id',row.id);history.replaceState(null,'',url);
    if(row.kind!=='metric'){const u=new URL(location.href);u.searchParams.delete('run_id');history.replaceState(null,'',u);window.dispatchEvent(new CustomEvent('metric-context-cleared',{detail:row}));}
    try{
      if(row.kind==='metric'){
        const response=await fetch('/api/scientific/metric-studies/'+encodeURIComponent(row.id),{signal:openController.signal});const summary=await response.json();if(!response.ok)throw Error(summary.error||'Дослідження не відкрито');if(version!==openVersion)return;
        window.dispatchEvent(new CustomEvent('catalog-metric-summary',{detail:summary}));document.querySelector('[data-view="transmitter"]').click();
      }else window.dispatchEvent(new CustomEvent('catalog-open',{detail:{kind:row.kind,id:row.id}}));
    }catch(error){if(error.name!=='AbortError'&&version===openVersion)$('catalog-status-text').textContent=error.message;}
  }
  $('catalog-filters').onsubmit=e=>{e.preventDefault();for(const key of ['q','channel','status','profile','metric','kind','sort'])state[key]=$('catalog-'+key).value;state.page=1;refresh();};
  $('catalog-prev').onclick=()=>{if(state.page>1){state.page--;refresh();}};$('catalog-next').onclick=()=>{if(state.page<(state.response?.pages||1)){state.page++;refresh();}};
  $('catalog-size').onchange=()=>{state.size=Number($('catalog-size').value);state.page=1;refresh();};
  $('refresh-runs')?.addEventListener('click',()=>refresh());
  window.addEventListener('article-view',e=>{if(e.detail==='saved'&&!state.response)refresh();});
  window.addEventListener('article-view',e=>{if(e.detail==='saved')requestAnimationFrame(()=>window.scrollTo({top:savedScroll,behavior:'instant'}));});
  window.studyCatalog={state,refresh,open};
  const url=new URL(location.href),id=url.searchParams.get('study_id'),kind=url.searchParams.get('study_kind')||'metric';
  if(id&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(id))setTimeout(()=>open({id,kind},true),0);
  refresh();
})();
