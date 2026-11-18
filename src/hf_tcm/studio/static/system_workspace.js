/* Active B0/Joint shell. Keep compatibility nodes detached for legacy handlers. */
(() => {
  'use strict';
  window.systemOnly=true;
  window.systemNodes=new Map([...document.querySelectorAll('[id]')].map(n=>['#'+n.id,n]));
  const original=Object.fromEntries([...document.querySelectorAll('.view')].map(v=>[v.id,[...v.childNodes]]));
  const form=document.getElementById('run-form');
  const toolbar=document.querySelector('.sync-toolbar');
  const receiver=document.getElementById('global-receiver');
  const symbolField=document.getElementById('global-symbol'),sampleField=document.getElementById('global-sample');
  const stash=document.createDocumentFragment();window.systemArchive=stash;
  document.addEventListener('DOMContentLoaded',()=>{
    const routes={parameters:'Експеримент',transmitter:'Сигнал і канал',viterbi:'Декодування',metric:'Результати та ефективність',saved:'Дослідження'};
    const views=Object.fromEntries(Object.keys(routes).map(k=>[k,document.getElementById('view-'+k)]));
    for(const v of document.querySelectorAll('.view'))stash.append(...v.childNodes);
    const heading=(key)=>{const h=document.createElement('h1');h.textContent=routes[key];views[key].append(h);};
    for(const key of Object.keys(routes))heading(key);
    views.parameters.append(form);
    form.querySelector('#include-b1').checked=false;
    stash.append(form.querySelector('#include-b1').closest('label'));
    for(const key of ['transmitter','channel'])views.transmitter.append(...original['view-'+key]);
    views.viterbi.append(...original['view-viterbi']);
    views.metric.append(...original['view-comparison'],...original['view-energy']);
    views.saved.append(...original['view-saved'],...original['view-statistical']);
    for(const v of document.querySelectorAll('.view'))if(!Object.values(views).includes(v))stash.append(v);
    for(const v of Object.values(views)){
      const headings=[...v.querySelectorAll('h1')];headings.slice(1).forEach(h=>stash.append(h));
      v.querySelectorAll('p,.eyebrow,.status-pill,.notice,.status-note,.value-chip,small,.step').forEach(n=>stash.append(n));
    }
    // Remove metric-only and B1 entry points from the active route.
    for(const id of ['exp03b-saved-results','open-long-frame']){const n=document.getElementById(id);if(n)stash.append(n.closest('article')||n);}
    document.querySelectorAll('option[value=b1]').forEach(o=>o.remove());
    receiver.querySelector('[value=b1]')?.remove();receiver.value='joint';
    receiver.options[0].textContent='Joint / Евклід';receiver.options[1].textContent='B0 / Хемінг';
    const nav=document.querySelector('.tabs');nav.replaceChildren();
    const aliases={energy:'metric',comparison:'metric',statistical:'saved',channel:'transmitter',joint:'viterbi',separate:'viterbi',constellation:'transmitter'};
    function go(key){key=aliases[key]||key;if(!routes[key])key='parameters';for(const [k,v]of Object.entries(views))v.classList.toggle('active',k===key);nav.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.view===key));window.dispatchEvent(new Event('resize'));}
    for(const [key,title]of Object.entries(routes)){const b=document.createElement('button');b.type='button';b.className='tab';b.dataset.view=key;b.textContent=title;b.onclick=()=>{history.pushState(null,'','#'+key);window.dispatchEvent(new CustomEvent('scientific-navigate',{detail:key}));go(key);};nav.append(b);}
    window.addEventListener('scientific-view',e=>go(e.detail));window.addEventListener('hashchange',()=>go(location.hash.slice(1)));window.addEventListener('popstate',()=>go(location.hash.slice(1)));
    const header=document.querySelector('header');header.append(toolbar);
    toolbar.querySelector('#sync-status').textContent='Готово';
    const status=document.getElementById('job-status');header.append(status);
    const domain=document.createElement('select');domain.setAttribute('aria-label','Одиниця навігації');
    for(const [value,title]of Object.entries({symbol:'Елементи',sample:'Відліки',information:'Інформаційні біти',coded:'Кодові біти'})){const o=document.createElement('option');o.value=value;o.textContent=title;domain.append(o);}
    const index=document.createElement('input');index.type='number';index.min=0;index.value=0;index.setAttribute('aria-label','Позиція');toolbar.prepend(domain,index);
    let offset=0;
    const factor=()=>({symbol:1,sample:8,information:2,coded:3})[domain.value];
    function maximum(){const summary=window.systemSignal?.summary||window.systemDecoding?.summary;return summary?Math.max(0,(domain.value==='sample'?summary.sample_count:domain.value==='information'?summary.information_bit_count:summary.frame_symbols*factor())-1):0;}
    index.onchange=()=>{const divisor=factor(),n=Math.max(0,Math.min(maximum(),Math.floor(Number(index.value)||0)));offset=n%divisor;index.value=n;const target=domain.value==='sample'?sampleField:symbolField;target.value=domain.value==='sample'?n:Math.floor(n/divisor);target.dispatchEvent(new Event('change'));};
    const update=()=>{index.max=maximum();index.value=Math.min(maximum(),domain.value==='sample'?Number(sampleField.value):Number(symbolField.value)*factor()+offset);};domain.onchange=()=>{offset=0;update();};symbolField.addEventListener('change',update);window.addEventListener('system-position',update);
    for(const [id,delta]of [['symbol-previous',-1],['symbol-next',1]]){const old=document.getElementById(id),button=old.cloneNode(true);button.setAttribute('aria-label',delta<0?'Попередня позиція':'Наступна позиція');old.replaceWith(button);button.onclick=()=>{index.value=Math.max(0,Math.min(maximum(),Number(index.value)+delta));index.onchange();};}
    // Controls stay in the shared navigator, without duplicate position fields.
    stash.append(symbolField.closest('label'),sampleField.closest('label'));
    window.addEventListener('scientific-summary',()=>{offset=0;toolbar.hidden=false;});
    go(location.hash.slice(1)||'parameters');
  });
})();
