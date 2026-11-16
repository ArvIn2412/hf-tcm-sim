# Portable CI та зовнішній historical audit

`.github/workflows/ci.yml` має три окремі jobs:

- Portable: Python 3.11/3.12, `pytest -m "not historical"`, CLI smoke.
- Source quality: `ruff check src tests scripts/ci` та відповідний format check.
  Дослідницькі архіви, приватні документи та scratch-файли не входять до scope.
  Додатково Node 22 перевіряє синтаксис browser JS і QA `.mjs`; npm-пакети не потрібні.
- Historical audit: лише за workflow_dispatch із `run_historical_audit=true`.

Для historical job потрібно передати ID довіреного Actions run у цьому самому
репозиторії та назву окремо завантаженого artifact. Він має містити:

1. `outputs/ci/historical-artifacts.sha256` — незалежно перевірений manifest.
2. Згадані в ньому immutable `outputs/` fixtures для всіх historical tests.
3. Оригінальний `HF_TCM_SIM_SCIENTIFIC_EXP_01_ENERGY_AUDIT.zip` у корені bundle.
4. `outputs/scientific_exp_01/archive_verification.json`, pinned у SHA manifest.

Artifact завантажується в `.historical-input/`, а не поверх вихідного коду.
Preflight перевіряє SHA всіх зазначених файлів і EXP-01 ZIP перед копіюванням.
Він дозволяє лише перелічені outputs-пути та фіксований ZIP; інші файли artifact
не встановлюються. Існуючі відмінні історичні байти не перезаписуються.
Довіра до самого manifest та Actions run має бути встановлена окремо.

Відсутні файли: `BLOCKED_MISSING_ARTIFACT`, exit 2, pytest не запускається.
Неправильний SHA: FAIL, exit 1. Перевірений bundle: запускаються оригінальні
`pytest -m historical` без skip/xfail та без послаблення assertions.
Вимкнений historical job не означає успішний historical audit.

Перевірка відбитків первинної статті також має marker `historical`: вона читає
`references/source_paper_2026.docx` та доступні page scans за незмінним ledger.
У поточному checkout вони вже відстежуються Git. Публікація цих документів
потребує окремої перевірки прав; у source-only portable snapshot вони відсутні.
Повний historical запуск потребує правомірного доступу й до цих джерел.

Локально: `python scripts/ci/verify_historical_bundle.py --root PATH`.
`--install` матеріалізує перевірені fixtures в поточний checkout; не використовуйте
його для оновлення або заміни заморожених результатів.

Workflow не запускався віддалено під час підготовки без commit/push;
локальний звіт окремо вказує перевірені команди та платформу Python.
