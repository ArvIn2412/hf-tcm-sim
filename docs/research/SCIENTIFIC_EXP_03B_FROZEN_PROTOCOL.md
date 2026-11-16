# SCIENTIFIC-EXP-03B — заморожений проект протоколу confirmatory дослідження

**Призначення:** протокол підготовлено після range-finding. Сам він не авторизує виконання. Новий runner gate `confirmatory` поки відсутній; жодного confirmatory trial за цим протоколом не запускався.

## Статус дизайну

Застосовується контрольований A-E/A-H metric contrast із pilot frontend; AWGN direct залишається базовим no-equalizer control. Oracle-CSI — тільки diagnostic, окрема namespace та окремі графіки. Повні B-Joint/B0/B1 receiver comparisons — самостійний системний контраст із окремими IDs, не об'єднувати оцінки gain із A-E/A-H.

Пілотні дані містять по п'ять кадрів на точку, мають немонотонність і не дають статистично стабільної сітки поблизу всіх перетинів. Тому сітки нижче є зафіксованим **широким candidate grid**, а не результатом підбору під вигідний outcome. Якщо хоча б один arm не перетне target, його gain позначається `NOT_ESTIMABLE`; екстраполяція заборонена. Результати pilot IDs 831031–831044 не включати до оцінки.

## Незмінні умови A-E/A-H

- Encoder A, 8PSK labeling, initial state `(0,0)`, trellis transition order та η=20 незмінні.
- На один cluster/energy point: одна payload sequence, одна pilot schedule, один channel realization і один noise realization; обидва arms отримують однакові `ReceiverObservation` та frontend output.
- Pilot frontend primary: preamble 4, burst length 4, cadence 32 symbols; 16/128 overhead у F=128 pilot. Перед confirmatory F=1024 ця точна schedule зберігається; pilots з F=1024 становитимуть 128/1024, payload 896 symbols/1792 payload bits.
- Rician pilot-period-8 — попередньо визначений sensitivity arm із окремою оцінкою та окремим overhead; не обирати як primary постфактум.
- Path profile fixed: AWGN unit path; static taps `1+0j`, `0.3−0.2j`, delays `[0,3]`; Rician average path powers `[1,0.25]`, K `[4,1]`, LOS phase `[0,0.7]` rad, AR(1) `rho=0.98/sample`, delays `[0,3]`; noise complex variance baseline 0.05.
- Primary sweep amplitude-at-fixed-noise; gamma axis is project discrete `E_b,d/σ_c²`, including training energy in numerator and payload bits only in denominator. Do not label physical Eb/N0.
- Outcomes: BER, information-pair SER, FER, decoder runtime; paired cluster bootstrap resamples whole independent channel/noise/bit trial clusters, not bits.
- Targets: primary 0.05; secondary 0.01; 0.001 exploratory only if enough errors and budget. Fixed monotone interpolation in log10(BER) versus gamma between observed adjacent bracketing points, applied within each bootstrap resample. No smoothing/extrapolation. If no bracket or insufficient valid bootstrap crossing fraction (<0.95), gain is non-estimable.
- Proposed inference: 5000 paired cluster-bootstrap resamples, 95% percentile interval; report valid crossing fraction and raw point counts. Bootstrap seed namespace separate from data RNG.
- Fixed-size initial design: F=1024, 100 independent clusters per energy point; no outcome-driven stopping. A separate blinded runtime preflight on 10 fresh clusters/point must fit the authorized cap; it is feasibility-only and cannot be pooled into outcomes. Confirmatory grid may be executed only after the preflight determines budget sufficiency and explicit 03B authorization.
- Trial records: store payload bits/decoded arrays, actual transmitted energy, channel/noise seeds, actual observation SHA-256, frontend hash, pilot ages, estimated gain, branch metrics, BER/SER/FER/runtime, and manifest. Resume only from matching immutable config and manifest; reject duplicate trial IDs.

## Candidate grids, amplitude offsets from A=1

| Scenario | Frozen offsets (dB) | Rationale / estimability rule |
|---|---|---|
| AWGN direct | `[-18,-17,-16,-15,-14,-13,-12,-11]` | Pilot brackets A-E around −16…−15 and Hamming around −15…−12; wide overlap retained |
| AWGN pilot frontend | `[-15,-13.5,-12,-10.5,-9,-7.5]` | Cover observed high-error region and adjacent points near both 0.05 curves; pilot results were noisy, so all points remain |
| Static multipath `[0,3]` | `[-15,-13.5,-12,-10.5,-9,-7.5]` | Covers both observed pilot brackets without narrowing to one favorable pair |
| Rician AR(1), period 32 primary | `[-3,0,3,6,9,12,15,18]` | Existing pilot never crossed 0.05; extend only to measure whether a crossing exists; no crossing means no gain |
| Rician AR(1), period 8 sensitivity | `[-9,-6,-3,0,3,6,9,12,15,18]` | Existing A-E points were already below target and Hamming above; extend on both sides for possible crossings; separately account for 50% pilot overhead at F=128 schedule ratio (for large F, exact count recomputed) |

Before preregistration is declared executable, independently validate that these amplitude offsets produce the intended `gamma_b,d` and that F=1024 pilot schedule count/energy is correct. The current runner's accepted phases are only `validation` and `range_finding`; a versioned confirmatory implementation must expose an explicit immutable protocol ID and reject edits to grid/seeds after first record.

## Seed and resource namespaces

Freeze root seeds distinct from the pilot domain: AWGN direct `831101`; AWGN pilot `831102`; static `[0,3]` `831103`; Rician period 32 `831104`; Rician period 8 sensitivity `831105`. For each record derive independent bits/channel/noise streams as `SeedSequence([root, 0x03B, scenario_id, point_index, cluster_index, stream_id])`; persist exact derived uint64 values. Do not use pilot roots 831031–831044 or pilot trial IDs. Bootstrap RNG uses a separate `SeedSequence([root, 0x03B_C1, scenario_id, bootstrap_replicate])` domain. These roots are reserved for this protocol and must not be reused by GUI acceptance or other studies.

Measured F=128 paired runtime is 0.0337–0.0397 s in memory, excluding writes. Linear F=1024 estimate is 0.27–0.32 s/pair. The grids above sum to 38 scenario-point cells; 100 pairs/cell is 3,800 paired frames and about 17–21 min raw compute by scaling; manifests, bootstrap and process overhead add unknown cost. Pilot records average about 37 kB per F=128 pair including JSON/NPZ; naive linear array scaling suggests roughly 0.3 GB for F=1024, with a conservative 0.3–1.2 GB disk envelope pending measured compression/I/O. Measure F=1024 preflight before allocating the confirmatory budget. Streaming one trial at a time keeps working memory bounded; budget peak RAM <512 MiB only after runtime instrumentation confirms it.

## Stop and release rules

No more than one confirmatory series is in flight. Budget exhaustion yields incomplete/partial status and immutable resume, not a success claim. Main conclusions require at least 95% valid bootstrap crossings for both compared arms; zero observed errors are represented by a binomial upper confidence bound, never as exact zero probability. Report error-floor evidence only if supported by a planned high-energy plateau design; the current candidate grid alone cannot establish an asymptotic error floor. Full receiver B results remain separate tables and estimates.

**Execution state: NOT STARTED.** SCIENTIFIC-EXP-03B requires explicit authorization and implementation of the frozen-runner gate; this document does not start it.
