# REPRO-01 — підсумковий звіт

Дата: 2026-11-06.

**REPRO_01_SPEC_COMPLETE** — завершено project-defined формальну специфікацію парного експерименту, двох receiver contracts, параметрів, gaps та ізольованої архітектури. Це документаційний результат; receiver/channel алгоритми не реалізовувалися.

**PAPER_EXACT_BLOCKED_BY_SOURCE_GAPS** — точний v7 та Раздел_4.doc відсутні; доступний DOCX не підтверджений як v7; A(2), phase mapping, channel laws/parameters, SNR і receiver details неповні.

## Джерела та хеші

- references/source_paper_2026.docx — a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8.
- references/supervisor/Раздел_4.pdf — fa802b480e6d49089847867aacb2702231df758d1c990320b3d471202951f77d.
- references/supervisor/4.pdf — 97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904.
- references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx — 2f070e438f1d8fa4a6cd84e3e6cab24c560ba55670c93ec759a6f4fe82e76b58.
- Missing: references/supervisor/Яковів_Гриненко_2026_в7 27-10-26(4).docx; references/supervisor/Раздел_4.doc. Інша редакція не використана як тиха заміна.

## Покриття й обмеження

A(1)–A(10) внесені до реєстру, друковані стор.4–7 візуально перевірені. Encoder A має 4 стани/16 переходів і алгебраїчно узгоджується з G за оголошеної convention; initial/termination/mapping — реконструкції. Коефіцієнти A(10) зіставлені з модулем; innovation/init є project choices. Визначено спільний buffer для joint-Euclidean A та hard-demod/Hamming B без truth leakage. Записані N=20000, n=8, η=20, R=2/3, Δφ=π/4, p*=0.05 та їх обмеження. Енергетичний gain має знак, але потребує SNR normalization; 1.5 dB не є критерієм.

Жодного production code, GUI, ADR або M5–M10 artifact не змінено. Monte Carlo/receiver/decoder не запускався; BER/SER не створювалися. Historical fingerprints не переобчислювалися, тому в цій фазі вони не переаудитовані, хоча artifacts не чіпалися.

## Перевірки, фактично виконані

- Documentation validation: 12/12 обов'язкових Markdown/JSON файлів непорожні; обидва JSON розбираються; 16 векторів у JSON взаємно збігаються і відповідають next-state recurrence; A(1)–A(10) покриті.
- python -m pytest -q: 977 passed in 31.05s. Pytest завершився з додатковим atexit PermissionError на ACL-protected pytest-current у Windows temp; тестовий результат — успішний. Каталоги не видалялися.
- ruff check src tests: passed.
- ruff format --check src tests: 168 files already formatted.
- ruff check .: неуспішний для повного traversal — Access denied на ACL paths та 27 lint findings у docs/figures/generate_thesis_figures.py; цей unrelated generated-figure script не змінювався.
- ruff format --check .: Ruff упав під час traversal з “Expected a ruff source file”; targeted src/tests format check пройшов.

REPRO-02: frozen config schema та незалежний Encoder A oracle/tests; channel/pair APIs — окремими майбутніми фазами. Monte Carlo не запускати автоматично.
