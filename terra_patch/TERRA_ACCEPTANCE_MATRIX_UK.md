# Terra Focus — матриця фактичного приймання

| Перевірка | Стан | Підстава |
|---|---|---|
| JS syntax | PASS | `node --check terra_focus.js` |
| CSS syntax | PASS | `tinycss2` parse без помилок |
| Інсталятор dry-run / apply / undo | PASS | Перевірено на ізольованому дереві `scientific.html` |
| Архів ZIP | PASS | Перевірено CRC усіх записів |
| Мінімальна нова структура навігації | IMPLEMENTED, NOT BROWSER VERIFIED | Є в `terra_focus.js`; реальний UI ще не відкрито |
| Підменю сигналу та збереження стану | IMPLEMENTED, NOT BROWSER VERIFIED | Логіка JS; без E2E |
| Згортання додаткових інструментів | IMPLEMENTED, NOT BROWSER VERIFIED | CSS+JS; без E2E |
| Кирилиця UTF-8 | PASS FOR PACKAGE FILES | Файли записано як UTF-8; старі компоненти не перевірено |
| 320/390/834/1366/1920 | NOT VERIFIED | Browser у середовищі заблокував file:// та localhost |
| Фактичний N=20000 / 160000 sample navigator | NOT VERIFIED | Немає локальної runtime копії |
| Zoom/pan/LOD, BER, trellis, catalog | NOT REGRESSION TESTED | Оригінальні модулі не змінено, але не перевірено у браузері |
| Portable pytest | NOT RUN | Повний актуальний репозиторій у сесії відсутній |
| Historical SHA | NOT RECHECKED | Історичні наукові файли пакет не модифікує |

**Загальний статус:** PARTIAL / готовий для локального UX-приймання. Це не фінальний реліз.
