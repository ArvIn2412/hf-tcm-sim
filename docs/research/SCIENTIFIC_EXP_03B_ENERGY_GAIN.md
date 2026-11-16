# SCIENTIFIC-EXP-03B — енергетичні оцінки

## Визначення

Для дискретних transmitted samples обчислено \(E_{tx,d}=\sum_n |x[n]|^2\), \(E_{b,d}=E_{tx,d}/N_{payload\ bits}\) та \(\gamma_{b,d}=10\log_{10}(E_{b,d}/\sigma_c^2)\). У primary A pilot cadence 32 кадр F=1024 містить 128 pilot і 896 інформаційних 8PSK-елементів (1792 корисні біти); pilot енергія включена в чисельник, а payload біти — у знаменник. Для cadence 8 pilot overhead більший; результати винесено окремо. У блоці B F=256 і задана сітка вимірюється за дискретною проєктною конвенцією.

\(\gamma_{b,d}\) — нормована дискретна шкала. Частота дискретизації, фізична форма імпульсу в смузі, шумова спектральна густина, matched filter та зв'язок sample-domain complex variance із фізичним \(N_0\) не встановлені; тому фізичне Eb/N0 не підтверджене.

## A: ізольований ефект метрики

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

Ціль 0,05: точкові модельні оцінки підтверджують нижчу потрібну дискретну енергію евклідового декодера у AWGN direct, AWGN із pilot frontend та статичному multipath із pilot frontend. У primary Rician cadence 32 та для target 0,01/0,001 валідної парної оцінки gain немає. Для cadence 8 лише E перетинає 0,05, отже gain також не оцінюється.

## B: повна технологія Joint проти Separate

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

Тільки AWGN Joint/B0 при BER=0,05 пройшов заморожені критерії статистичної точності. Static point estimates при BER=0,05 не пройшли 95% crossing fraction; Rician та частина нижчих target не мають парного перетину. Інформаційна перевага B1 (відомі номінальні taps) відрізняється від практичного оцінювання каналу.

## Порівняння зі статейними 1,5 дБ

Стаття повідомляє 1,5 дБ за власним визначенням помилки, енергії й умов каналу. Цей експеримент використовує іншу project-defined дискретну шкалу, окремі A і B контрасти, F та pilot accounting. Точкова B AWGN оцінка 1,666 дБ має bootstrap інтервал, що включає 1,5 дБ, однак це не відтворення статті й не підтверджує її авторський результат. Жоден результат не підганявся до 1,5 дБ; `paper_exact:false` залишається незмінним.
