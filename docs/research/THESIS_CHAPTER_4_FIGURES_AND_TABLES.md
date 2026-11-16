# Розділ 4 — реєстр рисунків і таблиць

Усі рисунки — з фактичних завершених confirmatory records. PNG — растровий експорт 300 dpi (перевірено мінімум 1000×600 px); SVG містить vector path. Повний каталог: `figures/SCIENTIFIC_EXP_03B/`; SHA-256 і розміри наведено у [`docs/research/figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json`](figures/SCIENTIFIC_EXP_03B/FIGURE_EXPORTS_MANIFEST.json). Усього 59 PNG + 59 SVG.

## Основні рисунки

| № | Назва | Файл PNG | Векторний SVG |
|---:|---|---|---|
| 4.1 | BER, AWGN direct, A-E/A-H | `figures/SCIENTIFIC_EXP_03B/metric/awgn_direct/amplitude_fixed_noise/ber.png` | `figures/SCIENTIFIC_EXP_03B/metric/awgn_direct/amplitude_fixed_noise/ber.svg` |
| 4.2 | BER, AWGN pilot frontend, A-E/A-H | `figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/ber.png` | `figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/ber.svg` |
| 4.3 | BER, static multipath [0,3], A-E/A-H | `figures/SCIENTIFIC_EXP_03B/metric/static_pilot/amplitude_fixed_noise/ber.png` | `figures/SCIENTIFIC_EXP_03B/metric/static_pilot/amplitude_fixed_noise/ber.svg` |
| 4.4 | BER, Rician AR(1), primary cadence 32 | `figures/SCIENTIFIC_EXP_03B/metric/rician_period32/amplitude_fixed_noise/ber.png` | `figures/SCIENTIFIC_EXP_03B/metric/rician_period32/amplitude_fixed_noise/ber.svg` |
| 4.5 | BER, Rician cadence-8 sensitivity | `figures/SCIENTIFIC_EXP_03B/metric/rician_period8/amplitude_fixed_noise/ber.png` | `figures/SCIENTIFIC_EXP_03B/metric/rician_period8/amplitude_fixed_noise/ber.svg` |
| 4.6 | Потрібна енергія та виграш метрики з 95% ДІ, AWGN із пілотним фронтендом | `figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/energy_gain.png` | `figures/SCIENTIFIC_EXP_03B/metric/awgn_pilot/amplitude_fixed_noise/energy_gain.svg` |
| 4.7 | BER повних систем AWGN | `figures/SCIENTIFIC_EXP_03B/system/awgn/ber.png` | `figures/SCIENTIFIC_EXP_03B/system/awgn/ber.svg` |
| 4.8 | BER повних систем static multipath | `figures/SCIENTIFIC_EXP_03B/system/static/ber.png` | `figures/SCIENTIFIC_EXP_03B/system/static/ber.svg` |
| 4.9 | BER повних систем Rician | `figures/SCIENTIFIC_EXP_03B/system/rician/ber.png` | `figures/SCIENTIFIC_EXP_03B/system/rician/ber.svg` |
| 4.10 | Час виконання повних приймачів, статичний канал | `figures/SCIENTIFIC_EXP_03B/system/static/runtime.png` | `figures/SCIENTIFIC_EXP_03B/system/static/runtime.svg` |

Примітка: конкретна кількість/назва рисунка в остаточному тексті дисертації може бути перенумерована за вимогами кафедри. У деяких графіках target BER позначено, але немає виміряного перетину; це навмисно — не є підставою для екстраполяції.

## Таблиці

| Таблиця | Вміст | Машинно-читаний файл |
|---|---|---|
| 4.1 | A: усі енергетичні точки двох sweep-ів, BER/SER/FER/ΔBER/ДІ | [`metric_isolation_all_points.csv`](tables/SCIENTIFIC_EXP_03B/metric_isolation_all_points.csv) |
| 4.2 | A: Eᵦ,d і gain за target BER та bootstrap-підтримка | [`SCIENTIFIC_EXP_03B_ENERGY_GAIN.md`](SCIENTIFIC_EXP_03B_ENERGY_GAIN.md) |
| 4.3 | B: усі криві BER/SER/FER і arms | [`full_system_all_points.csv`](tables/SCIENTIFIC_EXP_03B/full_system_all_points.csv) |
| 4.4 | B: енергетичний gain і час на кадр | [`SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md`](SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md) |
