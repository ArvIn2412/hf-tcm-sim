# Experiment protocol / Протокол досліджень

## Принцип
Одна пара реалізацій `(tx, channel_noise)` для кожного порівнюваного декодера, однаковий `Eb/N0`, точний `seed`. У вихідних файлах фіксувати визначення енергії, overhead, кількість корисних бітів, raw counts, estimator CSI-mode.

| ID | Назва | Умови | Результат |
|---|---|---|---|
| E-01 | AWGN baseline | P0; hard/soft, Es=1, no CSI | BER(Eb/N0), T-04…T-08 |
| E-02 | 1-path fading | P1; `none`/`oracle` окремо | калібрувальна різниця, не польовий результат |
| E-03 | multipath | P1; задані `L`, `tau`, powers, `K` | BER/SER, I/Q, SCI-04 |
| E-04 | estimator | P1; тільки дозволені приймачеві спостереження | помилка оцінки + BER |
| E-05 | adaptive comparison | P1; A/B/C, paired channel; SCI підтверджені | таблиці, порівняльні графіки |
| E-06 | reported gain audit | однаковий target BER, надійні точки кривих | ΔEb/N0, CI, відхилення від 1,5 дБ |

## Мінімальні поля CSV

`experiment_id,scheme,channel_kind,csi_mode,seed,ebn0_db,frames,info_bits_checked,bit_errors,ber,ber_ci_low,ber_ci_high,symbols_checked,symbol_errors,ser,runtime_s`.

## Точність

- Стартова довжина зі статті: `N = 20000` модульованих символів / експеримент; це **не** гарантує точну оцінку при малій BER.
- Для більш рідкісних помилок збільшити `frames`, повторні seed, фіксувати counts.
- Довірчі інтервали: запропоновано Wilson 95% або exact binomial, обраний метод зберігати в `metadata.json`.
- Якщо `errors = 0`, показувати оцінку як `0/N`, верхній bound, не стверджувати нульову справжню ймовірність.
- Не вимагати суворої монотонності BER для випадкової скінченної вибірки.

## Архів кожного запуску

Зберігати `config_resolved.yaml`, `metadata.json`, `summary.csv`, `metrics_by_point.csv`, `plots/`, за потреби `raw/*.npz`. Не змінювати постфактум результатів у CSV для досягнення бажаного графіка.
