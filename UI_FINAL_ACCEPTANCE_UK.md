# TCM-SIM — фінальне приймання наукового вебінтерфейсу, етап 2

Функціональне впровадження завершено. `paper_exact:false`. Неповне покриття історичного SHA-аудиту й root-wide lint наведено окремо; вони не приховані за успішними тестами програми.

| Перевірка | Статус | Фактичний доказ |
|---|---|---|
| IMPLEMENTATION | COMPLETE | Реальні API, NPZ, декодери, frontend та браузерні jobs |
| ARTICLE DEFAULTS | PASS | Чистий вхід: article; N=20000, n=8, η=20, p*п=.05, M=8, R=2/3, Rician |
| LIVE I/Q | PASS | Збережені RX I/Q без генерації координат для графіка; безшумовий exact TX=RX контроль; шумовий scatter |
| VITERBI COMPARISON | PASS | Replay зі збережених branch rows, перевірка бітів; два однакові trellis, різні метрики; синхронні k та інтервал |
| METRIC PAIRING | PASS | Спільні observation/frontend SHA-256; одна NPZ із RX для обох arms |
| ADAPTIVE ENERGY SWEEP | PASS | Окрема згода, новий seed/ID, ±3 дБ, ліміти, план, прогрес і stop; реальна серія 6/6 trials |
| TOOLTIPS AND PARAMETER GROUPS | PASS | П’ять груп; labels/одиниці/межі/джерела; readonly статейні константи; advanced модельні масиви |
| HISTORICAL SHA-256 | PARTIAL | 87 714 PASS / 0 FAIL, включно з 31 100 trials; 32 пізніші файли NOT_VERIFIED |
| DESKTOP/MOBILE | PASS | 1366×900 і 390×844; desktop дві рівні колонки, mobile одна; scrollWidth=390 |
| TESTS | PASS | 1295 passed / 0 failed у фінальному повному pytest |

## Покриття 12 приймальних вимог

1. Чисте відкриття, початковий профіль і константи — перевірено Edge; `outputs/ui_article_alignment/browser_results.json`.
2. Шість навігаційних вкладок — перевірено; старі діагностики перенесені в додаткові технічні секції, старі IDs та loaders збережені.
3. Сузір’я — API читає `received_samples`, `transmitted_samples`, `equalized_symbols`; actual RX, чотири режими, вектори, hover, ideal points та decoder overlays.
4. Pairing — API перевіряє manifest і рівність observation/frontend hashes; обидва replay використовують один набір збережених constraints та той самий trellis.
5. Решітки — спільні start/end/k/zoom, покроковий перегляд і scroll; actual state metrics, survivor rows та `DecisionRecord`.
6. Облік — одиничний контроль: 1 демонстраційний кадр + 2 окремі sweep кадри; Monte Carlo: 2/2; cancellation не запускає pending sweep.
7. Gain при допустимому перетині — фактичний N=128 AWGN контроль: 20 + 80 кадрів, 5000 bootstrap, valid_fraction=.9994; Δγ=2.855 дБ, 95% ДІ [2.404,3.449]. Це приклад приймання, не новий науковий висновок.
8. Без перетину — `ENERGY_GAIN_NOT_ESTIMABLE`; при valid_fraction=.8778 — `INSUFFICIENT_PRECISION`. Без екстраполяції, pseudocount або підстановки 1,5 дБ.
9. Параметри — п’ять груп, явне розмежування [СТАТТЯ]/[ПРОЄКТ], уточнено одиниці; номерів неперевірених формул не додано.
10. Історія — 31 100 confirmatory records та їх arrays перевірені за старими checkpoint hashes; додатково протоколи, CSV, графіки й звіти за архівним manifest. Для 32 файлів без manifest — NOT_VERIFIED.
11. Desktop/mobile — фактичні скриншоти й CSS grid; геометрія решіток спільна, таблиці/широкі решітки прокручуються всередині панелі.
12. Регресії — фінальний pytest 1295/0; scoped Ruff/format і Node syntax пройшли. Загальний Ruff не green через наведені нижче обмеження.

## Змінені файли

Програма:

- `src/hf_tcm/studio/server.py` — trace GET API.
- `src/hf_tcm/studio/metric_trace.py` — перевірка джерел, RX/frontend, replay і вікно траси.
- `src/hf_tcm/repro/metric_experiment.py` — zero-noise analysis, tolerance grouping за point_index, чинний atomic writer, hashes версій алгоритмів у нових записах.
- `src/hf_tcm/studio/static/scientific.html` — підключення нових модулів.
- `src/hf_tcm/studio/static/scientific.js` — міст сумісної навігації.
- `src/hf_tcm/studio/static/article_workspace.js` — групування, deep links, restore checkbox state.
- `src/hf_tcm/studio/static/scientific_metric.js` — етапи jobs, adaptive consent, точні статуси, правильний aggregate key Евкліда.
- `src/hf_tcm/studio/static/metric_live.js` — сузір’я, TX/RX, решітки, stats, SVG/PNG.
- `src/hf_tcm/studio/static/metric_parameters.js` — параметри, джерела, tooltip, модельні масиви та adaptive controls.

Тести й аудит:

- `tests/studio/test_metric_trace.py`.
- `scripts/qa_ui_stage2.mjs`, `scripts/qa_ui_stage2_runs.mjs`, `scripts/qa_ui_stage2_gain.mjs`.
- `scripts/verify_ui_historical.py`, `scripts/verify_ui_archive_baseline.py`.

Не змінювалися кодер, maintained Viterbi decoder, frontend, noise/fading mathematics, bootstrap/interpolation routines та SCIENTIFIC-EXP-03B protocol/trials. Старі saved config loaders збережені.

## Запущені перевірки

Фінальний повний прогін:

```text
python -m pytest -q --basetemp tmp/ui-stage2-1295-final -p no:cacheprovider
1295 passed in 63.83s
```

Focused metric/trace suite: 24 passed. Node syntax для нових frontend модулів — PASS. Edge CDP сценарії перевіряють реальні HTTP jobs і дані, а не макети.

Проміжні збої були зафіксовані та усунені: sandbox ACL тимчасових каталогів; один HTTP timeout при паралельному великому SHA-аудиті; Windows replace lock нового manifest; розщеплення енергетичної точки floating-point округленням. Фінальний регресійний прогін green. Сирі результати старих досліджень цими виправленнями не перераховувалися.

Root-wide `ruff check .`: 152 findings. Root-wide `ruff format --check .`: traversal panic `Expected a ruff source file`. Змінені Python файли окремо проходять Ruff і format. Журнали збережено у `outputs/ui_article_alignment/stage2-*-root-final.log`.

## Артефакти й скриншоти

Повний [звіт реалізації](outputs/ui_article_alignment/UI_IMPLEMENTATION_REPORT_UK.md), [браузерна перевірка](outputs/ui_article_alignment/stage2-browser.json), [runtime перевірки](outputs/ui_article_alignment/stage2-runtime-tests.json), [gain](outputs/ui_article_alignment/stage2-gain-live.json), [SHA зведення](outputs/ui_article_alignment/historical_combined_summary.json).

- [Налаштування](outputs/ui_article_alignment/stage2-parameters.png).
- [Передавач і канал](outputs/ui_article_alignment/stage2-transmitter.png).
- [Реальна RX хмара](outputs/ui_article_alignment/stage2-constellation.png).
- [Обидві решітки](outputs/ui_article_alignment/stage2-viterbi.png).
- [Порівняння](outputs/ui_article_alignment/stage2-metric.png).
- [Збережені дослідження](outputs/ui_article_alignment/stage2-saved.png).
- [Mobile решітки](outputs/ui_article_alignment/stage2-mobile-viterbi.png).
- [Mobile сузір’я](outputs/ui_article_alignment/stage2-mobile-constellation.png).

## Залишкові обмеження

**REMAINING ISSUES: 2 категорії аудиту, відкритих функціональних дефектів за виконаними перевірками — 0.**

1. Для 32 пізніших дисертаційних/методологічних файлів не знайдено початкового checksum manifest. [Перелік NOT_VERIFIED](outputs/ui_article_alignment/historical_later_revisions_not_verified.json). Це не підстава оголошувати їх незмінність доведеною.
2. Загальний lint/format дерева не проходить; незв’язані scratch/історичні файли масово не виправлялися. Точні журнали наведено вище.

Наукові межі збережено: Encoder A не оголошений доведено тотожним статейному (9,6); «елемент» відображено на символьний інтервал моделі з пілотами; p*п не прирівняно до BER; Rician AR(1) та параметри — модельні; шкала дискретна, не фізичний Eb/N0. Обчислений UI-контроль не підтверджує статейні 1,5 дБ. N=20 000 є початковим значенням; інтеграційні перевірки виконані на коротких кадрах, без повторного запуску 31 100 trials.

Локальний запуск: `python -m hf_tcm.repro.scientific_studio --port 8765`; відкрити `http://127.0.0.1:8765/scientific`.
