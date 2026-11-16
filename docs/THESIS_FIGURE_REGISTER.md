# Реєстр рисунків магістерської роботи

SVG 1–13 створюються локальним утилітарним скриптом
`docs/figures/generate_thesis_figures.py` з проєктних рівнянь та вже
збережених frozen report values. Скрипт не імпортує HF-TCM-SIM, не викликає
receiver/decoder і не генерує нових експериментальних даних. Edge screenshots
14–18 є фактичними файлами M11e, не AI-зображеннями.

| № | Підпис українською | Файл | Джерело | Пояснення / вісь |
|---|---|---|---|---|
| Рисунок 1 | Архітектура HF-TCM-SIM | `docs/figures/fig01_hf_tcm_sim_architecture.svg` | `src/hf_tcm/`, M11 reports | Потік бітів → encoding → channel → metric/estimator/Viterbi; концептуальна схема реконструкції |
| Рисунок 2 | Реконструйована структура кодера R=2/3 | `docs/figures/fig02_tcm_encoder.svg` | [A], стор. 5–6; `coding/encoder.py` | Пам'ять двох затримок; вихідний порядок зазначено |
| Рисунок 3 | Чотиристанова решітка та 16 проєктних переходів | `docs/figures/fig03_reconstructed_trellis.svg` | `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md`; code mapping | Edge ID, input/output, next state, b; авторське phase labeling не стверджується |
| Рисунок 4 | Сузір'я 8PSK із фазовим кроком π/4 | `docs/figures/fig04_8psk_constellation.svg` | [A](3),(5), стор. 5; `psk8.py` | Осі I/Q; проєктні b labels |
| Рисунок 5 | Тракт передачі через модельний канал | `docs/figures/fig05_model_channel.svg` | Channel models; M10 report | Неповна фізична модель; P0/P1/P2 описані в freeze |
| Рисунок 6 | Реконструйований тракт joint receiver | `docs/figures/fig06_joint_receiver_reconstruction.svg` | Source audit + receiver modules | Candidate costs → project posterior → update/conditional decode |
| Рисунок 7 | Рекурсивне оновлення оцінки | `docs/figures/fig07_recursive_estimator.svg` | [A](1); `paper_recursion.py` | Явні проектні operands; подальше використання стану f+1 |
| Рисунок 8 | Conditional Viterbi над frozen metric rows | `docs/figures/fig08_conditional_viterbi.svg` | `reconstruction_viterbi.py` | Початковий state, min-plus, traceback; project tie policy |
| Рисунок 9 | M5j pooled BER: frozen B і combined C | `docs/figures/fig09_m5j_ber.svg` | M5j/M5k | Вісь x: BER, відношення errors/51 200; без SNR-кривої |
| Рисунок 10 | M7/M8 BER у TRAIN partitions | `docs/figures/fig10_m7_m8_train.svg` | M7b/M8 recovery reports/checkpoints | Вісь x: BER; різні study generations, жодна не є validation |
| Рисунок 11 | M9b paired ΔBER та 95% CI | `docs/figures/fig11_m9_ber_ci.svg` | M9b report/bootstrap | Вісь ΔBER anchored−B; вертикаль нуля; paired cluster interval |
| Рисунок 12 | M10 модельні профілі дійсного gain | `docs/figures/fig12_m10_gain_profiles.svg` | M10b report/config | x: symbol index 0–256; y: dimensionless gain a[f] |
| Рисунок 13 | M10 P1 paired ΔBER та 95% CI | `docs/figures/fig13_m10_p1_ber_ci.svg` | M10b report/bootstrap | Вісь ΔBER; interval crossing zero |
| Рисунок 14 | Стартовий екран Demo Studio (1366×768) | `docs/screenshots/m11e-start-1366x768.png` | M11e real Edge capture | Фактичний screenshot; перед демонстраційним POST |
| Рисунок 15 | Результат детермінованого POST (1366×768) | `docs/screenshots/m11e-demo-results-post-run-1366x768.png` | M11e real Edge capture | F=32 summary; UI не є незалежним experiment |
| Рисунок 16 | Решітка станів і переходів (1920×1080) | `docs/screenshots/m11e-trellis-1920x1080.png` | M11e real Edge capture | Реальні UI states/edges; реконструйована mapping |
| Рисунок 17 | Рекурсивний оцінювач (1920×1080) | `docs/screenshots/m11e-estimator-1920x1080.png` | M11e real Edge capture | Показ actual deterministic trace operands |
| Рисунок 18 | Conditional decode (1920×1080) | `docs/screenshots/m11e-decode-1920x1080.png` | M11e real Edge capture | Показ одного frozen-metric traceback |

Не створювалися BER-vs-SNR криві, не виконувалися нові симуляції, а результати
P0/P1/P2 та M9 не екстраполювалися на інші канали. Всі numeric axes мають
безрозмірні rates/counts або символний індекс; gain є дійсним модельним
множником, не одиницею потужності.

