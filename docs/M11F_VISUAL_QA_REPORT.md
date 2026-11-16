# M11f — візуальна QA

**Середовище:** Microsoft Edge headless, локальний Demo Studio server; viewport 1366×768 і 1920×1080. У кожному viewport виконано тільки один явний deterministic F=32 POST. GET перевірено окремо: trace відсутній, POST не відбувався.

## Результати

- 68/68 браузерних assertions пройшли (оновлений протокол `tmp/m11f-edge-signal-qa.json`), зокрема runtime render усіх 17 типів графіків у кожному viewport.
- Для кожного viewport перевірено 20-symbol window у позиціях first `[0,160)`, middle `[48,208)`, last `[96,256)`; mapping у символи відповідно 0–19, 6–25, 12–31.
- `signal-to-trellis` зберігає window start без індексного зсуву; actual full-frame decoded path доступний на кожному сегменті.
- Перевірено 17 типів графіків за runtime trace, constellation highlight (19 window symbols плюс selected symbol), f=31 із його відліками 248–255 і значеннями без `undefined`/`NaN`.
- JavaScript runtime exceptions: 0.
- Виправлено недостатній контраст SVG tick labels у системній dark theme, надмірну кількість цифр на осях та constellation window highlighting. Скорочені лише axis ticks; values у trace, картках і tooltip лишаються точними.
- Вісім реальних screenshots (чотири позиції на кожному viewport) лежать у `docs/screenshots/m11f-signal-*.png`.

## Межі QA

QA є перевіркою UI та індексної синхронізації на збереженому deterministic fixture. Це не нове receiver evaluation, не stochastic channel run і не доказ paper fidelity. Дозвіл на decoder виконується наявною кнопкою явного POST; сигнал і receiver результат отримані з наявного M11a trace builder.

