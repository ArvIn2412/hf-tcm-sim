# M11h — Interactive Demo acceptance та візуальна QA

## Перевірена поведінка

Реальний Microsoft Edge запускав поточний локальний Demo Studio у viewport 1366×768 та 1920×1080. Детермінований F=32 fixture виконується лише явним натисканням `Запустити симуляцію`; при GET trace відсутній. На кожному viewport дві послідовні детерміновані симуляції використали різні 64-бітові входи. Порівняння runtime значень підтвердило зміну кодерного виходу, Tx samples, Rx samples та candidate metrics.

Для обох viewport пройшли перевірки:

- whole-frame signal chart і 20×8 sample window;
- 8PSK constellation із реальними точками runtime trace;
- projector signal graph, trellis, recursive estimator і Viterbi results;
- BER/SER summary та пояснення, що це один демонстраційний frame;
- відсутність горизонтального overflow на рівні документа;
- не обрізаний viewport-графік при скриншотуванні;
- Ukrainian per-view explanations;
- перехід між панелями клавіатурою та доступність Previous/Next controls;
- browser fullscreen entry/exit з user gesture;
- відсутність JavaScript runtime exceptions.

Після першого acceptance виявлено, що projector graph trellis використовував 12px labels і низький контейнер. У `studio_ux.css` додано лише projector presentation rules для trellis, estimator і Viterbi: 550px графічні області, збільшені SVG labels/cards і внутрішнє прокручування довгої таблиці. Математичні дані, path і receiver outputs не змінювалися.

## Screenshots

Збережені фактичні Edge captures у `docs/screenshots/`:

- `m11h-signal-1366x768.png`, `m11h-signal-1920x1080.png`;
- `m11h-constellation-1366x768.png`, `m11h-constellation-1920x1080.png`;
- `m11h-trellis-1366x768.png`, `m11h-trellis-1920x1080.png`;
- `m11h-estimator-1366x768.png`, `m11h-estimator-1920x1080.png`;
- `m11h-viterbi-1366x768.png`, `m11h-viterbi-1920x1080.png`;
- `m11h-encoder-b-preview-1366x768.png`,
  `m11h-encoder-b-preview-1920x1080.png`.

Окремо B UI перевірено зі state ID 5 і входом `001011`: він показав фактичну траєкторію `5 → 1 → 8 → 14`, 64 ребра таблиці та статус «Приймач не викликався». Це перевірка encoder preview, не decoder.

Автоматизований звіт: `tmp/m11h-edge-acceptance.json`; harness: `scripts/qa_m11h_supervisor_acceptance.js`. **36/36 assertions passed**, по 18 на viewport.

Після M11h UI змін повторено попередній Signal Explorer harness:
`node scripts/qa_m11g_interactive_projector.js` — **106/106**. First/middle/last
вікна при sample starts 0, 48, 96, TCM synchronization, 8/20/160/full-frame
zoom, 17 chart views і попередні B/projector controls повторно пройшли на обох
viewport.

## Межі та візуальне застереження

Знімки показують, що trellis nodes, branch path і controls масштабуються, але кілька `ee#` підписів у щільному чотиристанному overview візуально зближені/перекриваються. Через вимогу проекторної читабельності ця частина не отримує повну acceptance, попри проходження структурних і розмірних assertions. Для демонстрації окремого переходу доступні zoom/time controls і таблиця edges; це не знімає зазначеного дефекту в оглядовому графі.

Fullscreen перевірено в headless Edge через браузерний Fullscreen API з user gesture. Це не є перевіркою фізичного проектора чи зовнішньої системи масштабування.

`paper_exact:false` і `receiver_enabled:false` видно у demo. Single-run BER/SER — лише результат детермінованого fixture, не нове наукове свідчення.
