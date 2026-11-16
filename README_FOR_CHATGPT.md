# HF-TCM-SIM — незалежний аудит SCIENTIFIC-EXP-03B

## Призначення пакета

Архів містить завершений confirmatory набір SCIENTIFIC-EXP-03B для незалежної перевірки контрольованого порівняння метрик Вітербі та окремого порівняння повних приймачів. Він включає всі первинні JSON/NPZ записи 31 100 підтверджувальних trials, аналіз, графіки, вихідний код, протокол, звіти й маніфест SHA-256. Жоден confirmatory trial у межах підготовки фінального звіту не перезапускався.

## Структура

- `outputs/scientific_exp03b/metric/confirmatory/` — 22 800 пар A-E/A-H у 5 сценаріях і 2 sweep-ах.
- `outputs/scientific_exp03b/system/confirmatory/` — 8 300 парних кадрів повних систем Joint/B0/B1.
- `outputs/scientific_exp03b/analysis/independent_analysis.json` — незалежно агреговані BER/SER/FER, енергії, CI, перетини та runtime.
- `outputs/scientific_exp03b/analysis/analysis_manifest.json` — хеш аналізу й перевірки системного масиву.
- `docs/research/SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md` та `SCIENTIFIC_EXP_03B_PROTOCOL_AMENDMENT.md` — незмінний дизайн і передекспериментальна поправка.
- `docs/research/SCIENTIFIC_EXP_03B_*.md` — фінальні звіти.
- `docs/research/THESIS_CHAPTER_4_*.md` — текст розділу 4 та реєстр таблиць/рисунків.
- `docs/research/figures/SCIENTIFIC_EXP_03B/` — 59 PNG і 59 векторних SVG; контрольні суми — у `FIGURE_EXPORTS_MANIFEST.json`.
- `docs/research/tables/SCIENTIFIC_EXP_03B/` — усі 76 точок метричного блоку й 195 записів по arms системного блоку у CSV.
- `scripts/analyze_scientific_exp03b.py`, `scripts/render_scientific_exp03b_figures.py`, `scripts/reanalyze_scientific_exp03b_system.py`, `scripts/write_scientific_exp03b_reports.py` — аналіз, графіки, повторне агрегування та звіти.
- `src/hf_tcm/` і `tests/repro/` — реалізація та регресійні/незалежні перевірки.
- `references/` — основна й альтернативна редакції статті та допоміжне джерело `Раздел_4.doc`, разом із вихідними контрольними сумами.

## Дизайн і основні результати

**Блок A — ізольований ефект метрики.** A-E та A-H отримують парні спостереження та однаковий pilot frontend/equalizer, оцінки каналу, кодову решітку й traceback η=20; відрізняється branch metric. Для BER=0,05 модельний discrete-energy gain Евклідової метрики становить:

- AWGN direct control: 2,8668 дБ, 95% paired cluster bootstrap CI [2,8197; 2,9140].
- AWGN із pilot frontend: 2,2960 дБ, CI [2,1586; 2,4236].
- Static multipath [0,3]: 2,4373 дБ, CI [2,3375; 2,5335].
- Primary Rician AR(1): `ENERGY_GAIN_NOT_ESTIMABLE`; обидві BER-криві не перетнули 0,05 у замороженій сітці. Евклідова метрика мала нижчий BER у виміряних точках, але це не дає необхідної енергії для спільного target.

**Блок B — повні системи.** AWGN Joint/B0 при BER=0,05: точкова оцінка 1,6664 дБ, CI [1,2921; 2,0016], 99,02% валідних bootstrap-перетинів. Static Joint/B0 і Joint/B1 мають лише точкові оцінки, бо валідні перетини становлять 94,68% і 94,94% (поріг протоколу 95%). У Rician B0 не перетинає BER=0,05, тому Joint/B0 gain не оцінюється.

Усі energy gain значення використовують дискретну project-defined шкалу `γ_b,d`, а не фізично відкаліброване Eb/N0. Число 1,5 дБ зі статті є тільки зовнішнім орієнтиром. Його не відтворено як статейний результат; `paper_exact:false` залишається.

## Питання для незалежної перевірки

1. Чи відповідають усі records frozen protocol, trial IDs унікальні, а SHA-256/парні observation hashes узгоджені?
2. Чи незалежний перерахунок BER/SER/FER із decoded bits збігається з агрегатами?
3. Чи коректно застосовано paired cluster bootstrap та критерій мінімуму 95% валідних перетинів?
4. Чи правильно відокремлені блок A (ефект метрики) і блок B (ефект повної технології)?
5. Чи є висновки щодо Rician і статейних 1,5 дБ обережними та статистично допустимими?
6. Чи відповідають графіки числовим таблицям і чи справді SVG є векторними?

## Важлива примітка щодо стану протоколу

`SCIENTIFIC_EXP_03B_FROZEN_PROTOCOL.md` збережено як первісний immutable дизайн-документ, у якому на момент freeze стан запуску був `NOT STARTED`. Подальша версія `SCIENTIFIC_EXP_03B_PROTOCOL_AMENDMENT.md` закріпила confirmatory процедуру до початку вимірювань. Фактичний стан завершення підтверджують 13 завершених study manifests, їхні checkpoints, per-trial hashes і `confirmatory_execution_state.json`.

## Фінальна перевірка пакета

- Підтверджувальні результати не запускалися повторно: у маніфестах залишаються 22 800 пар блока A та 8 300 кадрів блока B.
- Повторний повний набір: `python -m pytest -q -p no:cacheprovider` — 1 286 passed за 131,31 с. Перший повний запуск мав один тимчасовий HTTP timeout у тесті відкриття історичної серії EXP-01B; ізольований тест пройшов за 5,24 с, а повний повтор завершився без помилок.
- `ruff check` і `ruff format --check` для шести змінених файлів аналізу й пакування: PASS. Повний `ruff check .` не пройшов через Access Denied під час обходу workspace і 140 знахідок у наявних тимчасових/інших файлах; повний `ruff format --check .` завершився внутрішньою помилкою Ruff `Expected a ruff source file`. Жодні сторонні файли не форматувалися.
- Історичний fingerprint verifier: 694/694, без невідповідностей.
- `py_compile` для сценаріїв аналізу, побудови графіків, звітів і пакування: PASS.
- Первинні trial записи й математичні алгоритми під час фінального аналізу не змінювалися.

