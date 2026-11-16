# HF-TCM-SIM — стартовий репозиторій для Codex

**Готово:** M0 scaffold, M1 — згортковий кодер R=2/3, чотиристанна
решітка та нормована 8PSK, M2 — AWGN, hard/soft Вітербі, BER/SER і BER-графік,
M3 — конфігурований multipath/Rician, I/Q та статистика каналу. Повноцінний
запуск експериментів через CLI ще не реалізовано.
Профіль `baseline_assumption` — відтворюване проєктне маркування, не
підтверджене зі статті; SCI-02 залишається відкритим. **Ще не реалізовано:**
адаптивна обробка й наукові експерименти. SCI-04/07 відкриті; часово-
корельоване завмирання та прямокутний 8-відліковий waveform явно позначені
`approximate`, не як відтворення каналу чи імпульсної форми зі статті.

## Відкрити в Codex

1. Розпакуй ZIP. Відкрий каталог `hf-tcm-sim` у Codex.
2. Бажано виконай `git init` в каталозі (тільки локально).
3. У терміналі проєкту (Python 3.11+):

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m hf_tcm doctor
python -m hf_tcm check-config configs/m0_smoke.json
python -m pytest -q
ruff check .
ruff format --check .
```

Якщо `ruff` не встановився — встанови dev extras; у CI тести запускаються
автоматично. Команду `python -m hf_tcm doctor` можна також запускати через
`hf-tcm doctor` після встановлення.

4. Встав у Codex **лише промпт із `NEXT_TASK.md`**. Не проси
«реалізувати всю систему»: наступна фаза — тільки M1.

## Основні файли

- `AGENTS.md` — короткі постійні правила для Codex (економія контексту).
- `NEXT_TASK.md` — один цільовий промпт M1.
- `PLAN.md` — стан усіх етапів.
- `docs/TECHNICAL_SPECIFICATION.md` — повне ТЗ v1.0.
- `docs/ASSUMPTIONS_AND_DECISIONS.md` — SCI-01…08.
- `references/source_paper_2026.docx` — оригінальна стаття,
  ключові формули також у `references/key_pages/`.
- `configs/m0_smoke.json` — **не** налаштування симуляції; лише
  демонстрація читання конфігурацій у фазі M0.

Жодних результатів моделювання не отримано. Число 1,5 дБ наведене
лише як повідомлений у статті результат, не як підтвердження програмою.
