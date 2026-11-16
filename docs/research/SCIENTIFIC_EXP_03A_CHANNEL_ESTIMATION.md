# SCIENTIFIC-EXP-03A — спільне pilot оцінювання каналу

## Практичний frontend

`run_pilot_frontend()` приймає `ReceiverObservation`, pilot schedule та відкриті project parameters: nominal amplitude, integer delays, assumed complex noise variance. Він не приймає tap truth, decoded payload, channel object або `EvaluationTruth`. Pilot input pairs є однаковими для обох arms; encoder state logic окремо визначає, які coded phase symbols справді відомі. Для interior burst перші невизначені переходи не використовуються як відомі фази.

На кожному символі frontend спершу формує оцінений рівняний символ із поточною доступною оцінкою; лише після цього, якщо поточна coded phase відома і pilot спостережено, він оновлює composite gain. Отже оцінка причинна, без майбутнього payload і truth leakage. Обидва metric decoders отримують побітово один frontend output; trial records мають однакові `frontend_output_sha256_euclidean` і `_hamming`.

## Канальні умови

- **AWGN direct control:** `y=x+w`, пряме усереднення 8 samples. Немає estimator/equalizer; є контрольний baseline.
- **AWGN pilot:** той самий pilot frontend, щоб відокремити overhead/estimator effects від метрик.
- **Static `[0,3]`:** проектні taps `1+0j`, `0.3−0.2j`, затримки `[0,3]`. У clean-tail вибірці ISI від попереднього символу немає за ZOH/цілочисельного-delay доказом. Pilot estimate оцінює їхній сумарний composite gain, не окремі tap values.
- **Rician AR(1) `[0,3]`:** середні потужності `[1,0.25]`, K `[4,1]`, LOS phases `[0,0.7]` rad, `rho=0.98` на sample, AWGN complex variance у пілоті 0.05. Очікувана сума номінальних середніх path powers 1.25; генератор нормує промені до заданих потужностей відповідно до чинного channel contract. Зміна channel в часі береться зі справжнього REPRO-03 generator.

Rician pilot period 32 відповідає приблизно 256 sample інтервалу між відомими gain updates. Для `rho=0.98` це велика затримка відносно sample-rate recursion. Виміряний mean age 14,5 symbols, max 28, gain RMSE ~0,625 і equalized residual RMS ~1,137 в exploratory p32 fixture узгоджуються з помітним tracking residual. Period 8 зменшує середній вік до ~2,5 symbols, але накладні витрати 64/128 symbols (50%) і лишається високий BER Hamming. Це не підтверджує практичну якість pilot design.

## Резидуальна ISI і noise

Clean-tail operation точно усуває contributions інших символів лише для ZOH, causal integer delays `D<8`, незмінної pulse timing і достатньої довжини observation. Fractional delays, wider spread, pulse shaping та sample clock mismatch не підтримані цим доказом. За Rician sample-varying taps коефіцієнт змінюється всередині clean-tail; scalar composite estimate не знімає цю модуляцію. Практичний residual тому може бути multiplicative, навіть коли delay-domain ISI term у вибраних samples нульовий.

За умовно відомого gain matched linear combination має формальну теплову variance `σ²/(L|g|²)` при сталому `g` по L samples. В реальному pilot path `g` оцінено з шумних пілотів і повторно використовується; його помилка робить вихідні residuals залежними між символами та додає signal-dependent distortion. Діагностика за фактичними records бачить nonzero lag-1 correlation близько 0,08–0,10 для effective noise/residual у пілотних AWGN/static/Rician arms, а для Rician total equalized symbol error має виражену часову структуру. Тому downstream residual не слід описувати як iid `CN(0, σ²_out)` без умов.

## Статуси доступу до каналу

1. **Pilot estimated:** практичний common frontend; primary для metric-only comparison.
2. **Neutral prior:** поточний metric frontend не має recursive prior parameter; окремий neutral-prior test не оголошується реалізованим.
3. **Oracle CSI:** окрема діагностична функція, приймає truth tap trace навмисно. Її не можна змішувати з pilot-estimated results або представляти як практичний приймач.
4. **Повні Joint/B0/B1:** їхні наявні estimator/CSI умови залишаються власними контрактами історичного receiver comparison. Це не тотожні інформаційні умови і не контроль метрик.

Не змінювати `paper_exact:false`. Rician model — проєктна discrete AR(1), не повна фізична модель КХ каналу та не модель імпульсних/негаусівських завад.
