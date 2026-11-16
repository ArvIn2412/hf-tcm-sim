# REPRO-04 — перевірка reference fixtures і кадру

## Незалежні математичні перевірки

1. Вісім точок 8PSK тестуються як окремі complex samples, повторені 8 разів; очікувані phase indices задаються без виклику demodulator.
2. ADR-002 inverse для кожного `b` дорівнює бітам двійкового запису `b` у порядку `(c₂,c₁,c₀)`; усі вісім labels різні.
3. Для кожного з 16 edge output triples branch distance обчислюється тестом скалярно як кількість нерівних бітів. One-bit perturbation окремо порівнюється для всіх edges.
4. Equal-cost Viterbi fixture має всі нульові branch metrics; canonical tie rule відтворює edge ID 0 на кожному кроці від початкового `00`.
5. Identity channel із нульовим шумом і явним zero-tail відновлює payload біти та завершується у `00`; статичний complex coefficient відомий receiver config і тестується окремо.
6. 160003-sample multipath observation із `F=20000` обробляє 160000 відліків для 20000 символів і реєструє три tail samples як невикористані.

## Фактичний 20 000-symbol run

Input: `outputs/repro03/reference_n_star/receiver_observation.npz/json`, `F=20000`, 8 samples/symbol, nominal front end, `φ₀=0`, full-frame/free final state. Receiver loader не відкривав `evaluation_truth.npz`.

- Observation semantic SHA-256: `1bc276f254e358b5a4a52e8585f9a5616d00f554e3a84847a26cd58f16cb34ed`.
- Received samples: 160003; processed indices: 0–159999; excluded tail: 160000–160002.
- Hard phase array `(20000,)`; triple array `(20000,3)`; branch costs `(20000,16)` int8; path metrics `(20001,4)` int64; survivors `(20000,4)` int16; state path `(20001,2)`; output payload bits `(40000,)` int8.
- One run path metric: 4247. Це діагностика конкретного стохастичного профілю, не BER/SER чи performance claim.
- Receiver computation wall time записаний у performance manifest: 0.1991 s на Python 3.13.13 / NumPy 2.3.3 (hard demodulation 0.0044 s, Hamming matrix 0.0052 s, Viterbi 0.1623 s); plot generation 0.0299 s. Це одне вимірювання, не benchmark.
- Матеріалізовані receiver arrays займають 4,240,058 bytes; стиснений `receiver_result.npz` — 1,572,548 bytes. Peak process RSS не вимірювався.
- NPZ SHA-256: `8682e31a56c60d11c7c9e9b9530392ba5af59cf55a076f901ce245ef64e283aa`.
- Output arrays SHA-256: `683052c7d5ee6bd4ed8eaa63f62395e6a706ece57ef93716c22d490eb8f789ad`.

SVG файли у `outputs/repro04/reference_n_star/plots/` включають I/Q, прийняте сузір'я, hard decisions, Hamming heatmap, Viterbi path metric/state path, 20-symbol view та 20-sample detail. У них немає synthetic hidden states або BER-vs-SNR.

