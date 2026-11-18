/* Metric-isolation results use only verified study summaries and trace values. */
(() => {
  'use strict';
  const view=document.getElementById('view-metric');
  const archive=document.createDocumentFragment();
  window.resultsArchive=archive;
  archive.append(...view.childNodes);
  const heading=document.createElement('h1');heading.textContent='Результати';
  const subtitle=document.createElement('p');subtitle.textContent='Порівняння метрик Хемінга та Евкліда на спільному спостереженні.';
  const compare=document.createElement('div');compare.className='results-comparison';
  const comparisonCaption=document.createElement('p');comparisonCaption.textContent='Показники вибраного кадру';comparisonCaption.hidden=true;
  const empty=document.createElement('p');empty.textContent='Запустіть моделювання або відкрийте збережене дослідження.';
  const actions=document.createElement('div');actions.className='results-actions';
  const decode=document.createElement('button');decode.type='button';decode.textContent='Декодування';decode.onclick=()=>document.querySelector('[data-view="viterbi"]').click();
  const saved=document.createElement('button');saved.type='button';saved.textContent='Відкрити збережене дослідження';saved.onclick=()=>document.querySelector('[data-view="saved"]').click();
  actions.append(decode,saved);
  const chartSection=document.createElement('section');chartSection.className='results-chart';
  const chartTitle=document.createElement('h2');chartTitle.textContent='BER та енергія';
  const chartHint=document.createElement('p');chartHint.textContent='Енергетичне дослідження ще не виконано.';
  const chartSlot=document.createElement('div');chartSlot.className='results-chart-slot';
  const gain=document.createElement('p');gain.className='results-gain';
  chartSection.append(chartTitle,chartHint,chartSlot,gain);
  view.append(heading,subtitle,comparisonCaption,compare,empty,actions,chartSection);
  document.querySelector('[data-view="metric"]').textContent='Результати';
  const option=document.querySelector('.mobile-view-menu option[value="metric"]');if(option)option.textContent='Результати';
  const chart=window.energyInteractive.charts.ber;
  const controls=chart.canvas.parentElement.querySelector('.energy-chart-controls');
  const extras=document.createElement('details');const label=document.createElement('summary');label.textContent='Графік та експорт';extras.append(label,controls,chart.note,chart.inspector);chartSection.append(extras);
  controls.querySelector('[data-action=full]').onclick=()=>document.fullscreenElement?document.exitFullscreen():chartSection.requestFullscreen?.();
  const json=document.createElement('button');json.textContent='JSON';json.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(summary,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='results.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};controls.append(json);displayTarget();
  function displayTarget(){const targetLabel=document.createElement('span');targetLabel.id='results-target';controls.prepend(targetLabel);}
  const displayMode=document.createElement('select');displayMode.setAttribute('aria-label','Обсяг результатів');displayMode.innerHTML='<option value="frame">Окремий кадр</option><option value="series">Статистична серія</option>';view.insertBefore(displayMode,comparisonCaption);displayMode.onchange=()=>{if(displayMode.value==='series')showSeries();else{comparisonCaption.textContent='Показники вибраного кадру';showComparison(trace?.arms?{hamming:trace.arms.hamming.statistics,euclidean:trace.arms.euclidean.statistics}:null);}};
  const seriesPoint=document.createElement('select');seriesPoint.setAttribute('aria-label','Енергетична точка');view.insertBefore(seriesPoint,comparisonCaption);seriesPoint.hidden=true;
  seriesPoint.onchange=()=>{displayMode.value='series';showSeries();};
  const archiveSelect=document.createElement('select');archiveSelect.setAttribute('aria-label','Підтверджена серія');
  for(const [key,name] of Object.entries({awgn_direct:'AWGN — прямий приймач',awgn_pilot:'AWGN — пілоти',static_pilot:'Статична багатопроменевість',rician_period32:'Rician — пілоти 32',rician_period8:'Rician — пілоти 8'})){const o=document.createElement('option');o.value=key;o.textContent=name;archiveSelect.append(o);}
  const open=document.createElement('button');open.textContent='Відкрити підтверджену серію';actions.append(archiveSelect,open);
  let verifiedArchive=null;
  open.onclick=async()=>{open.disabled=true;empty.hidden=false;empty.textContent='Перевіряємо збережені дані. Це може тривати кілька хвилин.';try{
    if(!verifiedArchive){const response=await fetch('/api/scientific/exp03b-results',{signal:AbortSignal.timeout(600000)});const data=await response.json();if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);if(!data.provenance_verified)throw Error('Походження даних не підтверджено');verifiedArchive=data;}const data=verifiedArchive;
    const section=data.metric_isolation?.[archiveSelect.value]?.amplitude_fixed_noise;if(!section)throw Error('Серія недоступна');
    const map=v=>({hamming:v?.hamming,joint:v?.euclidean});
    const aggregates=section.point_summaries.map(p=>({...p,ber:map(p.ber),ser:map(p.ser_information_pairs),fer:map(p.fer),pair_errors:map(p.pair_errors),frame_errors:map(p.frame_errors),ser_ci:map(p.bootstrap_95ci?.ser_information_pairs),fer_ci:map(p.bootstrap_95ci?.fer),bit_errors:map(p.bit_errors),ber_ci:map(p.bootstrap_95ci?.ber)}));
    window.dispatchEvent(new CustomEvent('metric-summary',{detail:{confirmed_archive:true,configuration:{target_ber:0.05},aggregates,archive_gains:section.metric_gain}}));
  }catch(error){empty.hidden=false;empty.textContent=`Не вдалося відкрити серію: ${error.name==='TimeoutError'?'Перевірка архіву перевищила 10 хвилин. Повторіть відкриття; сервер може завершувати перевірку файлів.':error.message}`;}finally{open.disabled=false;}};
  function showSeries(){
    const row=summary?.aggregates?.[Number(seriesPoint.value)||0];if(!row)return;
    showComparison(Object.fromEntries([['hamming','hamming'],['euclidean','joint']].map(([name,key])=>[name,{ber:row.ber?.[key],bit_errors:row.bit_errors?.[key],bits:row.bits,ser_information_pairs:row.ser?.[key],fer:row.fer?.[key],ci:row.ber_ci?.[key],pair_errors:row.pair_errors?.[key],pairs:row.pairs,frame_errors:row.frame_errors?.[key],trials:row.trials,ser_ci:row.ser_ci?.[key],fer_ci:row.fer_ci?.[key],series:true}])));
    comparisonCaption.textContent=`Статистична серія · ${row.trials} кадрів · γᵦ,ᵈ = ${fmt(row.gamma_db)} дБ`;
  }
  let summary=null,trace=null;
  const count=value=>Number.isSafeInteger(value)?value.toLocaleString('uk-UA'):'—';
  const fmt=value=>typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('uk-UA',{maximumSignificantDigits:5}):'—';
  function showComparison(arms,description){
    if(!arms){compare.replaceChildren();empty.hidden=false;comparisonCaption.hidden=true;return;}
    empty.hidden=true;comparisonCaption.hidden=false;compare.replaceChildren();
    for(const [key,label] of [['hamming','Хемінг'],['euclidean','Евклід']]){
      const s=arms[key],section=document.createElement('section');
      const h=document.createElement('h2');h.textContent=label;
      const ber=document.createElement('strong');ber.textContent=`BER ${fmt(s?.ber)}`;
      const p=document.createElement('p');p.textContent=`Бітові помилки: ${count(s?.bit_errors)} із ${count(s?.bits ?? s?.information_bits)} · Помилки інформаційних пар: ${fmt(s?.ser_information_pairs)} · ${s?.series?'FER: '+fmt(s.fer):'Кадр із помилкою: '+(s?.fer===1?'так':s?.fer===0?'ні':'—')} ${s?.ci?'· 95% ДІ BER ['+s.ci.map(fmt).join('; ')+']':''}`;
      const details=document.createElement('details');const title=document.createElement('summary');title.textContent='Counts та невизначеність';const info=document.createElement('p');info.textContent=`Інформаційні пари: ${count(s?.pair_errors)} із ${count(s?.pairs)}. ${s?.series?'Кадри: '+count(s.frame_errors)+' із '+count(s.trials)+'. ':''}${s?.ser_ci?'95% ДІ SER: ['+s.ser_ci.map(fmt).join('; ')+']. ':''}${s?.fer_ci?'95% ДІ FER: ['+s.fer_ci.map(fmt).join('; ')+']. ':''}${s?.bit_errors===0?'Помилок не спостережено; це не доводить нульову ймовірність помилки.':''}`;details.append(title,info);
      section.append(h,ber,p,details);compare.append(section);
    }
    empty.textContent=description||'Запустіть моделювання або відкрийте збережене дослідження.';
  }
  function renderChart(){
    const rows=(summary?.aggregates||[]).filter(r=>Number.isFinite(r.gamma_db)&&Number.isFinite(r.ber?.hamming)&&Number.isFinite(r.ber?.joint));
    const sample=summary?.ui_run_kind==='sample'||String(summary?.configuration?.experiment_id||'').endsWith('-sample');
    const valid=!sample&&rows.length>=2&&new Set(rows.map(r=>r.gamma_db)).size>=2;
    const canvas=window.energyInteractive.charts.ber.canvas;
    if(valid){chartSlot.append(canvas);chartHint.textContent='Виміряна статистична серія · дискретна модельна енергетична шкала, дБ.';window.dispatchEvent(new Event('resize'));}
    else {archive.append(canvas);chartHint.textContent=sample||!summary?'Енергетичне дослідження ще не виконано.':'Недостатньо виміряних енергетичних точок для графіка.';}
  }
  window.addEventListener('metric-context-cleared',()=>{summary=null;trace=null;showComparison(null);renderChart();gain.textContent='';seriesPoint.hidden=true;seriesPoint.replaceChildren();});
  window.addEventListener('metric-summary',e=>{
    if(e.detail.contrast_mode==='system'||e.detail.contrast_id==='full_system'){window.dispatchEvent(new CustomEvent('metric-context-cleared',{detail:{kind:'system',id:''}}));empty.textContent='Порівняння повних приймачів не є ізольованим порівнянням метрик.';return;}
    summary=e.detail;document.getElementById('results-target').textContent='Ціль BER: '+fmt(summary.configuration?.target_ber);
    if(!e.detail.trace_preserve_existing)trace=null;
    showComparison(trace?.arms?{hamming:trace.arms.hamming.statistics,euclidean:trace.arms.euclidean.statistics}:null);
    seriesPoint.replaceChildren();seriesPoint.hidden=!summary.aggregates?.length;
    for(const [i,row] of (summary.aggregates||[]).entries()){const o=document.createElement('option');o.value=i;o.textContent=`γᵦ,ᵈ ${fmt(row.gamma_db)} дБ`;seriesPoint.append(o);}
    const sample=summary.ui_run_kind==='sample'||String(summary.configuration?.experiment_id||'').endsWith('-sample');displayMode.value=trace||sample?'frame':'series';displayMode.options[0].disabled=!trace;displayMode.options[1].disabled=sample||!summary.aggregates?.length;seriesPoint.hidden=sample||!summary.aggregates?.length;if(!trace&&!sample)showSeries();
    renderChart();gain.textContent='';
    if(summary.confirmed_archive){const a=summary.archive_gains?.['0.05'];const ci=a?.bootstrap?.log_ber?.gain_db_ci95;gain.textContent=a?.precision_assessment?.status==='PRECISION_CRITERIA_MET'&&Number.isFinite(a?.gain_db_log_ber)&&Array.isArray(ci)&&ci.every(Number.isFinite)?`Підтверджувальна модельна серія · ціль BER 0,05 · виграш ${fmt(a.gain_db_log_ber)} дБ · 95% ДІ [${ci.map(fmt).join('; ')}]`:(a?.precision_assessment?.status==='INSUFFICIENT_PRECISION'?'Виграш не підтверджено: недостатня точність або частка валідних перетинів.':'Виграш не оцінено: одна або обидві криві не перетинають цільовий BER 0,05.');}

  });
  window.addEventListener('metric-trace-loaded',e=>{if(summary?.confirmed_archive)return;displayMode.options[0].disabled=false;if(displayMode.value==='series'){trace=e.detail;return;}comparisonCaption.textContent='Показники вибраного кадру';trace=e.detail;showComparison({hamming:trace.arms.hamming.statistics,euclidean:trace.arms.euclidean.statistics});});
  window.addEventListener('metric-energy-status',e=>{
    if(summary?.confirmed_archive)return;const a=summary?.gain_analysis,ci=a?.bootstrap?.confidence_interval_db;
    if(e.detail.status==='GAIN_ESTIMATED'&&Number.isFinite(a?.gain_db)&&Array.isArray(ci)&&ci.length===2&&ci.every(Number.isFinite))
      gain.textContent=`Розвідувальна модельна оцінка виграшу: ${fmt(a.gain_db)} дБ · ціль BER ${fmt(summary?.configuration?.target_ber)} · 95% інтервал [${fmt(ci[0])}; ${fmt(ci[1])}] дБ.`;
    else gain.textContent=e.detail.reason||'Виграш не оцінено: недостатньо статистичних даних.';
  });
  window.addEventListener('article-view',e=>{if(e.detail==='metric')window.dispatchEvent(new Event('resize'));});
  // Keep auxiliary views reachable through their existing navigation handlers.
  for(const [key,button,label] of [['viterbi',decode,'Декодування'],['saved',saved,'Відкрити збережене дослідження']]){
    const tab=document.querySelector(`.tabs [data-view="${key}"]`);
    tab.textContent=label;button.replaceWith(tab);
    document.querySelector(`.mobile-view-menu option[value="${key}"]`)?.remove();
    const back=document.createElement('button');back.type='button';back.textContent='До результатів';
    back.onclick=()=>document.querySelector('.tabs [data-view="metric"]').click();
    document.getElementById('view-'+key).prepend(back);
  }
  const experiment=document.querySelector('.tabs [data-view="parameters"]');experiment.textContent='Експеримент';
  const experimentOption=document.querySelector('.mobile-view-menu option[value="parameters"]');if(experimentOption)experimentOption.textContent='Експеримент';
  const source=document.querySelector('.source-summary');if(source)archive.append(source);
  document.querySelector('footer')?.remove();document.querySelector('.legacy-link')?.remove();
  document.querySelectorAll('#view-parameters input[title],#view-parameters select[title]').forEach(el=>el.removeAttribute('title'));
})();
