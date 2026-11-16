# REPRO-02 — фінальний звіт

## Вердикт

**REPRO_02_TRANSMITTER_READY** — для ізольованого transmitter scope. Це не означає paper-exact implementation усього експерименту: точна supervisor v7 редакція відсутня, ADR-002 mapping реконструйований, source `N*` одиниця не встановлена.

## Реалізація

Новий пакет `src/hf_tcm/repro/` реалізує strict config, manual/pattern/PCG64 seeded bits, Encoder A, explicit termination, ADR-002 mapping з fingerprint, 8PSK complex modulation і восьмикратний rectangular ZOH. `run_transmitter(config)` формує `TransmitterResult` з повною історією та provenance. CLI: `python -m hf_tcm.repro.transmitter`; відсутність аргументів лише виводить help. Persisted results розміщені в `outputs/repro02/reference_n_star/`, окремо від M5–M10.

## Перевірки

- Цільові `tests/repro`: 23 passed.
- Незалежний scalar oracle перевіряє всі 16 векторів, не використовуючи production encoder для expected values.
- End-to-end deterministic reference: 20,000 steps → 40,000 input bits → 60,000 coded bits → 160,000 samples; output arrays та manifest з SHA-256 збережені.
- 10 transmitter plots створено з фактичного результату.
- Два однакових reference runs дали однаковий summary та array hashes.
- `ruff check src tests` — PASS; `ruff format --check src tests` — PASS, 182 files already formatted.
- `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro02-final -p no:cacheprovider` — 1000 passed in 31.83s.
- M5–M10 historical fingerprint recount: 694/694 matched, 0 missing, 0 changed.
- Receiver/channel invocation guard тест пройшов; BER/SER та Monte Carlo не виконувались.
- Усі 10 SVG успішно прочитані XML parser; manifest hashes повторно збігаються для 20/20 NumPy arrays.

## REPRO-01 vector correction

Перевірка на незалежному oracle виявила 16 test vectors REPRO-01 з output triples, що не відповідали формулі, записаній у тому ж encoder spec. Машинний spec, vectors і Markdown table виправлено до recurrence `c2=u0`, `c1=u1 XOR p2`, `c0=p1`, `next=(u1,p1)`. Це корекція тестових oracle-даних, а не зміна статті або historical production. Див. `REPRO_02_ENCODER_VERIFICATION.md`.

## Source і припущення

Використаний local paper файл hash `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8`; його редакція не підтверджена як supervisor v7. ADR-002 natural-binary mapping реконструйований. `A=1`, `φ₀=0`, source input pattern та тлумачення `N*=20,000` intervals є явними project choices. Δφ=π/4 є фазовим приростом, не абсолютною фазою.

Збережено `paper_exact:false`, `receiver_enabled:false`, SCI-02/SCI-03/SCI-METRIC-02 OPEN. Історичні M5–M10 результати та production receiver не змінювались. ACL-protected pytest artifacts не видалялися.

## Наступний етап

REPRO-03 може окремо реалізувати source-aligned physical channel candidate за REPRO-01 specification та зафіксувати кожну reconstruction choice. Він має споживати `TransmitterResult` без модифікації цього transmitter, генерувати спільний channel/noise buffer для майбутніх receiver A/B, а невизначені SNR/RNG/channel conventions лишати явними параметрами. REPRO-03 тут не запускався.
