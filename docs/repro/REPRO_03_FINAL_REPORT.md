# REPRO-03 — фінальний звіт

## Вердикт

**REPRO_03_CHANNEL_READY** як версійований, відтворюваний project-defined complex-baseband channel із integer delays, named Rician profiles і sample-domain AWGN. Це не означає, що вся фізична модель HF propagation або точне відтворення S1 доведені. Реалізований профіль є придатним спільним джерелом received buffer для майбутніх двох приймачів.

## Source/API audit

Переглянуто `AGENTS.md`, усі REPRO-01 матеріали, усі REPRO-02 звіти/schema, фактичні channel helpers і повний `TransmitterResult`. Вихідний transmitter contract містить `tx_samples` complex128, `absolute_sample_index`, `sample_symbol_index`, `sample_local_index`, `samples_per_symbol=8`, інформаційні bits/symbols, mapping/source fingerprints і fidelity flags. Усі поля передавача завантажуються лише після NPZ/array/container SHA перевірки.

Стаття S1 A(4)/(6) дає structural multi-ray/delayed quadrature form; A(8)–A(10) дає real correlated quadrature disturbance. Доступні REPRO-01 матеріали фіксують, що L, числові затримки, повні fading law/parameters, physical time/carrier projection і SNR convention недовизначені. Rician із заданими K, complex-baseband integer convolution та circular sample-domain AWGN — project reconstructions. Корельований A(9) шум не підключений без визначеної passband-to-baseband transformation. Fractional delay і Eb/N0 фізична конверсія не доступні.

Виправлені 16 Encoder A vectors додатково перевіряються окремим recurrence oracle у REPRO-03 test; production Encoder A не є джерелом expected values. Сам transmitter/spec не змінювався в REPRO-03.

## Реалізований канал

`c_l[n]=h_l[n]x[n-d_l]` із zero extension, `y_sig=Σc_l`, `r=y_sig+w`; output length `N_tx+max(delay)`. При `n<d_l` або `n-d_l>=N_tx` внесок точно нульовий. Delay unit — sample; receive symbol/local index — `n//8`, `n%8`. Dtype coefficients/signals complex128, timing int64. Rician K convention — LOS power / diffuse power; AR(1) complex diffuse path має unit stationary power і lag correlation ρ^k, але не є Jakes. AWGN convention — E|w|²=σc² і Var(I)=Var(Q)=σc²/2.

Профілі: `identity_project_v1`, `single_path_rician_awgn_project_v1`, `multipath_rician_awgn_project_v1`; values у config є project defaults, не авторськими. `s1_structure_reconstruction_profile(...)` приймає обов'язкові numeric values і позначає структурну реконструкцію. Немає default прихованого padding, delay rounding, SNR normalisation чи correlated-noise substitution.

## Перевірки та реальний кадр

- REPRO-03 targeted tests: 21 passed; весь `tests/repro`: 44 passed. Перевірки включають незалежний two-path fixture, 16 незалежно перевірених transition vectors, identity, gain, pure delay, multi-path, AWGN statistics, Rician power/K/correlation/reproducibility, seed separation, truth isolation, CLI/serialization/plots.
- Full regression: `python -m pytest -q --tb=short --maxfail=1 --basetemp tmp/pytest-repro03-final -p no:cacheprovider` — 1021 passed in 71.53s.
- `ruff check src tests` — PASS; `ruff format --check src tests` — PASS, 194 files already formatted.
- Reference input: `outputs/repro02/reference_n_star` — 20,000 TCM steps, 40,000 input bits, 160,000 transmitted complex samples.
- Multipath profile output: two paths, delays 0/3 samples, 160,003 received samples; channel 0.1498 s, plots 0.0980 s in this single run.
- Result arrays occupy 27,240,456 bytes. This is materialized array storage, not process peak RSS; measurement is one run, not a benchmark.
- 16 SVG plots generated from actual channel truth/observation; all artifact/plot hashes in the manifest verified. Observation hash: `1bc276f254e358b5a4a52e8585f9a5616d00f554e3a84847a26cd58f16cb34ed`; receiver NPZ SHA-256 `1d9c1c95e0dcfb80971b000a2fc392697931f8cde38fee56990ea966fb6260e4`; evaluation truth NPZ SHA-256 `fe9db789be9c27023bd60e564bcc7e0afdd1eaab09cf8f078c540afe2e027b2c`; output `manifest.json` SHA-256 `0f291e155dd586901aafd94df3b374208c0b7c04b097c35f44d046fc40d33ae2`. Total output files 18,323,384 bytes.
- Manifest provenance pins transmitter sample SHA-256 `77317d2e41966694675e1ebed9fca8f530348d70a471495f0e9c63714ae8e459` and information-bit SHA-256 `ce1dcfcd5c9fece276ffee1106a330b0539dca36db14dbd5d08749a5b920f148` in addition to source and mapping fingerprints.
- Receiver observation and evaluation truth serialize separately. `paper_exact:false`, `receiver_enabled:false`.
- Historical M5–M10 SHA recount: 694/694 matched, zero missing or changed.
- Input S1 `references/source_paper_2026.docx` SHA-256 `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8` remained unchanged. Corrected REPRO-01 vector/spec hashes at verification: `REPRO_01_ENCODER_SPEC.json` `df420ae8347d810355f91c6014a944b5084316972ae26aec8a2a7bbd8ded1767`; `REPRO_01_ENCODER_TEST_VECTORS.json` `cfa1cdfefeca24340e193e4dfed864f050b814009236d46ef46a20c726748ef3`.

## Межі

Не встановлено авторських physical values для L/delays/K/power/noise/SNR/initial conditions/RNG; exact v7 file absent. Rician approximation is not proof of HF fading fidelity. No fractional delay, Doppler/Jakes spectrum, passband/RF, matched filter, physical Eb/N0, A(9)–A(10) baseband mapping, receivers, BER/SER, or Monte Carlo. Historical M5–M10 code/artifacts and REPRO-02 transmitter math are outside changes. REPRO-04 is not started.
