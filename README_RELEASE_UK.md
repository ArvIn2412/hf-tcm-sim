# HF-TCM-SIM: запуск веблабораторії

Потрібні Python 3.11+ та сучасний браузер. Запускайте команди з кореня
репозиторію: це реліз із вихідним кодом, включно з каталогом `scripts/`.

## Встановлення та запуск

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m hf_tcm.repro.scientific_studio --no-browser --port 8765
```

Linux/macOS: після створення `.venv` використовуйте `.venv/bin/python`
замість `.venv\Scripts\python`. Відкрийте `http://127.0.0.1:8765/scientific`.
Сервер слухає лише localhost. Зупинка — Ctrl+C у терміналі.

## Демонстрація

Для короткої власної демонстрації виберіть AWGN, N=32 або 64, seed=331,
один повтор; вимкніть «Обчислювати енергетичний виграш» і натисніть запуск.
Це окремий демонстраційний кадр; sweep має стан NOT_RUN.

У наявному наборі даних контроль N=20000 відкривається за URL
`/scientific?run_id=stage3-control-20000`. Перейдіть до символу 19999 або
відліку 159999. Wheel масштабує, drag переміщує, Shift+drag виділяє область;
на touch доступні drag/pinch. Minimap і додаткові дії розкриваються в навігаторі.
Сузір'я, інспектор і решітки використовують фактичні збережені дані.

У чистому checkout історичних I/Q немає. Вони постачаються окремо та
відкриваються тільки після перевірки provenance/SHA; відсутні дані не замінюються
демонстраційними. Великі архіви та `outputs/` не додаються до Git.

## Перевірки

```text
python -m pytest -q -m "not historical"
ruff check src tests scripts/ci
ruff format --check src tests scripts/ci
python scripts/ci/verify_historical_bundle.py
```

Остання команда блокує historical audit, якщо немає reviewed manifest,
артефактів або оригінального EXP-01 ZIP. Це не PASS і не пропуск assertions.
Докладний порядок зовнішнього historical bundle — [CI README](scripts/ci/README.md).

## Наукові обмеження

Лише офлайнова академічна симуляція; без SDR, радіокерування або БПЛА.
`paper_exact:false`. Фазове маркування, модель завмирань та інші реконструкції
позначені [ПРОЄКТ] і не приписуються статті. Дискретна енергетична шкала не є
фізичним Eb/N0; незалежного підтвердження статейних 1,5 дБ немає. Демонстрація
та технічна готовність не доводять статистичної переваги алгоритму.

31 100 trials SCIENTIFIC-EXP-03B, протоколи, seeds та історичні SHA зберігаються
без змін. Точні технічні статуси: `outputs/release_readiness/` у локальному пакеті
приймання; ці звіти та дослідницькі результати не входять у source-only Git-реліз.
