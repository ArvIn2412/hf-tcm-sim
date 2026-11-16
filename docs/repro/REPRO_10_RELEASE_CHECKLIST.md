# REPRO-10 release checklist

- [x] Scientific Workspace має окремий launcher і запускається локально з кореня проєкту.
- [x] Звичайний запуск не запускає автоматично модель; health endpoint підтверджений.
- [x] Реальні transmitter/channel/Joint/B0 та підтримуваний B1 backend підключені.
- [x] Identity, static multipath, Rician, paired observation hashes перевірено через Edge.
- [x] Відображені 4/16 і 17/68 trellis, selected survivor/edge, η=20 та окремий 20-sample zoom.
- [x] Save/load single result; stop/resume Monte Carlo; exploratory BER/SER plots.
- [x] PNG експорт перевірено як фактичний PNG файл із canvas.
- [x] F=20,000 archived metrics/trace відкриваються lazy; відсутні I/Q та різні hashes чесно показані.
- [x] `paper_exact:false`; фізичний Eb/N0 та виграш 1.5 dB не заявляються.
- [x] Historical source verifier: 694/694; restored demo launcher SHA перевірено.
- [x] Scoped Ruff, Ruff format і Node syntax checks пройшли.
- [ ] Чиста Windows інсталяція на окремій системі не перевірялась.
- [ ] Стаття не відтворена кількісно; `ARTICLE_REPRODUCTION_INSUFFICIENT_DATA`, `ENERGY_GAIN_NOT_ESTIMABLE`.
