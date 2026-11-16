# REPRO-06C: performance and output

Результат містить повні metric rows (`F×E`), post-update mean/covariance diagonal для кожного кадру й вузла (`F×S×L`), survivor-edge/innovation diagnostics і decoded arrays. При D=3 маємо E=68, S=17, L=2; η-ring зберігає щонайбільше 20 predecessor rows. Diagnostic arrays ростуть лінійно з F; competing path histories не накопичуються експоненційно. NPZ/JSON manifest рахує SHA-256.

SVG adapter наразі формує п'ять фактичних видів: received I/Q, середні survivor estimates I/Q, metric heatmap і decoded bits. Він не малює true-vs-estimated fading: такі графіки потребують окремого evaluation-only виклику із truth sidecar після декодування. Одиничний час у summary — вимірювання запуску, не benchmark.

F=32 paired fixtures завершилися. F=256 sample-level Rician + AWGN run завершився приблизно за 2 секунди для adaptive receiver; це одиничне вимірювання, не benchmark. Reference F=20,000 run завершився на REPRO-03 observation; час і розмір arrays зафіксовано у `outputs/repro06c/reference_20000/summary.json`. Не робити висновку про продуктивність за одиничними таймінгами.

За фінальним запуском F=20,000 adaptive receiver elapsed time становив 152.96 s; compressed NPZ має 28,031,692 байти. У NPZ branch metrics мають форму `(20000,68)`, survivor path metrics `(20000,17)`, mean histories `(20000,17,2)`, covariance diagonal `(20000,17,2)`, predictions `(160003,)`, а decoded information — 40,000 бітів. Peak process RAM окремо не вимірювався. Рішення η=20 зберігало ring максимум 20 рядків. Одне вимірювання не є benchmark.
