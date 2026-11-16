# M11j — Звіт браузерної QA

**Результат: PASS — 50/50 перевірок M11j** у Microsoft Edge при viewport **1366×768** та **1920×1080** (25 на кожен розмір).

## Перевірені взаємодії

- Початкова сторінка — Моделювання. GET залишає `app.trace` порожнім і не запускає receiver.
- Шість україномовних розділів, навігація Previous/Next і контекстна довідка працюють.
- Кнопка проекторного режиму на сторінці Моделювання перемикає projector styles.
- Явне натискання кнопки запускає детермінований F=32 POST та створює один активний run із 256 відліками.
- «Переглянути сигнал» відкриває сторінку відліків; перехід signal-to-trellis відкриває синхронізовану TCM решітку.
- Вікно 20 символів містить 160 відліків. Для F=32 перше/середнє/останнє вікна починаються на відліках 0/48/96 і закінчуються на 160/208/256. Окремий detail mode має 20 відліків.
- Вибрана частина trellis і decoded path відповідають візуальному вікну. Сторінка розрізняє visual window і Viterbi traceback depth.
- Десять етапів сигналу відображають графік із фактичного trace.
- Channel hidden-state дані явно мають статус `UNAVAILABLE`; траєкторії Markov каналу не вигадуються.
- Вкладки metrics, estimator та Viterbi відображають графіки. Поточні результати та архіви розділено.
- Зміна підтриманого параметра зберігає старий результат і встановлює `STALE`.
- Проєкторний режим не має горизонтального overflow; мінімальна висота основної signal-картки — 600 px на desktop.
- Кадр F=4 показує 32 фактичні відліки без padding.

## Скріншоти

| Сторінка | 1366×768 | 1920×1080 |
|---|---|---|
| Моделювання | [скриншот](screenshots/m11j-simulation-1366x768.png) | [скриншот](screenshots/m11j-simulation-1920x1080.png) |
| Відліки, проекторний layout | [скриншот](screenshots/m11j-samples-projector-1366x768.png) | [скриншот](screenshots/m11j-samples-projector-1920x1080.png) |
| Етапи сигналу | [скриншот](screenshots/m11j-signal-stages-1366x768.png) | [скриншот](screenshots/m11j-signal-stages-1920x1080.png) |
| Channel states недоступні | [скриншот](screenshots/m11j-hidden-channel-unavailable-1366x768.png) | [скриншот](screenshots/m11j-hidden-channel-unavailable-1920x1080.png) |
| Viterbi | [скриншот](screenshots/m11j-decoding-viterbi-1366x768.png) | [скриншот](screenshots/m11j-decoding-viterbi-1920x1080.png) |
| Результати | [скриншот](screenshots/m11j-results-1366x768.png) | [скриншот](screenshots/m11j-results-1920x1080.png) |

Суміжний браузерний suite інтерактивних елементів M11g також пройшов: **106/106** для обох viewport. Результат збережений у `tmp/m11g-edge-interactive-qa.json`.

## Межі висновків

QA перевіряє реалізовані сторінки та взаємодію з детермінованим fixture. Вона не доводить статистичну перевагу, фізичну модель HF-каналу, наявність приймача Encoder B або paper-exact fidelity. Залишаються `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN.
