(() => {
  const put = (selector, value) => { const node = document.querySelector(selector); if (node) node.textContent = value; };
  const tabLabels={parameters:"Параметри",transmitter:"Передавач",channel:"Канал",joint:"Спільне приймання",separate:"Роздільне приймання",viterbi:"Решітка Вітербі",comparison:"Порівняння","monte-carlo":"Monte Carlo",saved:"Збережені"};
  document.querySelectorAll(".tab").forEach(button=>{button.textContent=tabLabels[button.dataset.view]||button.textContent;});
  document.title="HF-TCM-SIM — наукова лабораторія";
  put(".brand small","наукова лабораторія"); put(".legacy-link","M11 демо");
  put("#view-parameters .eyebrow","ОДИН КОНТРОЛЬОВАНИЙ ЗАПУСК"); put("#view-parameters h1","Параметри моделювання");
  put("#view-parameters .page-heading p:not(.eyebrow)","Задайте конфігурацію та запустіть справжній ланцюг передавання, канал і два приймачі.");
  put("#view-transmitter h1","Передавач"); put("#view-transmitter .page-heading p:not(.eyebrow)","Фактичні біти, стани, переходи та відліки з одного збереженого запуску.");
  put("#view-channel h1","Радіоканал"); put("#view-channel .page-heading p:not(.eyebrow)","Прийнятий сигнал, внески шляхів і шум того самого запуску.");
  put("#view-joint h1","Спільне приймання"); put("#view-joint .page-heading p:not(.eyebrow)","REPRO-06C: survivor-specific адаптація та евклідові метрики. Відкладені рішення можуть походити з різних перекривних шляхів.");
  put("#view-separate h1","Роздільне приймання"); put("#view-separate .page-heading p:not(.eyebrow)","REPRO-04 B0: жорстке рішення 8PSK перед декодером Вітербі з цілочисельними метриками Хемінга.");
  put("#view-comparison h1","Парне порівняння"); put("#view-comparison .page-heading p:not(.eyebrow)","BER/SER описують цей кадр і не є статистичним доказом переваги.");
  put("#view-monte-carlo h1","Monte Carlo"); put("#view-monte-carlo .page-heading p:not(.eyebrow)","Реальний парний runner REPRO-07 · ті самі біти, шум і ReceiverObservation для двох приймачів.");
  put("#view-saved h1","Збережені експерименти"); put("#view-saved .page-heading p:not(.eyebrow)","Завантаження перевіряє маніфест і SHA-256.");
  const titleSets={
    "#view-transmitter .eyebrow":"ЕТАП 01","#view-channel .eyebrow":"ЕТАП 02","#view-joint .eyebrow":"ЕТАП 03A",
    "#view-separate .eyebrow":"ЕТАП 03B","#view-comparison .eyebrow":"ЕТАП 04","#view-monte-carlo .eyebrow":"ЕТАП 05",
    "#view-saved .eyebrow":"АРХІВ","#view-monte-carlo .status-pill":"sample-domain variance · не Eb/N0"
  };
  Object.entries(titleSets).forEach(([s,v])=>put(s,v));
  const heads={
    "#view-transmitter .chart-card h2":"Передані I/Q","#view-transmitter .card:not(.chart-card) h2":"Інформаційні біти та кодер",
    "#view-channel .chart-card h2":"Переданий і прийнятий сигнал","#view-channel .chart-grid article:nth-child(2) h2":"Внески delayed paths",
    "#view-channel .chart-grid article:nth-child(3) h2":"Параметри й синхронізація",
    "#view-joint .chart-card h2":"Метрики переходів","#view-joint .chart-grid article:nth-child(2) h2":"Оцінка каналу",
    "#view-joint .chart-grid article:nth-child(3) h2":"Результат декодування",
    "#view-separate .chart-card h2":"Метрики Хемінга","#view-separate .chart-grid article:nth-child(2) h2":"Жорсткі рішення 8PSK",
    "#view-separate .chart-grid article:nth-child(3) h2":"Результат декодування",
    "#view-comparison .chart-card h2":"Позиції бітових помилок",
    "#view-monte-carlo #mc-results h2":"Статистика серії",
    "#view-parameters .config-card:nth-child(1) h2":"Передавач",
    "#view-parameters .config-card:nth-child(2) h2":"Радіоканал",
    "#view-parameters .config-card:nth-child(3) h2":"Приймачі"
  };
  Object.entries(heads).forEach(([s,v])=>put(s,v));
  const labels=[...document.querySelectorAll("#run-form label")];
  ["Елементів сигналу F","Seed інформаційної послідовності","Профіль каналу","Комплексна дисперсія шуму","Шлях 0: коефіцієнт I, Q","Шлях 1: коефіцієнт I, Q","Rician K factors","Seed каналу","Декодер","Режим channel-aware B1"].forEach((text,i)=>{
    const label=labels[i]; if(!label)return; const n=[...label.childNodes].find(x=>x.nodeType===Node.TEXT_NODE && x.nodeValue.trim()); if(n)n.nodeValue=text;
  });
  const optionText=["Identity — без шуму та завмирання","AWGN — одиничний шлях","Статичний однопроменевий","Статичний multipath [0, 3]","Rician AR(1) multipath [0, 3]"];
  [...document.querySelector("#channel-profile").options].forEach((o,i)=>o.textContent=optionText[i]);
  const decoder=document.querySelector("#decoder-profile option"); if(decoder)decoder.textContent="Finite-depth Viterbi, η = 20";
  const smalls=[...document.querySelectorAll("#run-form label small")];
  ["За замовчуванням короткий кадр; 20 000 запускайте явно.","Sample-domain variance на відлік; це не фізичний Eb/N0.","Статичний project profile; коефіцієнти задаються нижче.","Значення project-defined profile; кореляція ρ = 0,98.","B1 існує в REPRO-08 API, але цей запуск порівнює A і B0."].forEach((v,i)=>{if(smalls[i])smalls[i].textContent=v;});
  const mcLabels=[...document.querySelectorAll("#mc-form label")];
  ["ID серії","Канал","Довжина кадру F","Дисперсії комплексного шуму","Пар на рівень","Початковий seed","Бюджет часу, секунд"].forEach((v,i)=>{const n=mcLabels[i]&&[...mcLabels[i].childNodes].find(x=>x.nodeType===Node.TEXT_NODE&&x.nodeValue.trim());if(n)n.nodeValue=v;});
  if(document.querySelector("#mc-form label small"))document.querySelector("#mc-form label small").textContent="Через кому; sample-domain variance на відлік, не Eb/N0.";
  put("#mc-run","Запустити / відновити"); put("#mc-stop","Зупинити після пари"); put("#mc-status","Очікує конфігурації.");
  const buttonsText={"#run-button":"Запустити моделювання →","#refresh-runs":"Оновити список"};
  Object.entries(buttonsText).forEach(([s,v])=>put(s,v));
  put("#open-long-frame","Відкрити великий результат");
  put("#job-status","Очікує запуску"); put("#paired-badge","Немає завершеного запуску");
  put("footer span:first-child","HF-TCM-SIM · REPRO-09");
  put("footer span:last-child","paper_exact: false · шум у sample-domain · офлайнова симуляція");
  const staticText=[
    ["#view-transmitter .chart-card p","Комплексні відліки прямокутного ZOH · нормована амплітуда"],
    ["#view-channel .chart-card p","I/Q · абсолютний індекс відліку"],
    ["#view-joint .chart-card p","Реальні candidate metrics · squared Euclidean project profile"],
    ["#view-separate .chart-card p","Локальна відстань 0–3 для переходів Encoder A"],
    ["#view-comparison .caveat strong","Межі інтерпретації"],
    ["#view-comparison .caveat p","Це порівняння двох повних алгоритмів на одному спостереженні. Шум задано в sample-domain; це не фізичний Eb/N0. 1,5 дБ зі статті не використовується для підгонки."],
    ["#view-monte-carlo #mc-results p","Після завершення тут з'являться BER/SER, DeltaBER та інтервали парного bootstrap."]
  ];
  staticText.forEach(([s,v])=>put(s,v));
  window.REPRO09_UA={
    queued:"У черзі…",running:"Виконується REPRO-02 → REPRO-03 → два приймачі…",
    complete:"Симуляцію завершено · результати збережено.",waiting:"Перевірка конфігурації…",
    runFailed:"Помилка моделювання",sameObs:"Парне спостереження",hashMismatch:"Хеші спостереження не збігаються",
    joint:"Спільний Euclidean · REPRO-06C",separate:"Роздільний Hamming · B0",
    noRun:"Запуск ще не виконано.",plotErrors:"Позиції бітових помилок"
  };
})();
