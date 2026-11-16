// Presentation adapter; simulation configuration and numerical arrays are unchanged.
(() => {
  const $=s=>document.querySelector(s), all=s=>[...document.querySelectorAll(s)];
  const put=(s,t)=>{const el=$(s);if(el)el.textContent=t;};
  all('.legacy-link,.eyebrow,.page-heading p,.page-heading .status-pill,footer,.status-note,.config-card small,.card-heading p,.chart-card > p,.caveat,#sync-status,.page-heading .window-control,#symbol-previous,#symbol-next,#zoom-20-samples').forEach(el=>el.hidden=true);
  $('#view-viterbi .window-control').hidden=false;
  $('#viterbi-symbol').closest('label').hidden=true;
  put('#view-joint h1','Спільна демодуляція та декодування — метрика Евкліда');
  put('#view-separate h1','Роздільна демодуляція та декодування — метрика Хемінга');
  put('#view-viterbi h1','Решітка Вітербі');
  put('#view-channel .chart-grid article:nth-child(2) h2','Внески затриманих променів');
  put('#view-saved .saved-row h2','Архів: 20 000 символів');
  put('#view-saved .saved-row p','Збережені метрики та діагностика. Відліки I/Q відсутні.');
  put('#run-button','Запустити моделювання');
  all('.run-card h2,.run-card p').forEach(el=>el.hidden=true);
  put('#decoder-profile option','Вітербі з обмеженою глибиною η = 20');
  const receiverNames=['Спільне приймання — Евклід','Роздільне приймання — Хемінг','Роздільне з компенсацією каналу — Хемінг'];
  [...$('#global-receiver').options].forEach((o,i)=>o.textContent=receiverNames[i]);
  function help(el,text){
    const box=document.createElement('span');box.className='help';
    const button=document.createElement('button');button.type='button';button.className='help-button';button.textContent='?';button.setAttribute('aria-label','Пояснення параметра');button.setAttribute('aria-expanded','false');
    const tip=document.createElement('span');tip.className='help-tip';tip.id=`help-${all('.help').length}`;tip.role='tooltip';tip.textContent=text;button.setAttribute('aria-controls',tip.id);
    button.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();button.setAttribute('aria-expanded',String(box.classList.toggle('open')));});
    button.addEventListener('keydown',e=>{if(e.key==='Escape'){box.classList.remove('open');button.setAttribute('aria-expanded','false');}});
    box.append(button,tip);el.append(box);
  }
  const names=['Кількість елементів сигналу','Початкове число генератора бітів','Профіль каналу','Дисперсія комплексного шуму','Промінь 0: коефіцієнт I, Q','Промінь 1: коефіцієнт I, Q','Коефіцієнти райсівських завмирань','Початкове число генератора каналу','Декодування','Додати роздільне приймання з компенсацією каналу'];
  const tips=['Кількість переходів решітки: 1–20 000; два інформаційні біти на перехід.','Невід’ємне ціле число для відтворення інформаційної послідовності.','Дискретна комплексна модель каналу.','Середня потужність комплексного шуму на відлік. Дисперсія кожної квадратури — половина цього значення; не фізичне Eb/N0.','Безрозмірні дійсна та уявна частини коефіцієнта першого променя.','Другий промінь: затримка 3 комплексні відліки; коефіцієнт безрозмірний.','Проєктні відношення регулярної та дифузної потужностей: 4 і 1; кореляція 0,98.','Невід’ємне ціле число для відтворення завмирань і шуму.','η = 20 переходів решітки. Перше звичайне рішення після 20-го символу; затримка — 19 наступних символів.','Публічно відомі статичні коефіцієнти. Не підтримує невідомі райсівські завмирання.'];
  all('#run-form label').forEach((el,i)=>{const n=[...el.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());if(n)n.textContent=names[i];help(el,tips[i]);});
  const channels=['Ідеальний канал','Адитивний білий гауссівський шум','Статичний однопроменевий','Статичний двопроменевий [0, 3]','Райсівський AR(1), два промені [0, 3]'];
  [...$('#channel-profile').options].forEach((o,i)=>o.textContent=channels[i]);
  put('.value-chip','Згортковий код 2/3 · 4 стани · 8PSK · 8 відліків/символ');
  const details=document.createElement('details');details.className='channel-details';details.innerHTML='<summary>Додаткові параметри</summary>';
  $('#static-fields').before(details);details.append($('#static-fields'),$('#rician-fields'));
  all('.sync-toolbar > label').forEach((el,i)=>{el.firstChild.textContent=['Символ','Відлік','Приймач'][i];help(el,['Номер елемента сигналу від 0; один перехід решітки.','Абсолютний номер комплексного відліку. Програмна конвенція n = 8k + i, i = 0…7.','Вибір діагностики алгоритму на спільному прийнятому спостереженні.'][i]);});
  const legend=document.createElement('div');legend.className='trellis-legend';legend.innerHTML='<span class="path-key">Обраний локальний шлях</span><span class="current-key">Поточний перехід</span><span class="alternative-key">Альтернативні переходи</span><span class="rejected-key">Відхилені переходи</span>';
  $('#trellis-svg').before(legend);help(legend,'Локальний шлях обраного кінцевого стану та фактично видані рішення — різні структури. η рахує переходи решітки.');
  const filter=document.createElement('label');filter.innerHTML='Показ переходів<select id="trellis-filter"><option value="all">Усі</option><option value="survivors">Лише збережені</option><option value="path">Обраний локальний шлях</option></select>';
  $('#load-viterbi').before(filter);
  all('.window-control label').forEach(el=>{const n=[...el.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());if(n)n.textContent=n.textContent.replace('η transitions','Глибина вікна η').replace('Survivor endpoint','Кінцевий стан шляху').replace('Symbol k','Символ');});
  all('#mc-form label').forEach(el=>help(el,'Параметр відтворюваної парної серії. Статистика використовує завершені незалежні випробування.'));
  all('#mc-form small').forEach(el=>el.hidden=true);
  const mcNames=['Райсівський AR(1), два промені','Повільні завмирання, два промені','Невідомий статичний двопроменевий','Відомий статичний двопроменевий','Статичний однопроменевий','Райсівський однопроменевий','Одиничний коефіцієнт із шумом'];
  [...($('#mc-profile')?.options||[])].forEach((o,i)=>o.textContent=mcNames[i]);
  document.addEventListener('click',e=>all('.help.open').forEach(el=>{if(!el.contains(e.target)){el.classList.remove('open');el.querySelector('button').setAttribute('aria-expanded','false');}}));
  const tools=document.createElement('div');tools.className='utility-buttons';tools.innerHTML='<button type="button" id="method-open" class="secondary-button">Методика й обмеження</button><button type="button" id="metadata-open" class="secondary-button">Відомості про експеримент</button>';
  $('.sync-toolbar').after(tools);
  function dialog(id,title){const d=document.createElement('dialog');d.id=id;d.innerHTML=`<h2>${title}</h2><div class="dialog-body"></div><form method="dialog"><button class="secondary-button">Закрити</button></form>`;document.body.append(d);return d;}
  const method=dialog('method-dialog','Методика й обмеження');method.querySelector('.dialog-body').innerHTML='<p>Офлайнова дискретна комплексна модель TCM/8PSK. Шумова дисперсія задана на комплексний відлік; шкала не є підтвердженим фізичним Eb/N0. Райсівський AR(1) канал і адаптивний оцінювач — програмна реконструкція. Енергетичний виграш 1,5 дБ незалежно не підтверджено.</p><p>Основний показник SER порівнює інформаційні пари після декодування. Фазовий SER спільного приймача оцінюється після декодування, роздільного — до декодування; ці стадії не тотожні. Результат одного кадру не доводить статистичної переваги.</p>';
  const metadata=dialog('metadata-dialog','Відомості про експеримент');metadata.querySelector('.dialog-body').innerHTML='<pre>Спочатку відкрийте або виконайте моделювання.</pre>';
  $('#method-open').onclick=()=>method.showModal();$('#metadata-open').onclick=()=>metadata.showModal();
  window.addEventListener('scientific-summary',e=>{metadata.querySelector('pre').textContent=JSON.stringify(e.detail,null,2);});
  const terms={'#view-transmitter h1':'TCM поєднує згорткове кодування 2/3 та 8PSK: вісім рівновіддалених фаз. Кодер статті має чотири стани. Нормування амплітуди — програмна конвенція.','#view-joint h1':'Метрика Евкліда — відстань між прийнятим і прогнозованим комплексними сигналами. Поточний профіль накопичує її квадрат; буквальна тотожність формулі статті не встановлена.','#view-separate h1':'Метрика Хемінга — кількість відмінних бітів у кодовій трійці, від 0 до 3.','#view-comparison h1':'BER — частка помилкових інформаційних бітів. SER інформаційних пар — частка пар з хоча б одним помилковим бітом. Обидві величини безрозмірні.'};
  Object.entries(terms).forEach(([s,t])=>help($(s),t));
})();
