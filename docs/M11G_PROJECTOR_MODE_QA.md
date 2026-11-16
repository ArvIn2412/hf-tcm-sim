# M11g — Projector Mode QA

## Реалізоване

Додано перемикач «РЕЖИМ ПРОЄКТОРА», fullscreen action, згортання sidebar, світлу/темну тему, кнопку переходу до параметрів і згорнуті presenter notes. Кнопки попереднього/наступного символу доступні на верхній панелі; playback, reset 20×8 та перемикання графіків розміщені в Signal Explorer. Стрілки клавіатури змінюють символ, пробіл керує playback поза полями вводу та кнопками.

У projector mode висота основного Signal Explorer card — 600 px на desktop; заголовки збільшуються до 28–34 px, шкали SVG і пояснювальний текст — до 18–20 px. Кольори сигналів і поточної вибірки лишаються роздільними, наукові caveats залишаються видимими. Графи обмежені шириною viewport; короткий вміст має responsive scaling.

## Перевірка

Microsoft Edge headless: 106/106 assertions у двох viewport — 1366×768 та 1920×1080. Перевірені projector layout, відсутність горизонтального overflow, мінімальна висота графіка, dark theme з high-contrast SVG text, collapse/restore sidebar, presenter notes default collapsed, signal navigation, перший/середній/останній windows і B preview. Кнопка довідки перевірена в обох viewport. JavaScript runtime exceptions — 0.

Screenshots збережені в `docs/screenshots/`:

- `m11g-projector-1366x768.png`
- `m11g-projector-1920x1080.png`
- `m11g-first-1366x768.png`, `m11g-middle-1366x768.png`, `m11g-last-1366x768.png`
- `m11g-first-1920x1080.png`, `m11g-middle-1920x1080.png`, `m11g-last-1920x1080.png`
- `m11g-selected-symbol-{1366x768,1920x1080}.png`

## Межі

Fullscreen і keyboard affordances доступні; автоматизований QA перевіряє projector actions/layout у headless Edge, а не фізичний проектор або зовнішню апаратну масштабувальну систему. Демонстраційні значення не є новою статистичною валідацією. Caveats `paper_exact:false` і `receiver_enabled:false` збережені.
