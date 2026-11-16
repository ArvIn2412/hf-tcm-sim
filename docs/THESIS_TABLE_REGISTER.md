# Реєстр таблиць магістерської роботи

Нумерація — робоча, для перенесення у формат закладу. Підставлені числа
походять із frozen reports/checkpoints; невідомі значення не імпутовані.

| № | Назва / зміст | Розділ | Джерело даних | Примітка |
|---|---|---|---|---|
| Таблиця 1.1 | Джерельні твердження і межі реконструкції | 1 | `M11D_SOURCE_FIDELITY_AUDIT.md` | Категорії source/project/unresolved |
| Таблиця 2.1 | Позначення кодера і відображення стану | 2 | `coding/encoder.py`, `MATHEMATICAL_MODEL.md` | Проєктна інтерпретація G(x) |
| Таблиця 2.2 | Усі 16 state/input/output/next-state/phase rows | 2 | M1 trellis + ADR-002; `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md` | b — проєктний, не авторський mapping |
| Таблиця 2.3 | Джерельні й проєктні параметри моделі | 2 | [A], configs, `ASSUMPTIONS_AND_DECISIONS.md` | Δφ відділено від absolute φ₀ |
| Таблиця 3.1 | Відповідність пакетів коду функціональним блокам | 3 | `src/hf_tcm/` | Реальні production/evaluation paths |
| Таблиця 3.2 | Які твердження перевіряють різні класи тестів | 3 | `tests/`, `BUILD_VERIFICATION.md` | Тест не дорівнює source validation |
| Таблиця 4.1 | M5j raw counts, BER/SER та pooled denominators | 4 | M5j report/checkpoints; M5k audit | C−B contrast |
| Таблиця 4.2 | M5f exploratory та M5h planning-pilot counts/intervals | 4 | M5f/M5h reports | Окремі pilot/exploratory namespaces |
| Таблиця 4.3 | M5j paired cluster-bootstrap intervals | 4 | M5j `bootstrap_summary.json`; M5k | 2 000 resamples |
| Таблиця 4.4 | M6 deterministic trace counts і допустимі висновки | 4 | M6b trace report | Три F=32 sequences; не performance sample |
| Таблиця 4.5 | M7 TRAIN ranking | 4 | M7b report/checkpoints | 9 кандидатів; без validation |
| Таблиця 4.6 | M8 TRAIN recovery ranking і невдалий первинний attempt | 4 | M8b/M8 recovery reports | 40 повторних IDs; failures not zero errors |
| Таблиця 4.7 | M9b pooled counts and rates | 4 | M9b report/checkpoints | 100 independent run clusters |
| Таблиця 4.8 | M9b ΔBER/ΔSER intervals | 4 | M9b bootstrap report | Обидва CI містять 0 |
| Таблиця 4.9 | M10 P0/P1/P2 raw counts and rates | 4 | M10b report/checkpoints | 6 cells; 300 paired profile buffers |
| Таблиця 4.10 | Класи доказів M5–M10 | 4 | Frozen reports | TRAIN/evaluation/diagnostic розділено |
| Таблиця 5.1 | Вміст і перевірені можливості Demo Studio M11e | 5 | M11e Edge QA/report | Simulation demonstration only |

