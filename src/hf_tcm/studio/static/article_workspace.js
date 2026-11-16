(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const titles = ['Налаштування і запуск', 'Передавач і канал', 'Сузір’я 8PSK', 'Декодування та решітка Вітербі', 'Порівняння та енергетичний виграш', 'Збережені дослідження'];
  document.querySelectorAll('.tab').forEach((el, i) => { el.textContent = titles[i]; });
  $('#view-constellation h1').textContent = titles[2];
  $('#view-constellation > p').textContent = 'Спільний прийнятий сигнал: спотворення каналу та рішення декодера показуються окремо.';
  [...$('#cloud-mode').options].forEach((el,i)=>el.textContent=['Порівняння','Ідеальне','Після каналу'][i]);
  const groups = {parameters:['parameters'],transmitter:['transmitter'],constellation:['constellation'],viterbi:['viterbi'],metric:['metric'],saved:['saved']};
  const aliases = Object.fromEntries(Object.entries(groups).flatMap(([key, values]) => values.map(v => [v,key])));
  Object.assign(aliases,{channel:'transmitter',joint:'viterbi',separate:'viterbi',energy:'metric',comparison:'metric',statistical:'metric'});
  function navigate(name) {
    const key = aliases[name] || 'parameters';
    document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', groups[key].includes(el.id.replace('view-',''))));
    document.querySelectorAll('.tab').forEach(el => {el.classList.toggle('active',el.dataset.view===key);el.setAttribute('aria-selected',String(el.dataset.view===key));});
    window.dispatchEvent(new Event('resize'));
    drawCloud();
    if(name!==key){const detail=document.getElementById('view-'+name)?.closest('details');if(detail)detail.open=true;}
    window.dispatchEvent(new CustomEvent('article-view',{detail:key}));
  }
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click',()=>{if(location.hash!=='#'+b.dataset.view)history.pushState(null,'','#'+b.dataset.view);navigate(b.dataset.view);}));
  const start = $('#view-parameters');
  const intro = document.createElement('article'); intro.className='card';
  intro.innerHTML=`<h1>Налаштування і запуск</h1><label>Профіль (P)<select id="article-profile"><option value="article">За науковою статтею</option><option value="archive">SCIENTIFIC-EXP-03B (архівний, лише перегляд)</option><option value="custom">Власний експеримент</option></select></label><p id="profile-origin"></p><p>Спільні вхідні дані: одна послідовність, канал, шум, ReceiverObservation та frontend; A-H / A-E відрізняються метрикою.</p><p>n = 8 відліків/символ; η = 20 переходів; M = 8; Δφ = π/4 рад; R = 2/3; p*п = 0,05 (джерельна помилка елемента, не BER). Джерело: код (9,6); тотожність Encoder A потребує доказу mapping.</p><button type="button" id="restore-article">Відновити останні налаштування</button>`;
  start.prepend(intro);
  const form = $('#metric-study-form'); start.append(form);
  const old = document.createElement('details');old.innerHTML='<summary>Додаткове: порівняння архітектур Joint / B0 / B1 — різні frontend та CSI</summary>';old.append($('#run-form'));start.append(old);
  const mode = document.createElement('div'); mode.className='card';mode.innerHTML='<label>Режим запуску (mode)<select id="article-mode"><option value="single">Одиничний</option><option value="multiple">Багаторазовий (Monte Carlo)</option></select></label><label><input type="checkbox" id="article-sweep" checked> Обчислювати енергетичний виграш (окрема енергетична серія)</label><p>Кількість парних кадрів = кількість рівнів × повторення на рівень. У поточному адаптері sweep замінює демонстраційний кадр; окремий sample run не додається.</p>';
  form.prepend(mode);
  const fields = {'mx-frame':['Довжина послідовності (N), символи','20000','Стаття: 20 000 елементів. У моделі це інтервали символів, включно з пілотами; payload має менше ніж 2N біт.'], 'mx-trials':['Кількість повторень (N_trials), кадри','1','Незалежні парні кадри на рівень; налаштування моделі.'], 'mx-noise':['Дисперсія комплексного шуму (σ²_c), на відлік','0.05','Налаштування моделі REPRO: комплексний білий гаусівський шум.'], 'mx-target':['Цільовий BER (BER_target), частка','0.05','Проєктний target gain; не тотожний p*п.'], 'mx-rho':['Кореляція AR(1) (ρ), на комплексний відлік','0.98','Налаштування моделі, не значення зі статті.'], 'mx-period':['Період пілотів (T_p), символи','32','Налаштування моделі EXP-03A: впливає на tracking та overhead.'], 'mx-burst':['Довжина пілотного блоку (B_p), символи','4','Налаштування моделі EXP-03A: навчальні символи.'], 'mx-preamble':['Довжина преамбули (N_p), символи','4','Налаштування моделі EXP-03A.']};
  for(const [id,[label,value,help]] of Object.entries(fields)) {const input=$('#'+id);input.value=value;input.parentElement.firstChild.textContent=label;input.title=`Що це: ${label}. На що впливає: формує спільне спостереження або оцінку. Звідки початкове значення: ${help}`;}
  $('#mx-scenario').value='rician'; $('#mx-run').textContent='Запустити';$('#mx-stop').textContent='Скасувати';
  const gain=document.createElement('article');gain.className='card';gain.innerHTML='<h2>Енергетичний виграш Евклід відносно Хемінга (Δγ, дБ)</h2><p>Δγ = γ_Хемінг − γ_Евклід; γ_b,d = 10 log₁₀(E_b,d / σ²_c). Інтерполяція log₁₀(BER) між сусідніми виміряними точками; без екстраполяції. 95% ДІ потребує ≥95% valid bootstrap crossings.</p>';
  $('#mx-gain-status').textContent='ENERGY_GAIN_NOT_ESTIMABLE — запуск ще не виконано.';gain.append($('#mx-gain-status'));$('#view-metric').prepend(gain);
  $('#exp03b-saved-results').querySelector('h2').textContent='Архівний SCIENTIFIC-EXP-03B — лише перегляд, окремо від live N=20 000';
  const formula=document.createElement('div');formula.className='article-pair';formula.innerHTML='<article class="card"><h2>Хемінг</h2><p>Декодер Хемінга: m_H = Σ_j 1[b̂_j ≠ b_j(e)]</p></article><article class="card"><h2>Евклід</h2><p>Декодер Евкліда: m_E = |z_k − s(e)|²</p></article>';$('#view-metric').prepend(formula);
  function defaults(){ $('#mx-frame').value=20000;$('#mx-scenario').value='rician';$('#mx-trials').value=1;$('#mx-id').value='ui-custom-'+Date.now(); }
  function profile(){const archive=$('#article-profile').value==='archive';$('#profile-origin').textContent=archive?'Архівний профіль: запуск заблокований. Відкрийте перевірені результати у вкладці порівняння.':'[СТАТТЯ] N, n, η, M, R. [ПРОЄКТ] решта моделі: L=2; τ=[0,3] відліки; K=[4,1]; P=[1,0.25]; ρ=0.98; пілоти. paper_exact:false.';form.querySelectorAll('input,select,button').forEach(el=>el.disabled=archive);if(!archive){defaults();$('#mx-stop').disabled=true;} }
  $('#article-profile').addEventListener('change',profile);profile();
  $('#article-mode').addEventListener('change',()=>{$('#mx-trials').value=1;$('#mx-trials').readOnly=$('#article-mode').value==='single';});$('#mx-trials').readOnly=true;
  form.addEventListener('submit',()=>{const values=Object.fromEntries([...form.querySelectorAll('input[id],select[id]')].map(el=>[el.id,{value:el.value,checked:el.checked}]));localStorage.setItem('hf-tcm-article-settings',JSON.stringify(values));},true);
  $('#restore-article').addEventListener('click',()=>{const saved=JSON.parse(localStorage.getItem('hf-tcm-article-settings')||'{}');for(const [id,value] of Object.entries(saved)){const el=$('#'+id);if(el){el.value=typeof value==='object'?value.value:value;if(el.type==='checkbox'&&typeof value==='object')el.checked=value.checked;}}$('#mx-id').value='ui-custom-'+Date.now();$('#article-profile').value='custom';document.querySelectorAll('form').forEach(f=>f.inert=false);$('#mx-trials').readOnly=$('#article-mode').value==='single';if($('#mx-trials').readOnly)$('#mx-trials').value=1;});
  mode.querySelector('p').textContent='Спочатку виконується N_trials демонстраційних парних кадрів на базовому рівні; потім, якщо увімкнено, окрема серія: кількість рівнів × N_trials. Виконані кадри обліковуються окремо.';
  let trace=null;
  const nativeFetch=window.fetch;
  window.fetch=async(...args)=>{const response=await nativeFetch(...args);if(String(args[0]).includes('/api/scientific/traces?')) response.clone().json().then(t=>{trace=t;drawCloud();}).catch(()=>{});return response;};
  function drawCloud(){if(window.stage4)return;const c=$('#received-cloud'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);const n=Math.min(trace?.received_i?.length||0,2000);const mode=$('#cloud-mode').value;const range=Math.max(1.3,...(trace?.received_i||[]).slice(0,n).map(Math.abs),...(trace?.received_q||[]).slice(0,n).map(Math.abs));const scale=210/range;const x=v=>350+v*scale,y=v=>250-v*scale;ctx.strokeStyle='#aaa';ctx.beginPath();ctx.moveTo(0,250);ctx.lineTo(700,250);ctx.moveTo(350,0);ctx.lineTo(350,500);ctx.stroke();for(let k=0;k<8;k++){const a=k*Math.PI/4;ctx.fillStyle='#162a39';ctx.beginPath();ctx.arc(x(Math.cos(a)),y(Math.sin(a)),5,0,7);ctx.fill();ctx.fillText(`${k}: ${k}π/4`,x(Math.cos(a))+8,y(Math.sin(a)));}if(mode!=='ideal'&&trace){for(let i=0;i<n;i++){const phase=trace.phase_indices?.[Math.floor(i/8)]||0;ctx.fillStyle=`hsl(${phase*45} 75% 45% / .5)`;ctx.fillRect(x(trace.received_i[i]),y(trace.received_q[i]),3,3);}$('#cloud-info').textContent=`Після каналу: ${n} відліків; лише візуалізаційна вибірка з вікна архітектурного запуску. Live A-H/A-E I/Q ще не підключено.`;}}
  $('#cloud-mode').addEventListener('change',drawCloud);
  const css=document.createElement('style');css.textContent='.article-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.tabs{flex-wrap:wrap}#received-cloud{width:100%;max-width:700px}#view-parameters #metric-study-form{width:100%}@media(max-width:760px){.article-pair{grid-template-columns:1fr}}';document.head.append(css);
  window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)));navigate(location.hash.slice(1)||'parameters');
  window.addEventListener('popstate',()=>navigate(location.hash.slice(1)||'parameters'));
  window.addEventListener('scientific-view',e=>navigate(e.detail));
})();
