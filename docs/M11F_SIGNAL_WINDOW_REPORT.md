# M11f — звіт Signal Explorer

## Реалізовано

Додано окремий розділ **Signal Explorer**, що використовує лише фактичний trace M11a після явного натискання запуску. При GET сторінки receiver не запускається. Кодер, transmitter, channel fixture, receiver, metrics, posterior і Viterbi не змінювалися.

Для поточного профілю `8 samples/symbol` побудовано bounded window розміром `min(20×8, N)` комплексних відліків. Для F=32 маємо N=256, тому початки вікна — від 0 до 96 включно, будь-який sample offset. Кнопки рухають вікно на 8 відліків (один символ); окремий symbol selector центрує вибраний символ настільки, наскільки дозволяють межі кадру. Коротший кадр показується фактичною довжиною, без padding.

Приклади перевірено на точному mapping:

| Позиція | sample range, напіввідкритий | символи у вікні | trellis offset |
|---|---:|---:|---:|
| First | `[0,160)` | `0…19` | 0 |
| Middle | `[48,208)` | `6…25` | 6 |
| Last | `[96,256)` | `12…31` | 12 |

Вибраний символ f має відліки `[8f,8f+8)`; деталі показують точні комплексні числа з trace. Огляд кадру відображає Tx I, gain-applied I, noise I та received I із виділеною смугою поточного вікна. Chart selector дає 17 runtime views: input bits, encoded bits, state/edge, phase, constellation, Tx, gain, noise, received, magnitude/phase, observed I/Q, candidate metrics, candidate-edge weights, estimator, Viterbi path, reference/decoded bits і frame BER/SER. Формули, числові операнди, source paths та `?` довідки прив’язані до вибраного символу.

Навігація до trellis передає ті самі межі символів. Перевірка першого, середнього та останнього вікон не знайшла зсуву між sample origin, symbol index, trellis offset і decoded path. Відображений шлях Viterbi залишається результатом одного full-frame запуску над frozen metric sequence. Візуальне вікно не є decoder depth `η=20`.

## Наукові позначки

- `Δφ=π/4` позначено як phase increment; абсолютне phase/edge mapping лишається ADR-002 реконструкцією.
- 16 відображених ваг — project candidate-edge weights, не posterior прихованого стану каналу.
- Metrics показано як фактичний squared-residual production output; неоднозначність [A](2) та `SCI-METRIC-02 OPEN` показані в поясненні.
- Noise — детермінований fixture, не stochastic AWGN/SNR realization.
- BER/SER є single-frame результатом, не статистичним доказом.
- Модель лишається реконструйованою: `paper_exact:false`, `receiver_enabled:false`.

## Перевірка

Додано `src/hf_tcm/studio/static/signal_window.js` із чистими функціями обмеження вікна, символізації sample index і центрування символу; `tests/test_m11f_signal_window.js` покриває F=32 first/middle/last, short-frame, mapping і invalid dimensions. Реальна Microsoft Edge перевірка з F=32 POST пройшла **68/68 checks** на 1366×768 та 1920×1080 сумарно; усі 17 chart types були rendered із actual trace в кожному viewport, GET без POST не створює trace. Перевірено actual 256-sample arrays, перші/середні/останні вікна, synchronized trellis highlight, constellation selection та відсутність `undefined`/`NaN` у ключових показниках. Винятків JavaScript не зафіксовано.

Фактичні знімки екрану збережено у `docs/screenshots/m11f-signal-{first,middle,last,selected-symbol}-{1366x768,1920x1080}.png`; машинний протокол: `tmp/m11f-edge-signal-qa.json`.

