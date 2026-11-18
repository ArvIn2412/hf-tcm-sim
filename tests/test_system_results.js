const {test}=require('node:test');
const assert=require('node:assert/strict');
const model=require('../src/hf_tcm/studio/static/system_results_model.js');
test('receiver runtimes use N symbols and actual M information bits independently of BER denominator',()=>{
 const r={compared_bits:36,bit_errors:3,runtime_seconds:12,runtime_scope:'complete_receiver_call'};
 const actual=model.single({frame_symbols:20,information_bit_count:40,elapsed_seconds:30,paired_observation_verified:true,separate:r,joint:{...r,runtime_seconds:8}});
 assert.equal(actual.arms.b0.perElement,.6);assert.equal(actual.arms.b0.perBit,.3);
 assert.equal(actual.arms.joint.perElement,.4);assert.equal(actual.arms.joint.perBit,.2);
 assert.equal(actual.arms.b0.ber,3/36);assert.equal(actual.total,30);
 assert.deepEqual(Object.keys(actual.arms),['b0','joint']);
 assert.throws(()=>model.single({frame_symbols:0,information_bit_count:0}));
 assert.throws(()=>model.single({frame_symbols:20,information_bit_count:40,paired_observation_verified:false}));
});
test('system comparison never accepts isolated metrics or unsupported gain estimates',()=>{
 assert.throws(()=>model.series({contrast_mode:'metric',receiver_arms:['joint','b0']}));
 const s={contrast_mode:'system',confirmatory:true,receiver_arms:['joint','b0','b1'],target_ber:.05,analyses:{b0:{gain_db:9,bootstrap:{confidence_interval_db:[8,10]},precision_assessment:{status:'INSUFFICIENT_PRECISION'}}}};
 assert.equal(model.series(s).gain,null);
 s.analyses.b0.precision_assessment.status='PRECISION_CRITERIA_MET';assert.equal(model.series(s).gain.value,9);
 assert.throws(()=>model.archive({provenance_verified:false},'awgn',.05));
});
test('confirmed system aggregates and gates come exclusively from full-system data',()=>{
 const fs=require('node:fs');
 const source=JSON.parse(fs.readFileSync('outputs/scientific_exp03b/analysis/independent_analysis.json','utf8'));
 for(const scenario of ['awgn','static','rician']){
  const actual=model.archive({...source,provenance_verified:true},scenario,.05);
  assert.deepEqual(model.series(actual).rows,source.full_system_comparison[scenario].point_summaries);
  assert.deepEqual(actual.receiver_arms,['joint','b0']);
  const expected=source.full_system_comparison[scenario].energy_gain['0.05'].b0;
  if(expected.precision_assessment.status==='PRECISION_CRITERIA_MET'){
   assert.equal(model.series(actual).gain.value,expected.gain_db_log_ber);
   assert.deepEqual(model.series(actual).gain.ci,expected.bootstrap.log_ber.gain_db_ci95);
  }else assert.equal(model.series(actual).gain,null);
 }
});
