# SCIENTIFIC-EXP-01B — рисунки й таблиці для розділу 4

Усі рисунки побудовано з 2 160 завершених незалежних кадрів confirmatory-серії. Кожна точка містить 40 кадрів по 512 інформаційних бітів. Горизонтальна шкала — нормована дискретна \(\gamma_{b,d}\), а не фізичне Eb/N0. Історичні пілотні дані не включено.

## Перелік рисунків

| Рисунок | Файл PNG / SVG | Рекомендований підпис і застереження |
|---|---|---|
| 4.1. BER статичного каналу | [PNG](../../outputs/scientific_exp_01b/analysis/plots/static_ber.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/static_ber.svg) | Залежність BER інформаційних бітів від нормованої дискретної енергетичної шкали для Joint, B0 і B1 у статичному двопроменевому каналі. 40 кадрів на точку, F=256. |
| 4.2. SER статичного каналу | [PNG](../../outputs/scientific_exp_01b/analysis/plots/static_ser.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/static_ser.svg) | SER інформаційних пар після декодування; не плутати з помилками фазових символів до декодування. |
| 4.3. Енергія / виграш статичного каналу | [PNG](../../outputs/scientific_exp_01b/analysis/plots/static_energy_gain.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/static_energy_gain.svg) | Необхідна \(E_{b,d}\) і модельний gain для target BER 0,05/0,01. Точки без виміряного перетину або з недостатньою bootstrap-підтримкою позначені як неоцінювані. |
| 4.4. Час приймання у статичному каналі | [PNG](../../outputs/scientific_exp_01b/analysis/plots/static_runtime.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/static_runtime.svg) | Медіанний час одного декодера; відображає програмну вартість для F=256, не апаратну пропускну здатність. |
| 4.5. BER у Rician AR(1) | [PNG](../../outputs/scientific_exp_01b/analysis/plots/rician_ber.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/rician_ber.svg) | Joint і B0 за двопроменевого Rician AR(1); B1 не підтримується для цього профілю. |
| 4.6. SER у Rician AR(1) | [PNG](../../outputs/scientific_exp_01b/analysis/plots/rician_ser.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/rician_ser.svg) | SER інформаційних пар. Високорівневий B0 plateau — спостереження лише в замороженому діапазоні 18–24 дБ. |
| 4.7. Енергія / виграш Rician | [PNG](../../outputs/scientific_exp_01b/analysis/plots/rician_energy_gain.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/rician_energy_gain.svg) | Joint перетинає задані цілі, але B0 — ні; тому gain не визначено і не екстраполюється. |
| 4.8. Час приймання у Rician | [PNG](../../outputs/scientific_exp_01b/analysis/plots/rician_runtime.png) · [SVG](../../outputs/scientific_exp_01b/analysis/plots/rician_runtime.svg) | Медіанний час одного виклику; два таймери, що збіглися із системними призупиненнями, не впливають на медіану, але збережені у raw records. |

## Готові числові висновки

За статичного двопроменевого каналу й цільового BER=0,05 розрахована необхідна дискретна енергія на біт становить 1,5894 для Joint, 6,0149 для B0 і 2,7979 для B1 (\(\sigma_c^2=1\)). Відповідний модельний виграш дорівнює 5,7800 дБ для Joint/B0 (95% paired bootstrap-ДІ 5,3931–6,2266 дБ) і 2,4561 дБ для Joint/B1 (2,2669–2,8526 дБ). Альтернативна лінійна інтерполяція BER дала 5,7757 та 2,4484 дБ відповідно.

Для BER=0,01 B0 у статичному профілі не досяг цілі до верхньої межі 14 дБ. Joint/B1 має точковий розрахунок, але 84,62% валідних bootstrap-перетинів не досягають замороженого порога 95%; тому підтверджувального ДІ та остаточного виграшу немає. У Rician Joint перетинає BER=0,05 та 0,01, але B0 не перетинає ці цілі до 24 дБ, отже енергетичну різницю без екстраполяції визначити не можна.

Значення 1,5 дБ зі статті не підтверджено. Ці числові оцінки характеризують дискретну модель і конкретні receiver profiles; вони не встановлюють фізичний Eb/N0 або універсальну перевагу алгоритму.
