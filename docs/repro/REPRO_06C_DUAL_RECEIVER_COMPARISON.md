# REPRO-06C: dual-receiver comparison

`scripts/run_repro06c_paired_checks.py` формує один transmitter output і один REPRO-03 realization для кожного сценарію. Спершу передаються лише `receiver_observation` об'єкти як до adaptive API, так і до REPRO-04. Після обох запусків evaluation layer порівнює їх з transmitter references. Для known-static контрольного сценарію використано наявний REPRO-06B static CSI joint MLSE окремо від нового adaptive PSP; 06B код і математика не змінені.

Identity, static-known, unknown-static, slow Rician і Rician AR(1)+AWGN мають окремі IDs/seeds в runner. Збережені observation hashes збігаються попарно між адаптивним/вибраним joint arm і Hamming arm. Результати та кілька прикладів BER/SER є descriptive single-frame output; немає Monte Carlo, довірчих інтервалів чи BER-vs-SNR графіків.

Незалежні тести підтверджують формули одного update і геометрію delayed regressors. Поточна paired перевірка не доводить точність PSP відносно глобального exhaustive unknown-channel оптимуму; для такого твердження потрібні інша постановка та незалежна oracle.
