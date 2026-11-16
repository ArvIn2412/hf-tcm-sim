# M11g — перевірка Signal Explorer та індексів вікна

## Вікно

Базове вікно Signal Explorer дорівнює 20 TCM symbols × 8 samples/symbol = 160 complex samples. Воно має довільний integer sample offset у межах кадру; кнопки ±1 symbol змінюють початок на 8 samples. Для F=32 і N=256 дозволені старти 0…96, включно. Селектор символу показує його samples `[8f,8f+8)`.

Додані режими перегляду: поточний символ (8 samples), 20 samples, стандартне 20×8, весь кадр; кнопка playback пересуває вікно кроком в один символ. Кадровий overview залишається доступним. В кінці кадру вікно обмежується фактичним N без padding. Вибрані sample/symbol indices відображаються разом із відповідним trellis segment і повнокадровим decoded path.

| Перевірка F=32 | Sample range | TCM symbols | Trellis offset |
|---|---:|---:|---:|
| First | `[0,160)` | 0–19 | 0 |
| Middle | `[48,208)` | 6–25 | 6 |
| Last | `[96,256)` | 12–31 | 12 |

Усі 17 графічних представлень беруть values із поточного A runtime trace. Вибір receiver policy, символу й графіка оновлює фактичні метрики, ваги, estimator values, Viterbi path та reference/decoded comparison. Candidate weights не називаються channel HMM posterior.

## Межа декодера

Поточний conditional Viterbi запускається на повній послідовності metric rows. У M11g вікно змінює лише видиму ділянку сигналу/trellis. Воно не реалізує finite-depth decoder і не означає `η=20`. Статус `paper_exact:false`, `receiver_enabled:false`; A receiver залишається project reconstruction.

## Edge verification

Реальний Microsoft Edge: **106/106 checks**, 1366×768 і 1920×1080, 53 checks на viewport. Перевірено sample starts 0, 48, 96, індекси вибраного символу 31 і його samples 248–255, 8/20/160/full-frame zoom, синхронізацію trellis offset, decoded path, усі 17 графіків та відсутність `undefined`/`NaN` у ключових виводах. Кнопка `?` відкриває Inspector dialog. JavaScript exceptions: 0.

Десять реальних screenshots: `docs/screenshots/m11g-{first,middle,last,selected-symbol,projector}-{1366x768,1920x1080}.png`. Автоматизований протокол у `tmp/m11g-edge-interactive-qa.json`.
