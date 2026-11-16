# SCIENTIFIC-EXP-01: експериментальна оцінка енергоефективності

Статус: **SCIENTIFIC_EXP_01_PARTIAL**. Фізичний Eb/N0 не калібрований; paper_exact:false. Погоджені squared Euclidean metric та complex AWGN використані без зміни алгоритмів.

| Фаза | Канал | Sweep | Completed pairs | Information bits |
|---|---|---|---:|---:|
| confirmatory | awgn | amplitude | 100 | 51200 |
| confirmatory | awgn | noise | 100 | 51200 |
| confirmatory | static | amplitude | 140 | 71680 |
| confirmatory | static | noise | 121 | 61952 |
| long | awgn | amplitude | 1 | 40000 |
| long | rician | amplitude | 1 | 40000 |
| pilot | awgn | amplitude | 15 | 7680 |
| pilot | awgn | noise | 15 | 7680 |
| pilot | rician | amplitude | 15 | 7680 |
| pilot | rician | noise | 15 | 7680 |
| pilot | static | amplitude | 15 | 7680 |
| pilot | static | noise | 15 | 7680 |

﻿# SCIENTIFIC-EXP-01: зафіксована методика

Цілі decoded information BER: 0,01 (основна), 0,05 (додаткова). Вони не ототожнюються з p* статті. Погоджені проєктні рішення: squared complex residual metric та чинний complex AWGN REPRO-03. paper_exact:false.

## Енергія

Використано 8 ZOH-відліків на перехід, 2 payload bits на перехід, амплітуда A>0. Відсутні termination/pilot bits. E_tx,d=Σ|x[n]|²=8FA², E_b,d=E_tx,d/(2F)=4A². Інформаційна швидкість у дискретній конвенції — 2/8 бітів на відлік. Хвіст каналу не є новим символом і не змінює payload denominator.

γ_b,d=10log10(4A²/σ_c²). Amplitude sweep змінює лише A за σ_c²=1. Noise sweep має A=1 та σ_c²=4/10^(γ/10). Усі приймачі отримують ту саму явну nominal amplitude. Потужності, коефіцієнти, їхні priors/covariances та часові параметри каналу не масштабуються з A.

Еквівалентність із дискретним Eb/N0 можлива при інтерпретації samples як ортонормованих complex координат, w~CN(0,N0 I), узгодженій нормі прямокутного імпульсу та використанні повної достатньої статистики проєкції. Наприклад, проєкція на pulse/√8 дає signal amplitude √8 A та noise variance σ_c². Фізичні sample period, смуга й PSD calibration не встановлені; фізичним Eb/N0 цю вісь не називаємо. Oversampling за фіксованої повної енергії не дає безкоштовного виграшу.

## Канали та дозволена інформація

AWGN: h=1, delay0. Static multipath: h0=√0.8, h1=√0.2 exp(j0.7), delays[0,3]. Joint має ці статичні коефіцієнти як явні public nominal priors з covariance0.25 і продовжує адаптацію; B1 — exact public static taps; B0 — nominal constellation без ISI compensation. Тому Joint/B1 не є порівнянням однакових estimator architectures, а Joint/B0 не ізольований ефект метрики.

Rician: powers[0.8,0.2], K[4,1], LOS phase[0,0.7]rad, rho0.98 на complex sample; stationary independent path streams. Регулярні потужності[0.64,0.10], дифузні[0.16,0.10]; сума ensemble powers1. B1 unavailable. Receiver priors походять із public distribution parameters, не actual realization. Received instantaneous power не дорівнює сумі powers автоматично через coherent/ISI terms. Основна енергетична шкала є transmitter-referred.

## Вибірка, невизначеність і зупинка

SeedSequence розділяє phase/scenario/sweep/point/trial/stream; bits/fading/noise різні між trials і grid points, однакові для receiver arms у парі. Пілот F256 має 3 trials/point. Основну сітку зафіксовано після нього, основна ціль — 20 trials/point, 10240 information bits/point: приблизно102 очікувані bit errors при BER0.01; це обмежена точність і лише20 independent clusters. Pilot не включається в confirmatory estimates. Жоден seed не обирався за BER.

20-cluster percentile bootstrap не є доказом рідкісної нульової ймовірності. За zero error frames використовується conservative one-sided frame upper bound 1−0.05^(1/T); BER≤FER для цих кадрів. Перетини з target лише в межах adjacent measured points; основне правило — linear log10(BER) versus γdB; без log(0), pseudocount, smoothing чи extrapolation. Gain=γ_Separate−γ_Joint, що дорівнює10log10(Eb_Separate/Eb_Joint) за fixed reference noise1. Перетини повторно обчислюють у paired trial-cluster bootstrap незалежно за grid points. 95% CI публікується лише при≥95% valid-crossing replicates; інакше conditional quantiles позначаються окремо. Інтервали pointwise, не simultaneous.

Бюджети: pilot300s, main1000s, long360s, disk400MB. Послідовне виконання, м’яка зупинка між completed pairs. Можливе перевищення на одну поточну пару; partial trial не агрегується. Усі завершені trials мають immutable config/record/NPZ та SHA-256 manifest. Resume перевіряє хеші перед skip. F20000 контроль не замінює багато independent frames.

У Joint delayed tail включено у last-symbol metric за наявним contract. B0 tail не є додатковим символом. Відмінності використання tail є частиною системного порівняння й не виправлялися для поліпшення результату.


Повні paired cluster bootstrap outputs, validity fractions, nonzero required-energy brackets і conditional-only quantiles наведені у analysis/gains.json. Перевірка errors та SHA independent від receiver функцій збережена в independent_replay.json. Zero BER не є точною нульовою ймовірністю.

## Підсумок validation та чутливість

Фінальний full pytest: **1212 passed in 67.75s**; Ruff check/format пройшли; historical fingerprints **694/694**, artifacts76/76. Незалежний replay перевіряє всі manifested control/series arrays. Додаткова posthoc діагностика F256, γ=3dB, 3 seeds×3 scenarios×2 sweeps не включена в inference: після нормування вектори received відрізняються лише на floating-point rounding, коефіцієнти ідентичні, decoded bits усіх arms ідентичні. Див. scaling_diagnostic.json.

При target0.05 static amplitude-sweep log-BER estimate Joint/B0=6.76779dB, 95%pointwise bootstrapCI[6.20976,7.51817]; Joint/B1=2.96415dB, CI[2.71560,3.22877]. Альтернативна linear-BER інтерполяція дає5.97000dB і2.60952dB відповідно: напрямок зберігається, але точна величина чутлива до грубої сітки. Ця modeling/interpolation uncertainty НЕ включена до наведених статистичних CI. Neighbor omission diagnostic у neighbor_sensitivity.json показує, коли втрачається допустимий bracket; це підстава для finer independently frozen follow-up grid, а не прихованої заміни поточної оцінки.

При primary target0.01 AWGN amplitude point estimate3.92381dB (EbJ2.69992, EbB0/B1=6.66395), static Joint/B0=9.98668dB (EbJ1.95649, EbB0=19.50502) і Joint/B1=3.97781dB (EbB1=4.88944). Для цих контрастів valid bootstrap crossing fraction нижча95%; безумовний95%CI не публікується. Rician B0 не має підтвердженого перетину target на виміряній сітці; main Rician trial count0 через бюджет.

Нові tooling defects виправлено до фінальної regression: tuple/list cache round-trip та глобальна ctypes signature у RAM probe. Це metadata/orchestration corrections; не зміни receiver/channel mathematics. Main memory fields можуть бути unavailable, long-frame measurements доступні. Не трактувати RAM unavailable як0.

Фінальні статуси: SCIENTIFIC_EXP_01_PARTIAL; ENERGY_NORMALIZATION_VALIDATED; BER_CURVES_PARTIAL (main Rician відсутній); ENERGY_GAIN_ESTIMATED лише для зазначених model contrasts; STATISTICAL_CONFIDENCE_PARTIAL; ARTICLE_1_5_DB_INSUFFICIENT_DATA. Фізичний виграш не доведений. Наступні роботи не запускалися.
