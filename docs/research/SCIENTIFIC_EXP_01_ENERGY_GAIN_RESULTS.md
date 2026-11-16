# SCIENTIFIC-EXP-01: експериментальна оцінка енергоефективності

Статус: **SCIENTIFIC_EXP_01_PARTIAL**. Фізичний Eb/N0 не калібрований; paper_exact:false. Погоджені squared Euclidean metric та complex AWGN використані без зміни алгоритмів.

| Фаза | Канал | Sweep | Target BER | Порівняння | Eb Joint | Eb Separate | Gain dB | 95% CI dB | Valid bootstrap fraction | Статус |
|---|---|---|---:|---|---:|---:|---:|---|---:|---|
| confirmatory | awgn | amplitude | 0.01 | Joint/b0 | 2.6999 | 6.6639 | 3.9238 | не визначено | 0.617 | PARTIAL |
| confirmatory | awgn | amplitude | 0.05 | Joint/b0 | 2.0403 | 3.773 | 2.6699 | не визначено | 0.710 | PARTIAL |
| confirmatory | awgn | amplitude | 0.01 | Joint/b1 | 2.6999 | 6.6639 | 3.9238 | не визначено | 0.625 | PARTIAL |
| confirmatory | awgn | amplitude | 0.05 | Joint/b1 | 2.0403 | 3.773 | 2.6699 | не визначено | 0.702 | PARTIAL |
| confirmatory | awgn | noise | 0.01 | Joint/b0 | 2.5043 | 6.7811 | 4.3261 | не визначено | 0.645 | PARTIAL |
| confirmatory | awgn | noise | 0.05 | Joint/b0 | 1.9797 | 3.7977 | 2.8292 | не визначено | 0.859 | PARTIAL |
| confirmatory | awgn | noise | 0.01 | Joint/b1 | 2.5043 | 6.7811 | 4.3261 | не визначено | 0.654 | PARTIAL |
| confirmatory | awgn | noise | 0.05 | Joint/b1 | 1.9797 | 3.7977 | 2.8292 | не визначено | 0.837 | PARTIAL |
| confirmatory | static | amplitude | 0.01 | Joint/b0 | 1.9565 | 19.505 | 9.9867 | не визначено | 0.642 | PARTIAL |
| confirmatory | static | amplitude | 0.05 | Joint/b0 | 1.3528 | 6.4271 | 6.7678 | [6.209755937566691, 7.518165405257755] | 1.000 | ESTIMATED |
| confirmatory | static | amplitude | 0.01 | Joint/b1 | 1.9565 | 4.8894 | 3.9778 | не визначено | 0.682 | PARTIAL |
| confirmatory | static | amplitude | 0.05 | Joint/b1 | 1.3528 | 2.677 | 2.9641 | [2.71559718117933, 3.2287690090798518] | 1.000 | ESTIMATED |
| confirmatory | static | noise | 0.01 | Joint/b0 | — | 23.957 | — | не визначено | 0.201 | NOT_ESTIMABLE |
| confirmatory | static | noise | 0.05 | Joint/b0 | 1.6746 | 6.0529 | 5.5804 | не визначено | 0.767 | PARTIAL |
| confirmatory | static | noise | 0.01 | Joint/b1 | — | 5.177 | — | не визначено | 0.194 | NOT_ESTIMABLE |
| confirmatory | static | noise | 0.05 | Joint/b1 | 1.6746 | 2.8107 | 2.249 | не визначено | 0.790 | PARTIAL |
| long | awgn | amplitude | 0.01 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| long | awgn | amplitude | 0.05 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| long | awgn | amplitude | 0.01 | Joint/b1 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| long | awgn | amplitude | 0.05 | Joint/b1 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| long | rician | amplitude | 0.01 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| long | rician | amplitude | 0.05 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | amplitude | 0.01 | Joint/b0 | — | 6.2565 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | amplitude | 0.05 | Joint/b0 | — | 3.2425 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | amplitude | 0.01 | Joint/b1 | — | 6.2565 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | amplitude | 0.05 | Joint/b1 | — | 3.2425 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | noise | 0.01 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | noise | 0.05 | Joint/b0 | — | 3.0892 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | noise | 0.01 | Joint/b1 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | awgn | noise | 0.05 | Joint/b1 | — | 3.0892 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | rician | amplitude | 0.01 | Joint/b0 | 11.481 | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | rician | amplitude | 0.05 | Joint/b0 | 2.848 | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | rician | noise | 0.01 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | rician | noise | 0.05 | Joint/b0 | 6.3324 | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | amplitude | 0.01 | Joint/b0 | — | 20.688 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | amplitude | 0.05 | Joint/b0 | — | 6.0765 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | amplitude | 0.01 | Joint/b1 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | amplitude | 0.05 | Joint/b1 | — | 2.1831 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | noise | 0.01 | Joint/b0 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | noise | 0.05 | Joint/b0 | — | 7.3981 | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | noise | 0.01 | Joint/b1 | — | — | — | не визначено | 0.000 | NOT_ESTIMABLE |
| pilot | static | noise | 0.05 | Joint/b1 | — | 3.1421 | — | не визначено | 0.000 | NOT_ESTIMABLE |


| Фаза / канал / sweep | γ_b,d (дБ) | Trials | Joint BER | B0 BER | B1 BER | Joint pair SER | B0 pair SER | Joint FER | B0 FER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| confirmatory/awgn/amplitude | 0 | 20 | 0.2519531 | 0.2520508 | 0.25205078125 | 0.4308594 | 0.4472656 | 1 | 1 |
| confirmatory/awgn/amplitude | 3 | 20 | 0.05683594 | 0.1452148 | 0.14521484375 | 0.09570312 | 0.2646484 | 1 | 1 |
| confirmatory/awgn/amplitude | 6 | 20 | 0.001074219 | 0.04570312 | 0.045703125 | 0.001953125 | 0.08105469 | 0.05 | 1 |
| confirmatory/awgn/amplitude | 9 | 20 | 0 | 0.005957031 | 0.00595703125 | 0 | 0.0109375 | 0 | 0.95 |
| confirmatory/awgn/amplitude | 12 | 20 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |
| confirmatory/awgn/noise | 0 | 20 | 0.2805664 | 0.2723633 | 0.27236328125 | 0.4839844 | 0.4794922 | 1 | 1 |
| confirmatory/awgn/noise | 3 | 20 | 0.04902344 | 0.1474609 | 0.1474609375 | 0.08320313 | 0.2669922 | 0.95 | 1 |
| confirmatory/awgn/noise | 6 | 20 | 0.000390625 | 0.04619141 | 0.04619140625 | 0.0005859375 | 0.08496094 | 0.05 | 1 |
| confirmatory/awgn/noise | 9 | 20 | 0 | 0.006347656 | 0.00634765625 | 0 | 0.01152344 | 0 | 0.95 |
| confirmatory/awgn/noise | 12 | 20 | 0 | 9.765625e-05 | 9.765625e-05 | 0 | 0.0001953125 | 0 | 0.05 |
| confirmatory/static/amplitude | 0 | 20 | 0.1868164 | 0.2551758 | 0.21865234375 | 0.3189453 | 0.4560547 | 1 | 1 |
| confirmatory/static/amplitude | 3 | 20 | 0.009179688 | 0.1558594 | 0.10712890625 | 0.015625 | 0.2806641 | 0.55 | 1 |
| confirmatory/static/amplitude | 6 | 20 | 0 | 0.07910156 | 0.01787109375 | 0 | 0.1427734 | 0 | 1 |
| confirmatory/static/amplitude | 9 | 20 | 0 | 0.04082031 | 0.0025390625 | 0 | 0.07421875 | 0 | 1 |
| confirmatory/static/amplitude | 12 | 20 | 0 | 0.01337891 | 0.0001953125 | 0 | 0.02421875 | 0 | 1 |
| confirmatory/static/amplitude | 15 | 20 | 0 | 0.005078125 | 0.0 | 0 | 0.01015625 | 0 | 0.95 |
| confirmatory/static/amplitude | 18 | 20 | 0 | 0.001855469 | 0.0 | 0 | 0.003710937 | 0 | 0.65 |
| confirmatory/static/noise | 0 | 20 | 0.2012695 | 0.2522461 | 0.2216796875 | 0.3458984 | 0.4509766 | 1 | 1 |
| confirmatory/static/noise | 3 | 20 | 0.03115234 | 0.16875 | 0.09892578125 | 0.05332031 | 0.30625 | 0.6 | 1 |
| confirmatory/static/noise | 6 | 20 | 0 | 0.08496094 | 0.025 | 0 | 0.1558594 | 0 | 1 |
| confirmatory/static/noise | 9 | 20 | 0 | 0.03544922 | 0.00224609375 | 0 | 0.065625 | 0 | 1 |
| confirmatory/static/noise | 12 | 20 | 0 | 0.02060547 | 9.765625e-05 | 0 | 0.0375 | 0 | 1 |
| confirmatory/static/noise | 15 | 20 | 0 | 0.006152344 | 0.0 | 0 | 0.01152344 | 0 | 0.95 |
| confirmatory/static/noise | 18 | 1 | 0 | 0.0078125 | 0.0 | 0 | 0.015625 | 0 | 1 |
| long/awgn/amplitude | 6 | 1 | 7.5e-05 | 0.0431 | 0.0431 | 0.00015 | 0.07975 | 1 | 1 |
| long/rician/amplitude | 6 | 1 | 0.057875 | 0.221325 | — | 0.0959 | 0.3906 | 1 | 1 |
| pilot/awgn/amplitude | -6 | 3 | 0.3873698 | 0.344401 | 0.3444010416666667 | 0.6315104 | 0.5703125 | 1 | 1 |
| pilot/awgn/amplitude | 0 | 3 | 0.2434896 | 0.25 | 0.25 | 0.4270833 | 0.4440104 | 1 | 1 |
| pilot/awgn/amplitude | 6 | 3 | 0 | 0.03776042 | 0.037760416666666664 | 0 | 0.0703125 | 0 | 1 |
| pilot/awgn/amplitude | 12 | 3 | 0 | 0.0006510417 | 0.0006510416666666666 | 0 | 0.001302083 | 0 | 0.33333 |
| pilot/awgn/amplitude | 18 | 3 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |
| pilot/awgn/noise | -6 | 3 | 0.4257812 | 0.3697917 | 0.3697916666666667 | 0.6901042 | 0.6119792 | 1 | 1 |
| pilot/awgn/noise | 0 | 3 | 0.2161458 | 0.2207031 | 0.220703125 | 0.3658854 | 0.3932292 | 1 | 1 |
| pilot/awgn/noise | 6 | 3 | 0 | 0.03580729 | 0.035807291666666664 | 0 | 0.06770833 | 0 | 1 |
| pilot/awgn/noise | 12 | 3 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |
| pilot/awgn/noise | 18 | 3 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |
| pilot/rician/amplitude | -6 | 3 | 0.3854167 | 0.3717448 | — | 0.6328125 | 0.6171875 | 1 | 1 |
| pilot/rician/amplitude | 0 | 3 | 0.2480469 | 0.3261719 | — | 0.4153646 | 0.5638021 | 1 | 1 |
| pilot/rician/amplitude | 6 | 3 | 0.02994792 | 0.2063802 | — | 0.05078125 | 0.3684896 | 1 | 1 |
| pilot/rician/amplitude | 12 | 3 | 0.007161458 | 0.1445312 | — | 0.01041667 | 0.2526042 | 0.66667 | 1 |
| pilot/rician/amplitude | 18 | 3 | 0 | 0.1979167 | — | 0 | 0.3385417 | 0 | 1 |
| pilot/rician/noise | -6 | 3 | 0.3776042 | 0.3867188 | — | 0.6197917 | 0.6263021 | 1 | 1 |
| pilot/rician/noise | 0 | 3 | 0.2701823 | 0.2779948 | — | 0.4583333 | 0.4739583 | 1 | 1 |
| pilot/rician/noise | 6 | 3 | 0.09635417 | 0.2402344 | — | 0.1536458 | 0.4257812 | 1 | 1 |
| pilot/rician/noise | 12 | 3 | 0.01367188 | 0.1803385 | — | 0.0234375 | 0.3242188 | 0.66667 | 1 |
| pilot/rician/noise | 18 | 3 | 0 | 0.188151 | — | 0 | 0.3359375 | 0 | 1 |
| pilot/static/amplitude | -6 | 3 | 0.3391927 | 0.3424479 | 0.3424479166666667 | 0.5533854 | 0.5703125 | 1 | 1 |
| pilot/static/amplitude | 0 | 3 | 0.1744792 | 0.2363281 | 0.23958333333333334 | 0.2981771 | 0.4244792 | 1 | 1 |
| pilot/static/amplitude | 6 | 3 | 0 | 0.08203125 | 0.014973958333333334 | 0 | 0.1536458 | 0 | 1 |
| pilot/static/amplitude | 12 | 3 | 0 | 0.01627604 | 0.0 | 0 | 0.02994792 | 0 | 1 |
| pilot/static/amplitude | 18 | 3 | 0 | 0.001302083 | 0.0 | 0 | 0.002604167 | 0 | 0.66667 |
| pilot/static/noise | -6 | 3 | 0.3678385 | 0.375651 | 0.3548177083333333 | 0.6171875 | 0.6236979 | 1 | 1 |
| pilot/static/noise | 0 | 3 | 0.09375 | 0.234375 | 0.17903645833333334 | 0.1588542 | 0.421875 | 1 | 1 |
| pilot/static/noise | 6 | 3 | 0 | 0.09700521 | 0.038411458333333336 | 0 | 0.1809896 | 0 | 1 |
| pilot/static/noise | 12 | 3 | 0 | 0.02213542 | 0.0 | 0 | 0.03645833 | 0 | 1 |
| pilot/static/noise | 18 | 3 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 |


Статуси ESTIMATED/PARTIAL/NOT_ESTIMABLE стосуються модельної дискретної енергії. Усі CI pointwise. Неперетин target не замінено extrapolation.

## Підсумок validation та чутливість

Фінальний full pytest: **1212 passed in 67.75s**; Ruff check/format пройшли; historical fingerprints **694/694**, artifacts76/76. Незалежний replay перевіряє всі manifested control/series arrays. Додаткова posthoc діагностика F256, γ=3dB, 3 seeds×3 scenarios×2 sweeps не включена в inference: після нормування вектори received відрізняються лише на floating-point rounding, коефіцієнти ідентичні, decoded bits усіх arms ідентичні. Див. scaling_diagnostic.json.

При target0.05 static amplitude-sweep log-BER estimate Joint/B0=6.76779dB, 95%pointwise bootstrapCI[6.20976,7.51817]; Joint/B1=2.96415dB, CI[2.71560,3.22877]. Альтернативна linear-BER інтерполяція дає5.97000dB і2.60952dB відповідно: напрямок зберігається, але точна величина чутлива до грубої сітки. Ця modeling/interpolation uncertainty НЕ включена до наведених статистичних CI. Neighbor omission diagnostic у neighbor_sensitivity.json показує, коли втрачається допустимий bracket; це підстава для finer independently frozen follow-up grid, а не прихованої заміни поточної оцінки.

При primary target0.01 AWGN amplitude point estimate3.92381dB (EbJ2.69992, EbB0/B1=6.66395), static Joint/B0=9.98668dB (EbJ1.95649, EbB0=19.50502) і Joint/B1=3.97781dB (EbB1=4.88944). Для цих контрастів valid bootstrap crossing fraction нижча95%; безумовний95%CI не публікується. Rician B0 не має підтвердженого перетину target на виміряній сітці; main Rician trial count0 через бюджет.

Нові tooling defects виправлено до фінальної regression: tuple/list cache round-trip та глобальна ctypes signature у RAM probe. Це metadata/orchestration corrections; не зміни receiver/channel mathematics. Main memory fields можуть бути unavailable, long-frame measurements доступні. Не трактувати RAM unavailable як0.

Фінальні статуси: SCIENTIFIC_EXP_01_PARTIAL; ENERGY_NORMALIZATION_VALIDATED; BER_CURVES_PARTIAL (main Rician відсутній); ENERGY_GAIN_ESTIMATED лише для зазначених model contrasts; STATISTICAL_CONFIDENCE_PARTIAL; ARTICLE_1_5_DB_INSUFFICIENT_DATA. Фізичний виграш не доведений. Наступні роботи не запускалися.
