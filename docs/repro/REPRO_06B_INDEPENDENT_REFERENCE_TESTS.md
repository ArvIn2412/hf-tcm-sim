# REPRO-06B — незалежна перевірка

`tests/repro/test_augmented_trellis.py`, `test_isi_predictor.py`, `test_isi_metrics.py`, `test_expanded_viterbi.py`, `test_multipath_joint_receiver.py` та `test_multipath_evaluation.py` містять контрольні перевірки. Expected values для коротких кодерних/каналових fixtures обчислюються локальним прямим evaluator, який не викликає production predictor/metric/Viterbi.

Ключовий критерій: для кадру з чотирьох символів незалежний oracle перебирає всі `4^4` інформаційні послідовності, окремо обчислює Encoder A recurrence і ADR-002 phase profile, виконує повну delayed sample sum для `[0,3]`, а потім сумує squared residual по всіх 35 відліках. Expanded Viterbi повертає ту саму послідовність пар і ту саму повну вартість.

Також перевірено: identity `D=0`; static complex gain; стартове zero-extension; попередньо-символьні внески; межа кадру і 3 tail samples; seeded noise; nonzero initial encoder state; усі canonical edge histories; metric rows проти прямого row oracle; metric profile norm/squared; D=9 (двосимвольна історія); same-seed determinism; truth rejection; конфігураційні caps; `eta=20` latency/flush; same observation для joint/Hamming; NPZ/JSON output та plots.

Ці fixtures доводять реалізацію лише для обраної static-public project model. Вони не перевіряють adaptive unknown Rician multipath і не є Monte Carlo чи статистичною оцінкою BER.
