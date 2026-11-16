# REPRO-06B — adaptive multipath estimator: статус

## Рішення milestone

`adaptive_rician_survivor_v1` навмисно недоступний. `MultipathReceiverConfig` відхиляє цей профіль під час створення конфігурації до будь-якого запуску. API не читає й не приймає actual fading histories, path contributions, noise samples або `EvaluationTruth`.

Причина: за затримок ISI кожна конкуруюча trellis hypothesis має власну фазову історію і власний waveform residual. Один глобальний коефіцієнт, оновлений після м'якого усереднення survivor paths, потребує чітко заданого posterior/update контракту та доведеної причинності. Без цих визначень він не є перевіреним extension старого однопроменевого estimator. REPRO-05 recursion тут не переписується і не оголошується multipath-compatible.

## Необхідний наступний дизайн (не виконувався)

Перед окремим етапом реалізації слід обрати й незалежно перевірити один з варіантів:

1. **Survivor-specific estimator banks:** зберігати estimator state на кожну живу path/history hypothesis; описати merge/pruning і числову вартість.
2. **Posterior-weighted update:** формально вивести posterior над expanded transitions, визначити innovation для кожної затриманої компоненти та довести, як ваги агрегуються між шляхами.
3. **Joint latent inference:** включити параметри/коефіцієнти каналу до state, із визначеними priors та complexity bounds.

Кожний варіант має пройти незалежний scalar oracle, причинність, synthetic channel truth-isolation і exhaustive малий сценарій, перш ніж відкрити Rician profile. Це рішення не є прихованою домовленістю про авторський алгоритм.

Статус: `ADAPTIVE_RICIAN_MULTIPATH_PARTIAL` / unavailable. Це головне обмеження загального статусу REPRO-06B.
