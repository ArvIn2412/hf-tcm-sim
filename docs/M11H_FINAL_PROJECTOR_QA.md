# M11h-FINAL — projector trellis QA

Дата: 2026-11-04. Усі перевірки виконані на локальній Demo Studio з детермінованим fixture; Monte Carlo не запускався.

## Зміна відображення

Trellis renderer тепер має два режими:

- **Оглядовий:** renderer зберігає повний набір ребер і станів, але не показує масові edge labels. Для A виділяються conditional Viterbi та reference шляхи й вибраний символ; для B показуються reference/input path та вибраний символ. У B немає Viterbi path.
- **Детальний:** підписується лише вибране ребро; у картці наводяться номер ребра, source/target, input/output bits і доступні для цього режиму дані. Для A доступні runtime phase/metric/posterior, якщо вони є у trace. Для B фаза, метрика і posterior явно позначені як недоступні.
- Кнопка **«Показати всі переходи»** відкриває окрему таблицю з 16 рядками A або 64 рядками B. Ребра не вилучаються з графа чи моделі.
- SVG labels із `hidden` мають явне CSS `display:none`, бо браузерне зображення показало, що самого HTML-атрибута недостатньо для приховування SVG `<text>`.
- Ребра мають назви для screen reader і keyboard focus. A edge selection перевірено фактичним Enter key dispatch у Edge. B SVG ребра focusable; B receiver actions лишаються відключеними.

Зміна стосується лише presentation/preview коду: `studio_ux.js`, `studio_ux.css`, `trellis_projector.js` і відповідних QA/tests. Encoder A/B, receiver math, trace data та історичні artifacts не змінювались.

## Реальна браузерна QA

| Viewport | Результат | Охоплення |
|---|---:|---|
| 1366×768 | Успішно, спільний Edge harness | A 4/16, overview без видимих labels, selected detail, клавіатурний вибір, show-all table; B 16/64, overview без labels, preview path, unavailable scientific fields, 64-row table; projector signal/estimator/Viterbi/constellation; без page-level horizontal overflow/runtime exceptions |
| 1920×1080 | Успішно, спільний Edge harness | Те саме покриття на другому розмірі; браузерний fullscreen і keyboard navigation також пройшли |
| Разом | 50/50 trellis acceptance checks у двох viewport | Рівномірно пройшли обидві конфігурації; harness перевірив кожну в окремій сесії |
| Signal Explorer | 106/106 checks сумарно на двох viewport | first/middle/last 20-symbol windows, їх sample offsets, selected-symbol 8 samples, 20-sample zoom, full-frame reset та синхронізація з time trellis/Viterbi path |

Для F=32 положення 20-символьного вікна мають початки 0…12; QA перевіряє sample starts 0, 48, 96 для першого, середнього й останнього вікон. У кожному повному вікні 160 samples; вибраний TCM-символ відповідає рівно 8 samples. Граф B має внутрішню прокрутку/панорамування для повної 16×64 решітки на вузькому viewport; сторінка не отримує горизонтального overflow.

## Збережені реальні скриншоти

Усі наведені файли зроблені Edge harness із локальної сторінки після явного deterministic POST або B preview:

- A overview: `docs/screenshots/m11h-trellis-1366x768.png`, `docs/screenshots/m11h-trellis-1920x1080.png`.
- A selected-edge detail: `docs/screenshots/m11h-trellis-detail-1366x768.png`, `docs/screenshots/m11h-trellis-detail-1920x1080.png`.
- B 16-state/64-edge graph: `docs/screenshots/m11h-encoder-b-trellis-1366x768.png`, `docs/screenshots/m11h-encoder-b-trellis-1920x1080.png`.
- B preview/transition table: `docs/screenshots/m11h-encoder-b-preview-1366x768.png`, `docs/screenshots/m11h-encoder-b-preview-1920x1080.png`.
- Інші signal, estimator, Viterbi та constellation screenshots: `docs/screenshots/m11h-*.png`.

## Підсумкові межі

Візуальна проблема масового накладання edge labels усунена і перевірена за обчисленою CSS-видимістю в реальному браузері. Огляд не приховує жодного переходу; за потреби точні підписи відкриваються для окремого ребра або таблицею. B залишається encoder/trellis preview без підтвердженої фази чи сумісного decoder. Це не робить комплекс paper-exact: `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN.

Вердикти: `PROJECTOR_TRELLIS_READY`; `ENCODER_B_PARTIAL`; source alignment remains incomplete because requested supervisor versions are missing.
