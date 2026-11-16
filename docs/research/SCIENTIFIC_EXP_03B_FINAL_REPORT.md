# SCIENTIFIC-EXP-03B — фінальний звіт

## Статус

**SCIENTIFIC_EXP_03B_PARTIAL** — усі 31 100 confirmatory trial records завершені та незалежно агреговані; науковий висновок позитивний для частини контрольованих порівнянь, але повний перелік заявлених target/channel gains не оцінюється через відсутні перетини або не досягнуту bootstrap-підтримку. Нова статистична серія не запускалася.

| Показник | Висновок |
|---|---|
| Парні A-E/A-H observations та pilot frontend | VERIFIED за протоколом, trial provenance і однаковими hash-полями записів |
| Евклідова проти Хемінга, target BER=0,05 | Підтверджена енергетична перевага у AWGN direct, AWGN pilot і static pilot |
| Primary Rician AR(1), metric gain | `ENERGY_GAIN_NOT_ESTIMABLE`; обидва arms не перетинають target 0,05 |
| B Joint/B0, AWGN, BER=0,05 | 1,6664 дБ; 95% ДІ [1,2921; 2,0016]; 99,02% valid crossings |
| B static gains | Point estimates наявні, але не проходять наперед визначений ≥95% bootstrap gate |
| B Rician gain | `NOT_ESTIMABLE`; B0 не перетинає target |
| Фізичне Eb/N0 | NOT_VALIDATED |
| Результат статті 1,5 дБ | Не відтворено як статейний результат; числовий збіг CI не є доказом відтворення |
| `paper_exact` | `false`, незмінено |

## Протокол і дані

Confirmatory протокол SHA-256: `d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6`. Блок A: 22 800 парних кадрів, п'ять зафіксованих metric scenarios, два sweep-и, F=1024, 300 clusters на точку. Блок B: 8 300 paired frames, F=256, 100 на точку; AWGN 2900, static 2900, Rician 2500. Усі counts, seeds, arrays, hashes і series manifests залишені незмінними.

## Результати

### A — ізольований ефект метрики

| Сценарій A | Ціль BER | Eᵦ,d Евклід | Eᵦ,d Хемінг | Виграш, дБ | 95% paired bootstrap-ДІ | Валідні перетини | Лінійна інтерполяція, 95% ДІ | Висновок |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `awgn_direct` | 0,05 | 0,096939 | 0,18758 | 2,8668 | [2,8197; 2,914] | 100% | [2,8295; 2,8998] | `PRECISION_CRITERIA_MET` |
| `awgn_direct` | 0,01 | 0,12755 | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `awgn_direct` | 0,001 | 0,16622 | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `awgn_pilot` | 0,05 | 0,28034 | 0,47565 | 2,296 | [2,1586; 2,4236] | 100% | [2,2779; 2,4932] | `PRECISION_CRITERIA_MET` |
| `awgn_pilot` | 0,01 | 0,51667 | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `awgn_pilot` | 0,001 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period32` | 0,05 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period32` | 0,01 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period32` | 0,001 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period8` | 0,05 | 1,389 | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period8` | 0,01 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `rician_period8` | 0,001 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |
| `static_pilot` | 0,05 | 0,25219 | 0,44203 | 2,4373 | [2,3375; 2,5335] | 100% | [2,3148; 2,5055] | `PRECISION_CRITERIA_MET` |
| `static_pilot` | 0,01 | 0,4787 | — | — | — | 0,02% | — | `TARGET_NOT_ESTIMABLE` |
| `static_pilot` | 0,001 | — | — | — | — | 0% | — | `TARGET_NOT_ESTIMABLE` |

ΔBER=Euclidean−Hamming. На Rician cadence 32 primary при найвищій точці \(\gamma_{b,d}=37,6108\) дБ: BER(E)=0,12332, BER(H)=0,18243; ΔBER=−0,05911, 95% ДІ [−0,06052; −0,05770]. Проте обидві криві лишились вище BER=0,05, тож горизонтальний енергетичний gain не визначається.

### B — повні системи

| Канал B | Ціль BER | Separate arm | Eᵦ,d Joint | Eᵦ,d Separate | Gain Joint/Separate, дБ | 95% ДІ | Валідні перетини | Статус |
|---|---:|---|---:|---:|---:|---:|---:|---|
| `awgn` | 0,05 | `B0` | 0,12939 | 0,18991 | 1,6664 | [1,2921; 2,0016] | 99,02% | `PRECISION_CRITERIA_MET` |
| `awgn` | 0,01 | `B0` | — | 0,32861 | — | — | 27,88% | `TARGET_NOT_ESTIMABLE` |
| `awgn` | 0,001 | `B0` | — | 0,60959 | — | — | 8,58% | `TARGET_NOT_ESTIMABLE` |
| `rician` | 0,05 | `B0` | 0,20613 | — | — | — | 0% | `TARGET_NOT_ESTIMABLE` |
| `rician` | 0,01 | `B0` | 0,46741 | — | — | — | 0% | `TARGET_NOT_ESTIMABLE` |
| `rician` | 0,001 | `B0` | — | — | — | — | 0% | `TARGET_NOT_ESTIMABLE` |
| `static` | 0,05 | `B0` | 0,08685 | 0,30765 | 5,4928 | — | 94,68% | `INSUFFICIENT_PRECISION` |
| `static` | 0,05 | `B1` | 0,08685 | 0,14543 | 2,2388 | — | 94,94% | `INSUFFICIENT_PRECISION` |
| `static` | 0,01 | `B0` | 0,13036 | 1,2503 | 9,8187 | — | 46,5% | `INSUFFICIENT_PRECISION` |
| `static` | 0,01 | `B1` | 0,13036 | 0,25397 | 2,8962 | — | 86,9% | `INSUFFICIENT_PRECISION` |
| `static` | 0,001 | `B0` | 0,16333 | — | — | — | 0% | `TARGET_NOT_ESTIMABLE` |
| `static` | 0,001 | `B1` | 0,16333 | 0,44898 | 4,3917 | — | 56,4% | `INSUFFICIENT_PRECISION` |

### Стаття та фізична інтерпретація

Статейні 1,5 дБ використані тільки як зовнішнє порівняльне значення. Дискретне \(\gamma_{b,d}\) не має встановленого зв'язку з фізичним Eb/N0. Порівняння Joint/B0/B1 оцінює сукупні відмінності систем оброблення, а не чистий ефект метрики.

## Артефакти

- Метрики: [`SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md`](SCIENTIFIC_EXP_03B_METRIC_COMPARISON.md).
- Системи: [`SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md`](SCIENTIFIC_EXP_03B_SYSTEM_COMPARISON.md).
- Енергія: [`SCIENTIFIC_EXP_03B_ENERGY_GAIN.md`](SCIENTIFIC_EXP_03B_ENERGY_GAIN.md).
- Статистика: [`SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md`](SCIENTIFIC_EXP_03B_STATISTICAL_VALIDATION.md).
- Стаття: [`SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md`](SCIENTIFIC_EXP_03B_ARTICLE_COMPARISON.md).
- Розділ 4: [`THESIS_CHAPTER_4_FINAL_DRAFT.md`](THESIS_CHAPTER_4_FINAL_DRAFT.md).
- Реальні точки: `tables/SCIENTIFIC_EXP_03B/*.csv`.
- PNG/SVG: `figures/SCIENTIFIC_EXP_03B/` (59 пар, маніфест з hash).
