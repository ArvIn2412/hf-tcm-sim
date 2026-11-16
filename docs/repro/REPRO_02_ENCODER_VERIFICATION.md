# REPRO-02 — незалежна перевірка Encoder A

## Визначення

Для input pair `(u0,u1)` і стану `(p1,p2)=(u1[k−1],u1[k−2])` реалізовано:

```text
c2 = u0
c1 = u1 XOR p2
c0 = p1
next_state = (u1, p1)
```

Output order є `(c2,c1,c0)`. Це causal interpretation матриці `G=[[1,0,0],[0,D²+1,D]]`, використана у REPRO-01; точна редакція supervisor v7 не наявна, тому ця конвенція не оголошується підтвердженою авторською serialization.

Edge IDs мають стабільний порядок REPRO `state 00,10,01,11`, у кожному стані input `00,01,10,11`. Encoder B не залучається.

## Перехресна перевірка

Усі 16 пар state/input звіряються з machine-readable `REPRO_01_ENCODER_TEST_VECTORS.json` і окремим тестовим oracle, який напряму обчислює XOR та next-state equations і не викликає production encoder. Тести перевіряють output triple, destination state та edge ID. Додатково перевірені кілька кроків, усі чотири стани, ненульовий initial state, детермінізм і termination.

Під час цього незалежного звіряння виявлено некоректні output triples у попередній версії REPRO-01 vectors. Їх замінено значеннями, які безпосередньо випливають із наведених recurrence equations. Виправлені таблиця та JSON vectors тепер є regression oracle. Це виправлення стосується REPRO-01 test evidence, не коду M5–M11.

## Тестові результати

`python -m pytest tests/repro -q --tb=short -p no:cacheprovider -p no:tmpdir` — 23 passed. Повний regression suite та підсумкова перевірка наведені у `REPRO_02_FINAL_REPORT.md`.
