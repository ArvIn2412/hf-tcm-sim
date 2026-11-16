# REPRO-10A — аудит BER/SER

## Висновок

Суперечність у записах REPRO-10 не була помилкою decoded bits або BER. Поле `separate.ser` та лічильник `separate.symbol_errors` позначали помилки **жорстко демодульованих 8PSK фаз до декодера**, але GUI підписував їх як SER інформаційних пар. Для порівняння BER потрібен інший показник: інформаційна пара помилкова, якщо помилковий хоча б один з двох її бітів у тій самій decoded sequence.

Для одних і тих самих reference/decoded information bits виконується `pair_errors <= bit_errors <= 2 * pair_errors`. Phase-symbol помилки не мусять задовольняти цю нерівність, оскільки це стадія до Вітербі.

## Незалежний read-only перерахунок історичних запусків

| Кадр | Bit errors / bits | Information-pair errors / pairs | Information-pair SER | Hard phase errors / phases | Phase-symbol SER |
|---:|---:|---:|---:|---:|---:|
| F=256 | 56 / 512 | 47 / 256 | 0.18359375 | 60 / 256 | 0.234375 |
| F=32 | 7 / 64 | 6 / 32 | 0.1875 | 9 / 32 | 0.28125 |

Скрипт `scripts/audit_repro10a_legacy_pair_ser.py` перевіряє маніфести, читає NPZ traces, окремо рахує помилки і перевіряє SHA-256 старих `summary.json` та `traces.npz` до/після. Старі файли не переписуються. Результат — `outputs/repro10a/audit/legacy_pair_ser_recount.json`.

## Зміни

- `evaluate_information_pair_errors` обчислює BER і information-pair SER з тієї самої впорядкованої decoded bit sequence та повертає positions.
- Нові summaries мають явні поля `information_pair_*` і `phase_symbol_*`. Сумісні старі поля `ser`, `symbol_errors` залишені; `symbol_metric_semantics` пояснює їхню семантику.
- Старі summaries, завантажені через `load_run_summary`, збагачуються в пам'яті з перевірених NPZ decoder bits. Їхні summary/manifests не переписуються. Якщо decoder traces відсутні, pair SER показується як недоступний.
- GUI окремо підписує information-pair SER та phase-symbol SER; Monte Carlo SER явно означає SER інформаційних пар.

## Нова контрольна серія REPRO-10A

`outputs/repro10a/reference_control_summary.json` містить три короткі реальні кадри F=32, seeds/configs, observation hashes та BER/обидва SER:

- Identity/noiseless: 64 бітів; Joint, B0, B1 мають 0 помилок.
- Static multipath `[0,3]`, без шуму: 259 received samples; Joint, B0, B1 мають 0 помилок для цього визначеного fixture.
- Rician AR(1) multipath, sample-domain variance 0.005: Joint 0/64, B0 1/64; B1 відхилено/не запускався для цього непідтримуваного каналу.

Ці короткі перевірки підтверджують узгодженість лічильників та проходження кадру, а не статистичну перевагу приймача. Інформаційний бітовий BER історичних запусків не змінився; було виправлено класифікацію і назву символьної метрики.
