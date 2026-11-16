# REPRO-10A — перевірка експорту графіків

## Дефект і виправлення

Архівний `hf-tcm-run-20261110-115613-8afe3624-chart-tx-k0.png` мав розмір 300×310, але alpha extrema `(0,0)`: жодного непрозорого пікселя. Причиною був порядок асинхронної роботи GUI: summary вмикав кнопку до завершення `loadWindow()`/`drawAll()`, тому `toDataURL()` серіалізував початковий прозорий canvas. Це не був дефект transmitter samples.

Тепер кожен canvas позначає стан `exportRendered`; export button залишається вимкненим, поки відповідне полотно фактично не намальоване. Chart renderer спочатку заливає білий фон, потім малює реальні дані, осі, легенду і заголовок. Canvas для BER/DeltaBER має таку саму політику, включно з порожнім статистичним набором. Перевірка PNG виконується декодуванням зображення і контролем розмірів, alpha, кольорів та ненульової графічної інформації; сам SHA не вважається доказом.

Решітка Вітербі експортується як SVG із вбудованим стилем і білим фоном. Експортуються лише фактичні rendered paths із decoder diagnostics.

## Реальна Edge QA

QA запуск `scripts/qa_repro09b_scientific.js` використовував Edge/CDP, GUI server та фактичні Identity, Static multipath, Rician і Monte Carlo runs. Усі PNG нижче декодовані браузером після завантаження та пройшли content checks.

| Графік | Розмір | Непрозорі пікселі | Небілі пікселі | Результат |
|---|---:|---:|---:|---|
| Transmitted I/Q | 800×300 | 240000 | 14655 | 68 sampled colors, PASS |
| Received I/Q | 800×300 | 240000 | 14814 | 60 sampled colors, PASS |
| Joint metrics | 800×300 | 240000 | 24233 | 172 sampled colors, PASS |
| Hamming metrics | 800×300 | 240000 | 20836 | 142 sampled colors, PASS |
| Bit error positions | 800×300 | 240000 | 7736 | 29 sampled colors, PASS |
| Monte Carlo BER | 581×250 | 145250 | 6006 | 27 sampled colors, PASS |

Вибірка кольорів для PNG містила 27–172 різні значення; кожен файл мав видимий вміст. Viterbi SVG містив 90 реальних edge paths, inline style та `viewBox="0 0 1000 500"`.

## Кодування тексту

HTML декларує `lang="uk"` та `<meta charset="utf-8">`; HTTP server додає `charset=utf-8` для text/JavaScript/JSON responses; JSON серіалізується з `ensure_ascii=False`; SVG має UTF-8 MIME type. Edge перевірив `document.characterSet == UTF-8`, коректний напис `Зберегти PNG` та завантажений SVG. У вихідному export label було mojibake; його замінено на UTF-8 текст. Scientific Workspace використовує символи η, γ, Δ, `8PSK`, `I/Q`, `BER/SER` у наявних UTF-8 UI рядках.

## Скріншоти

Післяфіксові скріншоти Edge збережені у `docs/screenshots/repro10a-*`: transmitter, channel, Joint, Separate, comparison, Viterbi і Monte Carlo при 1366×768; transmitter, channel та long-frame viewer при 1920×1080.

Архівний F=20000 viewer показує тільки збережені metrics/trellis diagnostics. Якщо старий архів не має I/Q traces, viewer і надалі явно каже, що сигнал недоступний; дані не реконструюються.
