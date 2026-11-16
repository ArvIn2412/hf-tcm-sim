# GUI-UX-02

GUI STATUS: PARTIAL.

Три колонки, українські підписи, чотири Tx/Rx I/Q, незалежні перемикачі на загальних графіках, фіксоване сузір’я 360×360, один заголовок, метадані й методика в діалогах. Видимі службові коди прибрано. Додано перемикачі BER-кривих. Залишкові обмеження: спеціалізовані графіки gain/phase/estimated/predicted trajectories не всі представлені в поточному workspace; повний UI verdict PARTIAL.

## Фактичні перевірки

1182 pytest passed (64.65 s); targeted article audit: 109 passed; Ruff check/format src tests passed; Node syntax passed; 694/694 historical fingerprints; Edge QA 12/12 checks, 22 screenshots at 1366×768 and 1920×1080. Окремий повтор Edge після остаточних BER-toggle/color правок завис; він не зарахований.

Запуск: `python -m hf_tcm.repro.scientific_studio --port 18802 --no-browser`, адреса `http://127.0.0.1:18802/scientific`.
