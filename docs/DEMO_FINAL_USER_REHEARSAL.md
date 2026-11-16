# Фінальна інструкція користувачу для демонстрації

Цей документ — операторський сценарій. Browser rehearsal, виконаний через Edge DevTools Protocol, перевіряє взаємодії інтерфейсу, але **не є особистою репетицією доповідача**.

## Перед захистом

1. Відкрийте корінь проєкту.
2. У Windows найпростіше запустити `start_demo.cmd`. Альтернатива з консолі: `python -m hf_tcm.demo_studio`.
3. Відкрийте локальну адресу, яку покаже launcher; типовий порт — `8765`, адреса має починатися з `http://127.0.0.1:`.
4. Перейдіть на «Демонстраційна симуляція». Переконайтеся, що preset «Захист магістерської · F=32» вибраний.
5. Натисніть **«Запустити демонстрацію»**. GET сторінки не запускає receiver.
6. Перевірте повідомлення про 32 symbols / 256 samples / `RNG used: false`, спільний received SHA-256 і мітку **DETERMINISTIC DEMONSTRATION · NOT SCIENTIFIC EVIDENCE**.

## Рекомендований шлях через GUI

1. **Pipeline:** почніть з 28 етапів; відкрийте stages 01–08, щоб зв’язати біти, encoder, стани, ребра, mapping, 8PSK та waveform.
2. **Trellis:** відкрийте «Приховані стани та решітка TCM». У режимі State-transition graph покажіть усі чотири стани й edge detail table з 16 рядками. Виберіть **edge 10** у таблиці; перевірте його підсвічення на графі. За бажанням натисніть ребро на графі й покажіть синхронізацію selector.
3. **Symbol:** відкрийте «Дослідити символ» і поставте **f=15**. Покажіть input pair, стан, edge, фазу та вісім абсолютних sample indices із Tx/noise/received values.
4. **Точні таблиці:** відкрийте таблицю 16 candidate edges з prediction, metric і posterior; перевірте, що posterior normalized.
5. **Оцінювач:** відкрийте «Рекурсивне оцінювання». Назвіть `alpha_prime`, `K_tilde`, `mu0`, beta; прочитайте `s pre`, full pre, innovation, post state та tick.
6. **Viterbi:** відкрийте режим time-expanded trellis. Розрізняйте hypothesis edge, decoded Viterbi path і reference encoder path.
7. **Порівняння:** відкрийте «Порівняти два приймачі» й покажіть same received hash та однакову вибрану позицію для `historical_frozen_B` і `anch_a085_k025`.
8. **Inspector:** відкрийте «Усі параметри». Для вибраного f шукайте `runtime.candidate_metrics`, `runtime.posterior_weights`, `runtime.estimator_pre_state`, `runtime.estimator_post_state`, `runtime.viterbi_decision`, `runtime.BER`, `runtime.SER`; перевірте значення і джерело. Шукайте `noise.sigma_squared`, `profile.gamma_b_eff_db`, `historical.M9b.delta_ber_ci`, `historical.M10b.primary_delta_ber_ci` для конфігурації та archived provenance.
9. **Архівні експерименти:** покажіть M5j, M7b, M8b recovery, M9b і M10b. Для M9/M10 скажіть, що інтервали DeltaBER містять нуль. Не представляйте M7b TRAIN ranking як independent validation.
10. **Презентація:** відкрийте «Захист магістерської», користуйтеся Next/Previous. Inspector доступний окремою навігацією, повернення до presentation не вимагає перезапуску. Завершіть кроком 18, натисніть Return to detailed view.

## Сценарій на 8–10 хвилин

Використайте повний 18-кроковий [сценарій презентації](DEMO_PRESENTATION_SCRIPT.md), розрахований на 8:45. Обов’язково покажіть edge table, один вибраний edge, symbol 15, усі 16 метрик/posterior values, causal update, умовний Viterbi path, raw BER/SER і saved M9/M10 CI.

## Стиснений сценарій на 5 хвилин

1. **0:00–0:30:** архітектура, fixed F=32, no RNG.
2. **0:30–1:20:** чотири стани, 16 ребер, вибір edge 10 та граф/table sync.
3. **1:20–2:00:** 8PSK phase, waveform, 8 samples/symbol, explicit channel/noise.
4. **2:00–3:00:** symbol 15, observed IQ, 16 predictions, metrics і posterior.
5. **3:00–3:50:** причинна рекурсія та conditional Viterbi decoded path.
6. **3:50–5:00:** fixture BER/SER, M9/M10 saved intervals, наукові обмеження.

## Аварійний сценарій на 2 хвилини

Якщо live GUI не відновився за хвилину, не видавайте screenshot за live run. Покажіть [1366×768 screenshot](screenshots/m11b-edge-1366x768.png) як знімок інтерфейсу, [1920×1080 screenshot](screenshots/m11b-edge-1920x1080.png) як додаткову ілюстрацію та цей звіт як provenance. Усно проговоріть: deterministic F=32; 4 reconstructed states / 16 edges; один fixture не є performance evidence; M9 і M10 CI містять нуль. Для цифр відкрийте `DEMO_PRESENTATION_SCRIPT.md` або `DEMO_DEFENSE_QA.md`. Чітко позначте, що це резервне статичне пояснення, не live scientific execution.

## Відновлення при збоях

| Ситуація | Ознака | Точна дія | Очікуваний результат | Безпечний fallback |
|---|---|---|---|---|
| A. Браузер закрився | Сервер лишився у консолі, вкладки немає | Відкрийте адресу, яку launcher надрукував, наприклад `http://127.0.0.1:8765/` | Локальна сторінка знову завантажиться; trace треба запускати явною кнопкою, якщо він не зберігся в новій вкладці | Перезапустити F=32 explicit demo; якщо не встигаєте, перейти до аварійного 2-хвилинного сценарію |
| B. Локальний сервер зупинився | URL не відповідає, у консолі процес завершився | Із кореня запустіть `start_demo.cmd`; за потреби `python -m hf_tcm.demo_studio` | Launcher покаже localhost адресу; працюючий процес залишайте у відкритій консолі | Використайте статичний аварійний сценарій, не заявляючи live обчислення |
| C. Порт уже зайнятий | Launcher повідомляє `Port ... is already in use` | Перевірте надрукований URL; якщо це не demo, запустіть `start_demo.cmd -Port 8766` | Новий GUI відкриється на `http://127.0.0.1:8766/`; traceback Python не приховується | Якщо порт не звільняється, використайте screenshots як ілюстрацію |
| D. Demo POST повернув помилку | У статусі видно `Demo failed: ...` | Прочитайте повідомлення, виберіть preset F=32, перевірте, що custom поля не редагувалися, натисніть кнопку ще раз один раз | Валідний preset виконається або покаже помилку збереженого середовища | Використайте F=4 smoke лише для перевірки GUI; не підміняйте ним наукові числа. За повторної помилки переходьте до статичного fallback |
| E. Архівний dataset недоступний | Dashboard показує `UNAVAILABLE` чи `AGGREGATE_ONLY` | Залиште статус як є; відкрийте coverage matrix і поясніть schema limitation | Інші доступні artifacts лишаються видимими, відсутні traces не вигадуються | Покажіть лише збережене джерело/summary з явною міткою недоступності |
| F. Немає інтернету | Інтернет недоступний | Нічого не змінюйте; GUI запускається локально | Сторінка, deterministic POST і архівні локальні файли працюють без cloud/API | Якщо локальне середовище також недоступне, використайте скриншоти й 2-хвилинний fallback |

## Завершення

Скажіть: «Модель реконструйована, `paper_exact:false`, `receiver_enabled:false`. Receiver mathematics не змінювалася. M9/M10 intervals включають нуль; одинична демонстрація не є науковим доказом. SCI-02, SCI-03 і SCI-METRIC-02 залишаються відкритими». Не починайте M12 з цього комплекту.
