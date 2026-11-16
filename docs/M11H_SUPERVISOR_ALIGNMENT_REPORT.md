# M11h — звіт узгодження з матеріалами наукового керівника

## Підсумок

Виконано preflight усіх наявних файлів, перевірено A/B encoder implementations і повторно звірено інтерактивні екрани з фактичним runtime trace. **`SUPERVISOR_ALIGNMENT_PARTIAL`**: потрібні `Раздел_4.doc` і стаття v7 відсутні, а рукописний `4.pdf` не містить машинно перевірюваного повного визначення фазового відображення. Кодер B тому лишається **`ENCODER_B_PARTIAL`** — джерельно похідний encoder/trellis preview без phase labels і receiver.

Детальні hashes і матриця source-to-code: [M11H_SOURCE_VERSION_MATRIX.md](M11H_SOURCE_VERSION_MATRIX.md). Не використано старішу статтю як мовчазну заміну v7. `paper_exact:false`, `receiver_enabled:false`, SCI-02, SCI-03 і SCI-METRIC-02 залишаються незмінними й відкритими.

## Висновки аудиту

1. **A:** код `src/hf_tcm/coding/encoder.py` має два біти пам'яті, чотири стани і 16 ребер, із парами входу на кожен TCM-символ. Це фактичний encoder HF-TCM-SIM. Прив'язку до конкретного рисунка відсутньої статті v7 не можна повторно засвідчити.
2. **B:** окремий `src/hf_tcm/coding/encoder_b.py` реалізує 16 станів і 64 переходи за доступними рис. 4.6/табл. 4.2 у `Раздел_4.pdf`, з регістровим порядком `(1,3,2,4)` та виходом `(C2,C1,C0)`. Unit/API tests перевіряють переходи та факт, що preview не викликає receiver. Branch parameter `B` не переіменовано в абсолютну фазу.
3. Кодери A і B не змішані. У GUI B використовує окремий preview; запуск A receiver для B недоступний. Немає підтвердженої B phase mapping, channel, metric, trellis termination або Viterbi сумісності.
4. Попередній source audit фіксує різницю `4` проти `8` samples/symbol і `η=20` статті проти повнокадрового project decoder. У M11h visual window перевірено незалежно від decoder: воно не перемикає алгоритм декодування.
5. Наявні AWGN, multipath, Rician і fluctuating-noise модулі залишаються ізольованими від Demo Studio. Вони не дають підстав представляти GUI як повну модель фізичного HF-каналу.

## Реальні можливості GUI

У режимі A користувач редагує binary bits, template чи локальний TXT/CSV, вибирає сумісну receiver policy та змінює підтримувані `alpha_prime`, `K_tilde`, `beta` і deterministic noise fixture. Запуск виконується лише явною кнопкою. Фактичний Edge acceptance порівняв два F=32 прогони: інверсія входу змінила encoded output, передані/прийняті samples і candidate metrics.

Початковий стан A зафіксований на сумісному reset; custom initial state існує тільки у B preview (ID 0–15). `mu0` лишається policy-defined. Gain, stochastic noise/SNR, samples-per-symbol, decoder depth, multipath та Rician параметри не редагуються; для них є документована gap matrix у [M11G_PARAMETER_EDITABILITY_MATRIX.md](M11G_PARAMETER_EDITABILITY_MATRIX.md). Жодного декоративного control немає.

## Вердикт

- `SUPERVISOR_ALIGNMENT_PARTIAL` — висновки для доступного PDF/коду сформульовані, але повну відповідність запитаним source versions встановити не можна.
- `ENCODER_B_PARTIAL` — окремий encoder/trellis preview перевіряється; phase/receiver semantics не вигадані.
- `DEMO_PARTIAL` — runtime, графіки, window, estimator, Viterbi та fullscreen проходять автоматичний acceptance на двох viewport. Візуальний перегляд знімка виявляє щільне перекриття частини edge labels у state-graph trellis; повна читабельність кожного ребра на проекторі не підтверджена.

Історичні M5–M10 артефакти не змінювалися: 694/694 baseline fingerprints збігаються. Новий Monte Carlo, нові stochastic observations і зміни receiver mathematics не виконувалися.
