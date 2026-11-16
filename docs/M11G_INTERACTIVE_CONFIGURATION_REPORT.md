# M11g — інтерактивне налаштування та запуск

## Результат

Інтерактивне введення для кодера A і source-derived preview кодера B реалізовані. Кодер A запускає наявний deterministic simulation/receiver лише після явної кнопки «Запустити симуляцію». Кодер B формує вихідні біти, послідовність станів і повну таблицю 16×4 trellis; запуск приймача для нього вимкнений.

Інформаційний ввід приймає лише `0` і `1` та пробіли, вимагає парну кількість бітів без padding або truncation. Межі UI: A — 2–64 біти, B preview — 2–256 бітів. TXT/CSV приймаються локально; заголовки, сторонні символи, зайві роздільники та некоректну довжину відхиляє валідатор. Доступні шаблони: перевірений F=32 preset, alternating, усі нулі, усі одиниці та довільне введення.

Кнопки `?` біля вибору encoder, бітового вводу, файлу, початкового стану та підтримуваних параметрів відкривають Inspector з одиницями/обмеженнями, поясненням і provenance.

Параметри `alpha_prime`, `K_tilde` I/Q, `beta`, policy та deterministic noise fixture передаються через наявний `/api/demo`. Модель каналу та параметри M5–M10 цим інтерфейсом не змінюються. Під час редагування inputs/config активний trace очищається, щоб у графіках не залишалися результати від попереднього запуску.

## Кодер і межі моделі

- **A:** наявний 4-state / 16-transition encoder і сумісний з ним поточний trace builder. Початковий стан — сумісний reset `00`; UI не дозволяє невідповідний override.
- **B:** окремий `coding/encoder_b.py`, 16 станів / 64 переходи. Джерельно визначені генераторна матриця й таблиця переходів; UI показує лише encoder/trellis preview. Немає фазової інтерпретації параметра B, channel/IQ тракту для цієї моделі чи сумісного Viterbi receiver.
- Для обох режимів `paper_exact:false`; `receiver_enabled:false` лишається науковим fidelity flag. A має робочий демонстраційний receiver path, але це не твердження про paper-exact приймач.

## Параметри та результати

Докладна editability/gap matrix і незалежний план Channel Simulation Sandbox наведені в `M11G_PARAMETER_EDITABILITY_MATRIX.md`. Наявний single-frame BER/SER показується лише як результат цього fixture, не як статистичне підтвердження. Порівняння наявних receiver policy працює за спільного received buffer у режимі A.

## Перевірки

- Encoder B unit/trellis/API tests: включені в загальний pytest.
- Інтерактивний ввід і sample-window helper: Node tests.
- Edge acceptance: 106/106 перевірок сумарно на 1366×768 і 1920×1080.
- Перевірено явний F=32 POST, ручний invalid input, TXT/CSV import, preset, відключення B receiver, фактичну таблицю 64 переходів, відсутність stale trace, повний Signal Explorer, projector theme/sidebar та runtime exceptions.
- Кожен Edge viewport виконує один детермінований F=32 demo POST; випадкові/Monte Carlo запуски не виконувалися.

## Статус

`INTERACTIVE_INPUT_READY` — для підтримуваного режиму A та окремого B preview. `ENCODER_A_READY` — demo path. `ENCODER_B_PARTIAL` — encoder/trellis preview без фазового відображення та receiver. Scientific model status лишається `PAPER_PARTIAL`; SCI-02, SCI-03 і SCI-METRIC-02 відкриті.
