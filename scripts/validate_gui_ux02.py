import json,time
from pathlib import Path
from hf_tcm.studio.scientific import ScientificRunConfig,run_scientific_run,load_run_summary
from hf_tcm.repro.paired_experiment import ExperimentConfig,run_paired_experiment,verify_experiment
root=Path('outputs/gui_ux_02');rows=[]
for profile in ['identity','awgn','static_single_path','static_multipath','rician_ar1_multipath']:
 multi=profile in ['static_multipath','rician_ar1_multipath']
 c=ScientificRunConfig(run_id='ux02-'+profile,frame_symbols=32,source_seed=10202,channel_seed=90202,channel_profile=profile,noise_variance=0 if profile=='identity' else .05,delays_samples=(0,3) if multi else (0,),path_coefficients=((.8,0),(.2,-.1)) if multi else ((1.,0.),),include_b1=profile!='rician_ar1_multipath',output_root=str(root/'controls'))
 t=time.perf_counter();s=run_scientific_run(c);loaded=load_run_summary(root/'controls'/c.run_id)
 assert s['receiver_observation_sha256']==loaded['receiver_observation_sha256']
 rows.append(s)
(root/'control_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
c=ExperimentConfig(experiment_id='ux02-bounded',frame_symbols=32,noise_variances=(.01,.1),trials_per_point=5,root_seed=7202,output_dir=str(root/'monte_carlo'),run_level='smoke',max_trials=10,bootstrap_replicates=200,diagnostics_level='selected_trials',selected_trial_indices=(0,))
a=run_paired_experiment(c);b=run_paired_experiment(c);print(verify_experiment(Path(c.output_dir)/c.experiment_id))
print('Controls',len(rows),'MC completed',a.completed_trials if hasattr(a,'completed_trials') else a)
