/* Configuration adapter for the existing paired B0/Joint API. */
(() => {
  'use strict';
  document.addEventListener('DOMContentLoaded',()=>{
    const form=document.getElementById('run-form'),stash=window.systemArchive;
    const old=id=>window.systemNodes.get('#'+id);
    const button=old('run-button'),status=old('job-status');
    const primary=document.createElement('div');primary.className='simulation-primary';
    const more=document.createElement('details');more.innerHTML='<summary>Додатково</summary>';
    const advanced=document.createElement('div');advanced.className='simulation-primary';more.append(advanced);
    const fields={};let reusedStatic=null;
    function field(key,title,values,defaultValue,target=primary){
      const label=document.createElement('label');label.textContent=title;
      const input=document.createElement(values?'select':'input');input.id='exp-'+key;
      if(values)for(const [value,text]of values){const o=document.createElement('option');o.value=value;o.textContent=text;input.append(o);}
      else input.type='text';
      input.value=defaultValue;label.append(input);target.append(label);fields[key]=input;return input;
    }
    field('awgn','Білий гаусівський шум',[['on','Увімкнено'],['off','Вимкнено']],'on');
    field('variance','Дисперсія σ²',null,'0.05').type='number';fields.variance.step='any';fields.variance.min='0';
    field('fading','Завмирання',[['none','Немає'],['rician','Rician'],['rayleigh','Rayleigh']],'none');
    field('rays','Кількість променів',[[1,1],[2,2],[3,3]],'1');
    function existing(name,title,value){const n=form.querySelector(`[name="${name}"]`);n.value=value;const label=document.createElement('label');label.textContent=title;label.append(n);primary.append(label);return n;}
    const n=existing('frame_symbols','N',20000),seed=existing('source_seed','Seed',20261109);
    field('mode','Режим',[['single','Один запуск'],['series','Статистична серія']],'single');
    const defaults={delays:[0,3,6],powers:[1,.25,.125],k:[4,1,1],phases:[0,.7,1.4]};
    for(const [key,title]of Object.entries({k:'K',rho:'Кореляція ρ',delays:'Затримки, відліки',powers:'Потужності променів',phases:'Фази, рад'}))field(key,title,null,key==='rho'?'.98':String(defaults[key][0]),advanced);
    field('amplitude','Амплітуда',null,'1',advanced);field('channelSeed','Seed каналу (порожньо — автоматично)',null,'',advanced);
    fields.rays.onchange=()=>{for(const key of Object.keys(defaults)){const a=fields[key].value.split(',');fields[key].value=defaults[key].slice(0,Number(fields.rays.value)).map((v,i)=>a[i]??v).join(',');}};
    fields.awgn.onchange=()=>{fields.variance.closest('label').hidden=fields.awgn.value==='off';};
    for(const [id,title]of Object.entries({'es-grid':'Енергетична сітка, дБ','es-trials':'Кадрів на точку','es-target':'Ціль BER','es-budget':'Бюджет, с','es-bootstrap':'Bootstrap-повторення','es-sweep':'Спосіб зміни енергії'})){
      const input=old(id),label=document.createElement('label');label.textContent=title;label.append(input);advanced.append(label);
    }
    const note=document.createElement('p');note.textContent='Пілоти в цьому системному API не застосовуються; обидва приймачі отримують одне спостереження.';more.append(note);
    const progress=old('es-progress');progress.removeAttribute('value');
    stash.append(...form.childNodes);button.textContent='Запустити моделювання';
    form.className='simulation-form';form.append(primary,button,progress,more);
    document.querySelector('#view-parameters h1').textContent='Імітаційне моделювання';
    window.systemExperiment={get mode(){return fields.mode.value;},build(){
      const arrays=Object.fromEntries(Object.keys(defaults).map(k=>[k,fields[k].value.split(',').map(Number)]));
      const root=Number(seed.value),rays=Number(fields.rays.value),dynamic=fields.fading.value!=='none';
      const channel=window.channelControls.build({awgn:fields.awgn.value==='on',fading:fields.fading.value,rays,variance:Number(fields.variance.value),seed:root,rho:Number(fields.rho.value),delays:arrays.delays,powers:arrays.powers,factors:arrays.k,phases:arrays.phases});
      old('es-frame').value=n.value;old('es-seed').value=root;old('es-b0').checked=true;old('es-b1').checked=false;
      const profile=dynamic?'rician_ar1_multipath':rays>1?'static_multipath':arrays.powers[0]!==1||arrays.phases[0]!==0?'static_single_path':fields.awgn.value==='on'?'awgn':'identity';
      old('channel-profile').value=profile;
      return {frame_symbols:Number(n.value),source_seed:root,channel_seed:fields.channelSeed.value.trim()?Number(fields.channelSeed.value):root+17,amplitude:Number(fields.amplitude.value),channel_profile:profile,noise_variance:channel.noise_complex_variance,delays_samples:arrays.delays,path_coefficients:reusedStatic&&reusedStatic.powers===fields.powers.value&&reusedStatic.phases===fields.phases.value&&reusedStatic.coefficients.length===rays?reusedStatic.coefficients:arrays.powers.map((power,i)=>[Math.sqrt(power)*Math.cos(arrays.phases[i]),Math.sqrt(power)*Math.sin(arrays.phases[i])]),path_powers:arrays.powers,rician_k_factors:dynamic?channel.paths.map(p=>p.k_factor):arrays.k,los_phases_rad:arrays.phases,fading_correlation:Number(fields.rho.value),traceback_depth:20,include_b1:false};
    }};
    window.addEventListener('system-reuse-configuration',e=>{
      const c=e.detail.configuration||{};n.value=c.frame_symbols??20000;seed.value=c.source_seed??c.root_seed??20261109;
      const dynamic=c.channel_profile==='rician_ar1_multipath',delays=c.delays_samples||[0],coefficients=c.path_coefficients||[];
      fields.rays.value=String(delays.length);fields.fading.value=dynamic?(c.rician_k_factors?.every(k=>k===0)?'rayleigh':'rician'):'none';
      fields.awgn.value=c.noise_variance>0?'on':'off';fields.variance.value=c.noise_variance>0?c.noise_variance:.05;fields.awgn.onchange();
      fields.delays.value=delays.join(',');fields.powers.value=(!dynamic&&coefficients.length?coefficients.map(([a,b])=>a*a+b*b):c.path_powers||[1]).join(',');
      fields.phases.value=(!dynamic&&coefficients.length?coefficients.map(([a,b])=>Math.atan2(b,a)):c.los_phases_rad||[0]).join(',');
      reusedStatic=!dynamic&&coefficients.length?{powers:fields.powers.value,phases:fields.phases.value,coefficients}:null;
      fields.k.value=(c.rician_k_factors||delays.map(()=>0)).join(',');fields.rho.value=c.fading_correlation??.98;
      fields.amplitude.value=c.amplitude??1;fields.channelSeed.value=c.channel_seed??'';fields.mode.value=e.detail.kind==='energy'?'series':'single';
      for(const [key,id]of Object.entries({gamma_grid_db:'es-grid',trials_per_point:'es-trials',target_ber:'es-target',time_budget_seconds:'es-budget',bootstrap_replicates:'es-bootstrap',sweep:'es-sweep'}))if(c[key]!==undefined)old(id).value=Array.isArray(c[key])?c[key].join(','):c[key];
      old('es-id').value='energy-'+Date.now();status.textContent='Конфігурацію завантажено для наступного запуску.';
    });
    const seriesStatus=old('es-status'),seriesButton=old('es-run');
    new MutationObserver(()=>{if(fields.mode.value==='series'){status.textContent=seriesStatus.textContent;button.disabled=seriesButton.disabled;}}).observe(seriesStatus,{childList:true,subtree:true,characterData:true});
    new MutationObserver(()=>{if(fields.mode.value==='single'){if(button.disabled)progress.removeAttribute('value');else progress.value=1;}}).observe(button,{attributes:true,attributeFilter:['disabled']});
  });
})();
