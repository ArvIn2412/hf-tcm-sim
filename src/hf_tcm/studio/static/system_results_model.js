/* Presentation only: no statistics or receiver estimation is performed here. */
((root)=>{
 'use strict';
 const finite=v=>typeof v==='number'&&Number.isFinite(v);
 function single(summary){
  const n=summary.frame_symbols,m=summary.information_bit_count;
  if(!Number.isSafeInteger(n)||n<=0||!Number.isSafeInteger(m)||m<=0)throw Error('Некоректні знаменники N або M');
  if(!summary.paired_observation_verified)throw Error('Спільне спостереження приймачів не підтверджено');
  return {n,m,total:finite(summary.elapsed_seconds)?summary.elapsed_seconds:null,arms:Object.fromEntries([['b0','separate'],['joint','joint']].map(([key,source])=>{
   const r=summary[source];if(!r||!Number.isSafeInteger(r.compared_bits)||r.compared_bits<=0||!Number.isSafeInteger(r.bit_errors)||r.bit_errors<0||r.bit_errors>r.compared_bits)throw Error('Некоректні counts приймача');
   const time=finite(r.runtime_seconds)&&r.runtime_seconds>=0?r.runtime_seconds:null;
   return [key,{errors:r.bit_errors,bits:r.compared_bits,ber:r.bit_errors/r.compared_bits,time,perElement:time===null?null:time/n,perBit:time===null?null:time/m,scope:r.runtime_scope||'historical_receiver_measurement'}];
  }))};
 }
 function series(summary){
  if(summary.contrast_mode!=='system'||!summary.receiver_arms?.includes('joint')||!summary.receiver_arms?.includes('b0'))throw Error('Потрібні системні результати Joint/B0');
  const rows=summary.aggregates||summary.analyses?.b0?.aggregate||[];
  const target=summary.target_ber??summary.configuration?.target_ber;
  const source=summary.analyses?.b0;
  const ci=source?.bootstrap?.confidence_interval_db;
  const accepted=source?.precision_assessment?.status==='PRECISION_CRITERIA_MET'||(!summary.confirmatory&&source?.observed_crossing===true&&source?.bootstrap?.valid_fraction>=.95);
  const gain=accepted&&finite(source?.gain_db)&&Array.isArray(ci)&&ci.length===2&&ci.every(finite)?{value:source.gain_db,ci}:null;
  return {rows,target,gain,reason:source?.precision_assessment?.status==='INSUFFICIENT_PRECISION'?'Недостатня статистична точність':'Немає допустимої парної оцінки перетину цільового BER'};
 }
 function archive(data,scenario,target){
  if(data.provenance_verified!==true)throw Error('Цілісність архіву не підтверджено');
  const section=data.full_system_comparison?.[scenario];if(!section)throw Error('Системна серія недоступна');
  const a=section.energy_gain?.[String(target)]?.b0;
  return {contrast_mode:'system',confirmatory:true,receiver_arms:['joint','b0'],target_ber:target,aggregates:section.point_summaries,
   analyses:{b0:{gain_db:a?.gain_db_log_ber,precision_assessment:a?.precision_assessment,bootstrap:{confidence_interval_db:a?.bootstrap?.log_ber?.gain_db_ci95}}}};
 }
 const model={single,series,archive};root.systemResultsModel=model;if(typeof module!=='undefined')module.exports=model;
})(typeof window==='undefined'?globalThis:window);
