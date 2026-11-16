# M12 — заморожений реєстр наукових доказів HF-TCM-SIM

**Дата фіксації:** 2026-11-02  
**Статус коду:** `paper_exact:false`, `receiver_enabled:false`  
**Source fidelity:** `SOURCE_AUDIT_COMPLETE` / `PAPER_PARTIAL`  
**Відкриті питання:** SCI-02, SCI-03, SCI-METRIC-02 — OPEN.

Цей документ є read-only індексом збережених доказів, а не новим результатом
симуляції. Рахунки нижче перевірено за наявними checkpoint-ами та звітами. У
M9b/M10b/M7b/M8b-recovery reference bits і decoded arrays у checkpoint-ах
порівнювалися простим підрахунком помилок без виклику коду приймача. M5j
checkpoint містить уже збережені цілочислові лічильники; його незалежний
історичний recount зафіксовано в M5k. Жодне спостереження, декодований шлях,
метрика або довірчий інтервал не генерувалися повторно в цьому freeze.

## Правила інтерпретації

- BER = pooled bit errors / pooled information bits; SER = pooled coded-symbol
  errors / pooled coded symbols. Знаменники наведені окремо.
- ΔBER і ΔSER обчислюються як Anchored/C мінус Frozen B, якщо нижче не
  зазначено інше. Від'ємна точкова оцінка не є доказом переваги без відповідної
  невизначеності.
- M7/M8 — результат відбору/порівняння в TRAIN partition; незалежної
  VALIDATION або FINAL partition немає. Їхні точкові значення не є
  підтверджувальною оцінкою.
- M9b/M10b мають наперед зафіксовані evaluation policies і парні кластери.
  Їхні 95% intervals містять нуль. Це не доводить superiority,
  equivalence, noninferiority чи відсутність ефекту.
- Усі ці результати належать реконструйованим офлайновим конфігураціям; це не
  paper-exact і не повна фізична модель HF-каналу.

## M5 — frozen B проти historical combined C

### Ранні M5 записи: окремі exploratory/pilot partitions

M5f зберіг 12 paired exploratory clusters, F=32, 64 бітів і 32 coded symbols
на run. Чисельники: B=0/768 bits і 0/384 symbols; C=189/768 і 181/384.
Отже, pooled BER дорівнює 0 і 0.246094, SER — 0 і 0.471354;
`ΔBER=+0.246094`, 95% exploratory paired CI `[+0.207031, +0.282552]`,
`ΔSER=+0.471354`, CI `[+0.406250, +0.533919]` (точність як у звіті).
Зафіксовані warning flags:
too few clusters (12), rare counts, degenerate B bootstrap та unreliable
interval. Нульова B похибка на 12 коротких кадрах не є доказом нульового
істинного BER.

M5h був окремим planning pilot: 120 runs, 30 paired clusters у кожній з
чотирьох effective discrete gamma strata; кожен має 512 bits і 256 coded
symbols, отже знаменники 15 360 і 7 680 на stratum/policy.

| γb, eff. | Policy B bit errors/BER | Policy C bit errors/BER | ΔBER [95% paired CI] | B symbol errors/SER | C symbol errors/SER | ΔSER [95% paired CI] | Статус |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0 dB | 3 988/15 360; 0.2596354 | 7 262/15 360; 0.4727865 | +0.2131510 [0.1915999, 0.2337272] | 3 509/7 680; 0.4569010 | 6 111/7 680; 0.7957031 | +0.3388021 [0.3096289, 0.3652376] | PILOT |
| 5 dB | 349/15 360; 0.0227214 | 5 929/15 360; 0.3860026 | +0.3632813 [0.3443994, 0.3809261] | 332/7 680; 0.0432292 | 5 463/7 680; 0.7113281 | +0.6680990 [0.6394401, 0.6938835] | PILOT primary stratum |
| 10 dB | 0/15 360; 0 | 5 388/15 360; 0.3507813 | +0.3507813 [0.3341113, 0.3668685] | 0/7 680; 0 | 5 187/7 680; 0.6753906 | +0.6753906 [0.6455729, 0.7016927] | PILOT; rare/degenerate warnings |
| 15 dB | 0/15 360; 0 | 5 240/15 360; 0.3411458 | +0.3411458 [0.3308561, 0.3521501] | 0/7 680; 0 | 5 024/7 680; 0.6541667 | +0.6541667 [0.6384115, 0.6710970] | PILOT; rare/degenerate warnings |

M5h intervals are pilot descriptions, not confirmatory/population conclusions;
the zero-error strata have degenerate B intervals. Neither M5f nor M5h was
pooled into M5j. Their configurations, separate seed namespaces and output
manifests remain preserved.

| Джерело | Partition / policy | Bit errors / bits | BER | Symbol errors / symbols | SER | Provenance / статус |
|---|---|---:|---:|---:|---:|---|
| M5j confirmatory; M5k read-only recount | EVALUATION, `historical_frozen_B` | 1,079 / 51,200 | 0.02107421875 | 1,003 / 25,600 | 0.0391796875 | 100 paired sequences; fixed 5 dB effective discrete γb, ADR-015 L=1; valid 100/100 |
| M5j confirmatory; M5k read-only recount | EVALUATION, `historical_combined_C` | 19,793 / 51,200 | 0.38658203125 | 17,956 / 25,600 | 0.70140625 | Same received buffer per B/C run; valid 100/100 |

`ΔBER = BER_C − BER_B = +0.3655078125`; 95% paired cluster-bootstrap CI
`[0.35548681640625, 0.37578173828125]`. `ΔSER = +0.6622265625`; 95% CI
`[0.6474599609375, 0.6771494140625]`. Each interval uses the archived ADR-014
2,000 paired whole-run resamples. This is a large observed contrast for these
two frozen policies in one fixed reconstructed profile; it does not establish
universal adaptive inferiority, an error in [A], a physical Eb/N0 result, or
the cause of the contrast. Per-symbol M5j estimator histories were not saved.

M5j provenance: 100 ordered evaluation IDs, 100 paired B/C outputs, no
failures, 51,200 information bits and 25,600 coded symbols per policy; the
approved config, child seeds, received hashes, code fingerprints, summary and
independent verification are preserved under
`outputs/m5j_confirmatory/20261029T-run/`. Pilot M5h and exploratory M5f are
not pooled into M5j.

## M6 — deterministic mechanism diagnostics

M6 is not a performance evaluation. M6a/M6b inspect fixed deterministic or
fresh-seed short traces; M6c/M6d audit equations and source evidence; M6e–M6h
perform controlled deterministic interventions/replays. In M6b, three paired
F=32 B/C diagnostic sequences yielded 192 B/C symbol rows. For each run,
`B` had `0/64` bit errors and `0/32` symbol errors; `C` had respectively
`16/64, 14/32`, `16/64, 15/32`, and `26/64, 21/32`. These small trace counts
are descriptive diagnostics, not a pooled estimator or inferential sample.
They show an implementation dependency: a post-update state can affect the
next symbol's predictions/metrics. They do not prove that this mechanism caused
the M5j contrast.

M6b provenance: exactly three planned fresh-seed IDs; data/noise streams were
shared within B/C; traces carry 16 metrics/posterior values, clocks, cutoffs,
and causal-order checks. The weighted innovation is a derived scalar replay,
not a raw exported B4c field. M6c independently checked [A](1) explicit
operand algebra and [A](5) signs against scalar arithmetic; source operand
equivalence remains unresolved. The intervention/factorial/posterior-clamp
traces remain deterministic fixture-specific results. There are no M6 BER
confidence intervals.

## M7 — exploratory TRAIN policy selection

Frozen grid: nine candidates `a100_k000`, `a100_k050`, `a100_k100`,
`a095_k000`, `a095_k050`, `a095_k100`, `a085_k000`, `a085_k050`,
`a085_k100`; F=256, 512 bits and 256 coded symbols per sequence. The
checkpoint recount covered 40 TRAIN sequences, 360 candidate records, and
20,480 bits / 10,240 symbols per candidate. No validation or final stream was
derived or executed. Selected `a100_k000` is exactly the frozen-B control and
is recorded as `TRAIN_SELECTED_NOT_VALIDATED`.

| Candidate | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|
| `a100_k000` (frozen B) | 478 / 20,480 | 0.02333984375 | 441 / 10,240 | 0.04306640625 |
| `a095_k000` | 1,903 / 20,480 | 0.092919921875 | 1,559 / 10,240 | 0.15224609375 |
| `a100_k050` | 3,050 / 20,480 | 0.14892578125 | 2,333 / 10,240 | 0.22783203125 |
| `a100_k100` | 4,831 / 20,480 | 0.235888671875 | 3,835 / 10,240 | 0.37451171875 |
| `a085_k000` | 4,871 / 20,480 | 0.237841796875 | 4,006 / 10,240 | 0.3912109375 |
| `a095_k100` | 7,357 / 20,480 | 0.359228515625 | 6,799 / 10,240 | 0.66396484375 |
| `a095_k050` | 7,575 / 20,480 | 0.369873046875 | 6,791 / 10,240 | 0.66318359375 |
| `a085_k100` (historical C) | 8,093 / 20,480 | 0.395166015625 | 7,339 / 10,240 | 0.71669921875 |
| `a085_k050` | 8,545 / 20,480 | 0.417236328125 | 7,502 / 10,240 | 0.7326171875 |

The outputs were recounted from the 40 saved TRAIN checkpoints; each received
buffer was shared by the nine policy calls. No inferential CI or independent
validation is claimed. The TRAIN ranking is subject to selection on the same
partition.

## M8 — anchored exploratory TRAIN and recovery

The original M8b TRAIN attempt is preserved as an orchestration failure:
40 inputs, 320 policy records, 320 `KeyError('clock_origins')` failures, zero
decoder calls, and no BER/SER. No error count was imputed. An explicitly
authorized technical recovery replayed the same 40 IDs/seeds; all received
hashes matched before decoding. It completed 320/320 decoder calls and was
independently recounted. It is the same TRAIN sample, not an independent
replication. Each candidate has 20,480 bits and 10,240 symbols.

| Candidate | Bit errors / bits | BER | Symbol errors / symbols | SER | TRAIN ranking status |
|---|---:|---:|---:|---:|---|
| `historical_frozen_B` | 413 / 20,480 | 0.020166015625 | 371 / 10,240 | 0.03623046875 | 1 |
| `anch_a085_k025` | 429 / 20,480 | 0.020947265625 | 385 / 10,240 | 0.03759765625 | 2 |
| `anch_a095_k025` | 490 / 20,480 | 0.02392578125 | 440 / 10,240 | 0.04296875 | 3 |
| `anch_a085_k050` | 528 / 20,480 | 0.02578125 | 463 / 10,240 | 0.04521484375 | 4 |
| `anch_a095_k050` | 924 / 20,480 | 0.0451171875 | 786 / 10,240 | 0.0767578125 | 5 |
| `anch_a100_k025` | 1,501 / 20,480 | 0.073291015625 | 1,204 / 10,240 | 0.117578125 | 6 |
| `anch_a100_k050` | 3,000 / 20,480 | 0.146484375 | 2,324 / 10,240 | 0.226953125 | 7 |
| `historical_combined_C` | 7,804 / 20,480 | 0.3810546875 | 7,074 / 10,240 | 0.6908203125 | 8 |

Frozen B was selected; anchored `anch_a085_k025` is the post-hoc runner-up,
not a validated winner. M8 did not produce a confirmatory CI or independent
validation. M8 closeout additionally extracted a read-only same-TRAIN paired
runner-up contrast: ΔBER=+16/20 480=+0.00078125, exploratory post-selection
95% CI [−0.002197265625, 0.003369140625]; ΔSER=+14/10 240=+0.0013671875,
95% CI [−0.00390625, 0.00595703125]. This uses the same 40 selected TRAIN
clusters, after policy ranking; it is not independent and cannot establish
equivalence or noninferiority. The M8 closeout differences are descriptive.

## M9 — independent fixed-policy evaluation

M9b compared the two frozen policies prospectively after the M8 TRAIN selection
but is not independent validation of the M8 grid. The raw checkpoint recount
compared saved reference bit/symbol arrays with decoded arrays for 100 runs,
200 policy records and 200 decoder invocations; IDs, seeds, approved config,
source fingerprint, and same-received hashes are retained in the M9 output
manifest. Each policy has 51,200 bits and 25,600 symbols.

| Policy | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---:|---:|---:|---:|
| `historical_frozen_B` | 1,130 / 51,200 | 0.0220703125 | 1,050 / 25,600 | 0.041015625 |
| `anch_a085_k025` | 1,072 / 51,200 | 0.0209375 | 1,001 / 25,600 | 0.0391015625 |

`ΔBER = BER(anchored) − BER(B) = −0.0011328125`, 95% paired whole-run
cluster-bootstrap CI `[-0.00322265625, 0.00068359375]`. `ΔSER = −0.0019140625`,
95% CI `[-0.0053125, 0.0011328125]`. Both include zero. No superiority,
equivalence, or noninferiority follows. The profile is L=1 real gain 0.75,
zero delay, fixed normalized 8PSK/ZOH, ADR-005/012/013/015 and effective
discrete γb=5 dB; it is not physical HF Eb/N0.

## M10 — fixed policies with controlled variable gain

M10b crossed 100 paired run clusters, three frozen gain schedules, and two
policies: 300 received buffers, 600 policy records/decoder calls; 51,200 bits
and 25,600 symbols per policy/profile. Checkpoint recount matched stored raw
counts for all six cells. Noise, waveform, and policy pairing are preserved by
run ID and hashes.

| Profile | Policy | Bit errors / bits | BER | Symbol errors / symbols | SER |
|---|---|---:|---:|---:|---:|
| P0 constant | `historical_frozen_B` | 1,202 / 51,200 | 0.0234765625 | 1,107 / 25,600 | 0.0432421875 |
| P0 constant | `anch_a085_k025` | 1,180 / 51,200 | 0.023046875 | 1,106 / 25,600 | 0.043203125 |
| P1 high-to-low | `historical_frozen_B` | 4,136 / 51,200 | 0.08078125 | 3,679 / 25,600 | 0.1437109375 |
| P1 high-to-low | `anch_a085_k025` | 4,120 / 51,200 | 0.08046875 | 3,660 / 25,600 | 0.14296875 |
| P2 low-to-high | `historical_frozen_B` | 4,205 / 51,200 | 0.08212890625 | 3,777 / 25,600 | 0.1475390625 |
| P2 low-to-high | `anch_a085_k025` | 4,208 / 51,200 | 0.0821875 | 3,780 / 25,600 | 0.14765625 |

Primary P1: `ΔBER = −16/51,200 = −0.0003125`; paired full-run 95% CI
`[-0.00205126953125, 0.0014453125]`, which includes zero. The P1 `ΔSER` is
`−19/25,600 = −0.0007421875`; CI `[-0.0037900390625, 0.0022275390625]`.
P0/P2 and segment counts are secondary/descriptive. P1 and P2 use the same two
gain values in opposite order; P0 has a different gain distribution. Profiles
are synthetic controlled real-gain schedules, not HF fading.

Усі збережені profile-level contrasts наведені нижче, щоб не приховувати
вторинні оцінки. Інтервали є парними, по 2 000 resamples повних run clusters;
для кожної пари profile/policy використовуються узгоджені run IDs.

| Contrast | Point estimate | 95% paired CI |
|---|---:|---:|
| ΔBER P0 | −0.0004296875 | [−0.0024609375, 0.00154296875] |
| ΔBER P1 (primary) | −0.0003125 | [−0.00205126953125, 0.0014453125] |
| ΔBER P2 | +0.00005859375 | [−0.00214892578125, 0.00224609375] |
| ΔSER P0 | −0.0000390625 | [−0.0036728515625, 0.0035546875] |
| ΔSER P1 | −0.0007421875 | [−0.0037900390625, 0.0022275390625] |
| ΔSER P2 | +0.0001171875 | [−0.0031640625, 0.00359375] |
| ΔBER P1 − ΔBER P0 | +0.0001171875 | [−0.00255859375, 0.00285205078125] |
| ΔBER P2 − ΔBER P1 | +0.00037109375 | [−0.00232421875, 0.00316455078125] |

Усі наведені M10 intervals містять нуль. Вторинні contrasts — descriptive;
додаткове confirmatory або multiplicity-adjusted твердження не робиться.

## Hashes, immutable baseline, and reproducibility boundary

M11e recorded **694/694** M5–M10 output/config/non-evaluation-math fingerprints
matched, with zero missing entries or mismatches. The immutable M11c release
manifest remained unchanged. M12 did not call receiver APIs or alter any
checkpoint, manifest, accepted ADR, GUI, or production source. This document
does not claim that the historical numerical results were reproduced in a
different Python/NumPy environment. Source evidence still supports only a
partial relationship to [A]; SCI-02, SCI-03, SCI-METRIC-02 remain OPEN.

## Read-only recount performed for this freeze

The command used an inline Python standard-library script that loaded only
saved records/checkpoints under M5f, M5h, M5j, M7b, M8b recovery, M9b, and M10b.
M5f run-level integer counters and paired received hashes were pooled and
checked; M5h's 120 saved checkpoint records were pooled by their stored
`gamma_b_eff_db` and confirmed 30 per stratum. For M9b,
M10b, M7b, and M8b it compared each saved `decoded_information_bits` and
`decoded_symbol_indices` elementwise with the checkpoint's reference arrays,
asserted that the resulting integer error totals equal the stored count record,
then pooled counts by candidate/profile. It did not import `hf_tcm`, compute
metrics, call an estimator or decoder, create random numbers, or write files.
For M5j it pooled the saved `b_counts`/`c_counts`; the independent M5k replay
is the preserved source for comparison with reference/decoder outputs.
