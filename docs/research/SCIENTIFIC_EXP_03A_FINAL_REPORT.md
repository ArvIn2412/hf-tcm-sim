# SCIENTIFIC-EXP-03A — фінальний звіт підготовки

**Статус: `SCIENTIFIC_EXP_03A_READY` для контрольованого порівняння метрик та обмежених range-finding пілотів.** Це не підтвердження ефективності, не дозвіл на автоматичний запуск 03B і не результат confirmatory-серії.

## Рішення і межі

- **[ПРОЄКТ]** Зафіксовано спільний pilot frontend та clean-tail combiner для пар A-E/A-H. У межах однієї пари декодери отримують однакові передані дані, observation, рівняні символи frontend, оцінки каналу, маску пілотних обмежень, решітку Encoder A, η=20 і правила traceback. Відрізняється лише спосіб обчислення гілкових метрик: squared complex Euclidean проти hard 8PSK label + Hamming distance.
- **[ПРОЄКТ]** AWGN-only, пряме усереднення восьми відліків, без пілотів та equalizer, реалізоване окремо як базовий контроль метрик.
- **[ПРОЄКТ]** Oracle-CSI — окремий діагностичний frontend. Його записи не входять до практичних BER чи енергетичних підсумків.
- **[ПРОЄКТ]** Існуюче порівняння повних Joint/B0/B1 приймачів залишається окремим системним контрастом. Його не можна тлумачити як ізольований ефект метрики.
- **[СТАТТЯ]** Encoder A узгоджується з перевіреними переходами, наведеними в REPRO-01/02 crosswalk. Точна тотожність активного адаптивного оцінювача та всього каналу статті не встановлена; `paper_exact:false` збережено.

## Реалізація

Нові ізольовані модулі: `src/hf_tcm/repro/metric_isolation.py` та `metric_experiment.py`. Це не заміна `Joint`, B0 або B1. Передавач, канал і чинні receiver implementation SCIENTIFIC-EXP-01B/02 не переписувалися. Фронтенд приймає `ReceiverObservation`; `EvaluationTruth` не входить до його API і читається тільки evaluation-diagnostics після декодування обох arms.

Для цілочисельних затримок `D<8` і восьми sample ZOH clean-tail відліки одного символу лежать у межах того самого переданого символу. Для максимального delay `D` беруться `8-D` відліків із `8k+D … 8k+7`; тому внеску попереднього символу в цій підмножині немає. Це exact clean-tail combiner саме для вказаного waveform/delay класу, а не загальний inverse equalizer або рішення для дробових затримок, delay ≥8, довільного pulse shaping чи повної sample-domain ISI MLSE.

Pilot estimates причинні: відлік `k` обробляється доступною попередньою оцінкою, відома пілотна фаза може оновити оцінку тільки після її спостереження. У Rician каналі оцінка є застарілим скалярним composite gain і не моделює повний sample-varying vector combiner. Тому пілотний режим є узгодженим спільним frontend для порівняння метрик, але його похибка tracking — частина обмежень обох arms.

## Виконані range-finding дані

Незалежний validator перевірив 9 незмінних пілотних study manifests, 205 завершених парних trial records, 205 відновлених із received samples observation hashes, відповідність парних observation/frontend hashes, незалежний перерахунок помилок із NPZ decoded bits і дискретної енергії. Записи мають `phase=range_finding`; вони не використовуватимуться як confirmatory observations.

| Сценарій / режим | Пілотна сітка, відносний dB зсув | Кадри на точку | BER A-E, стислий результат | BER A-H, стислий результат | Висновок для target 0,05 |
|---|---:|---:|---|---|---|
| AWGN direct, без equalizer | −18…−12 dB (уточнені точки −18, −16,5, −15; первинні −15, −12, −9, −6, −3) | 5 | на уточненій сітці 0,1438; 0,0992; 0,0078 | 0,2398; 0,1609; 0,0742 | A-E перетин локалізовано; для A-H треба нижча енергія, перетин у межах саме трьох уточнених точок не виміряний |
| AWGN, pilot frontend | −15…−3 та −12…−7,5 dB | 5 | на розширеній сітці 0,0188; 0,0170; 0; 0 | 0,0625; 0,0679; 0,0313; 0,0071 | малі вибірки й немонотонність біля target; gain непридатний до висновку |
| Static multipath `[0,3]`, taps `1`, `0,3−0,2j` | −15…−3 та −13,5…−9 dB | 5 | уточнено: 0,0473; 0,0054; 0,0089; 0 | 0,1598; 0,0804; 0,0723; 0,0339 | A-E й A-H мають точки по обидва боки на об'єднаній pilot сітці, але 5 кадрів/точку та шумна крива не дають оцінки виграшу |
| Rician AR(1), pilot period 32 | −15…−3 та −3…9 dB | 5 | у розширеній сітці від 0,2223 до 0,0786, далі 0,1911 | 0,2607…0,1723…0,2714 | жоден arm не досяг 0,05; перетину немає у виміряному діапазоні |
| Rician AR(1), period 8 sensitivity | −3…9 dB | 5 | 0,0406; 0,0141; 0,0297; 0,0094; 0,0297 | 0,1047; 0,0938; 0,0922; 0,0844; 0,1016 | A-E весь діапазон нижче цілі, A-H весь вище; перетинів обох кривих для gain немає; pilot overhead 50% |

Різкі нульові BER оцінки для п'яти кадрів на точку не є доказом BER=0. Пілотні криві мають шумну та в окремих ділянках немонотонну форму. Не заявляємо error floor: відсутність перетину означає лише відсутність виміряного перетину в обмеженій сітці.

## Rician tracking та еквівалентне спостереження

Для основної pilot-схеми період 32, кадр F=128, використано 16 pilot symbols із 128 (12,5% часових та енергетичних символів; 112 payload symbols/224 information bits). Tracking оцінка composite gain відставала в середньому на 14,5 символа, максимум 28. Оцінка коефіцієнта мала RMS похибку близько 0,625; зміна composite gain усередині clean-tail вікна близько 0,102 RMS. Після equalizer residual symbol RMS становив приблизно 1,137 за номінальної амплітуди 1. Теплова складова вихідного шуму мала lag-1 кореляцію близько 0,093; це не ідеально незалежний шум. Period 8 зменшив середній вік оцінки приблизно до 2,5 символа, але вимагає 64/128 pilot symbols (50%) і не зняв невизначеність Hamming перетину.

Для усіх каналів clean-tail ISI-внесок у межах цього дискретного профілю чисельно був близьким до машинного нуля. Це не означає нульового канального залишку: часовий variation Rician і stale/noisy channel estimate залишають multiplicative distortion. Вихідні зразки після pilot equalizer не можна вважати незалежними CN шумом однакової дисперсії: оцінка, повторно використана між пілотами, вносить спільну невизначеність, а Rician gain змінюється у часі.

## GUI та якість

Scientific Workspace містить окрему вкладку «Порівняння метрик», окрему від «Порівняння способів приймання». У браузері виконано реальний запуск однієї static `[0,3]` metric pair з GUI, відкрито збережену 25-trial Rician period-8 серію після manifest verification, перевірено PNG/SVG export BER/SER та перемикання окремих кривих. Edge QA: **5/5 checks PASS**. Screenshots з viewport 1366×768 та 1920×1080: `docs/screenshots/scientific-exp03a-metric-rician-1366x768.png`, `...1920x1080.png`.

Експортовані PNG не прозорі та мають нетривіальні pixels: BER 722×300 (23 088 bytes, 384 RGB colors), SER 722×250 (19 648 bytes, 289 RGB colors). SVG є валідними XML із українськими/математичними підписами та графічними шляхами/точками. Browser QA перевірено з `outputs/scientific-exp03a/validation/edge_gui_qa.json` і `export_validation.json`.

## Продуктивність і regression

Bounded in-memory benchmark (5 пар, F=128; без запису trial files): AWGN direct 0,0344 s/пару; AWGN pilot 0,0337; static `[0,3]` 0,0352; Rician period 32 0,0370; period 8 0,0397. Це не прогноз для великих кадрів: disk, manifests і scaling не включені. Консервативна оцінка лінійного перерахунку на 1024 symbols — близько 0,28–0,32 s/пару до I/O; для фіксованої 9-точкової ×100 trial ×3 channel сітки — орієнтовно 13–15 хв чистого decode/generation, але необхідно зробити новий runtime pilot на F=1024 перед budget sign-off.

Фінальні команди та логи лежать у `outputs/scientific-exp03a/validation/`. `python -m pytest -q --basetemp tmp/pytest-exp03a-final -p no:cacheprovider`: **1256 passed**. Таргетований новий suite: **17 passed**. Scoped Ruff check і format для змінених Python модулів: PASS; Node syntax: PASS. Edge QA: **5/5**; незалежний recount: **9 studies / 205 records PASS**; історичний verifier: **694/694**, 76/76 REPRO-06B files; EXP-02 integrity verifier: PASS, 2160 source confirmatory frames незмінні. PNG/SVG content validation: PASS.

Repo-wide `ruff check .` запускався, але не є чистим: denied ACL paths і 136 знайдених існуючих lint findings у всьому дереві (включно зі scratch `tmp` файлами); усі scoped змінені Python файли проходять. `ruff format --check .` запускався, але Ruff traversal падає з `Expected a ruff source file` на не-source вмісті. Перша паралельна full pytest спроба мала один 30 s timeout у незміненому EXP-02 HTTP route при одночасному Edge-сервері та важкому integrity scan; цей конкретний тест повторно пройшов за 11,36 s, після чого послідовний повний запуск пройшов 1256/1256 за 348,93 s. Це діагностовано як тимчасове навантаження/конкуренція ресурсів; застосункові файли цього маршруту не змінювалися.

## Висновок

Контрольоване A-E/A-H порівняння реалізоване для AWGN direct baseline та для спільного pilot frontend з clean-tail combiner у static/Rician профілях, з однаковими observations і trace semantics. Для `[0,3]` математичне скорочення ISI є точним за прийнятих integer-delay/ZOH умов; для Rician залишаються значні tracking/внутрішньосимвольні зміни й корельований ефективний шум. Тому даний адаптер придатний для підготовленого дослідження **впливу метрики умовно на цьому frontend**, але не доводить повної фізичної оптимальності метрик у fading каналі.

Основна SCIENTIFIC-EXP-03B confirmatory series не запускалася. Поточний runner навмисно приймає тільки `validation` і `range_finding`; confirmatory execution вимагає окремого затвердженого implementation/review gate. Рекомендація: спершу заморозити практичну pilot cadence/CSI проти temporal Rician coherence та окремий fair full-receiver design; потім окремо дозволити 03B. `paper_exact:false`; статейні 1,5 дБ і фізичний `Eb/N0` не підтверджені. Загальний `SCIENTIFIC_EXP_03A_READY` стосується підготовленої контрольованої metric-isolation інфраструктури з переліченими межами, а не готовності Rician energy gain або source-exact reproduction заявляти.
