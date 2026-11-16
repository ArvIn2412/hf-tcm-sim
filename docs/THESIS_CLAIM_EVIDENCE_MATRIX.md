# Матриця «твердження — доказ» для чернетки магістерської

Категорії відтворюють доказову силу кожного твердження, а не його важливість.
`SOURCE_DOCUMENTED` означає, що локальна стаття прямо містить відповідне
положення; `ALGEBRAICALLY_VERIFIED` — що формулу зіставлено з незалежним
скалярним обчисленням за явних конвенцій; `DETERMINISTICALLY_VERIFIED` — що
перевірено детерміновану реалізацію; TRAIN та evaluation класифікують дані, а
не source fidelity.

| ID | Твердження | Розділ | Джерельний документ | Реалізація / тести | Експериментальний артефакт | Статус | Обмеження |
|---|---|---|---|---|---|---|---|
| C01 | Стаття розглядає TCM 8PSK та спільне оцінювання/декодування | Вступ, 1.1–1.3 | [A], вступ і стор. 2–7; `M11D_SOURCE_FIDELITY_AUDIT.md` | — | — | SOURCE_DOCUMENTED | Контекст статті не підтверджує конкретну реконструкцію |
| C02 | У [A] надруковано G(x)=[[1,0,0],[0,1+x²,x]], R=2/3 | 2.1 | [A], стор. 5, key page 5 | `coding/encoder.py`, encoder tests | — | SOURCE_DOCUMENTED | bit/state order і часовий індекс треба встановлювати окремо |
| C03 | Реалізовані рівняння c₂=u₀, c₁=u₁⊕u₁[k−2], c₀=u₁[k−1] відповідають вибраному розкладу G | 2.1 | [A], стор. 5; `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md` | `coding/encoder.py` | deterministic unit tests | ALGEBRAICALLY_VERIFIED | Верифіковано з проєктним convention delay/order |
| C04 | Реалізація має чотири memory states та 16 state/input branches | 2.1 | [A], Fig. 2–3, стор. 6 (часткова підтримка) | `coding/trellis.py`, `coding/hypotheses.py` | `M11E_FINAL_PATCH_REPORT.md` Edge QA | DETERMINISTICALLY_VERIFIED | State IDs і canonical rows — project reconstruction |
| C05 | Таблиця 16 переходів із b=4c₂+2c₁+c₀ є ADR-002 mapping | 2.1.1–2.2 | `ASSUMPTIONS_AND_DECISIONS.md`; `M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md` | `receiver/reconstruction_labeling.py`; mapping tests | — | PROJECT_RECONSTRUCTION | Авторське edge→b повне маркування не знайдене |
| C06 | Вісім точок 8PSK задаються рівномірними фазами | 1.2, 2.2 | [A], стор. 2, 5 (8PSK і фазовий індекс); code contract | `modulation/psk8.py` | — | SOURCE_DOCUMENTED | Абсолютна фазова орієнтація/labeling проєктна |
| C07 | Δφ=π/4 є фазовим кроком у виразі bΔφ | 1.2, 2.2 | [A], стор. 5, [A](3),(5) | `receiver/iq_prediction.py` | — | SOURCE_DOCUMENTED | Це не тотожне абсолютній φ₀ |
| C08 | [A](5) знаки −sin/+cos відповідають ізольованому IQ kernel за явних μ і b | 2.3.2 | [A], стор. 5; `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md` | `receiver/iq_prediction.py`, `tests/test_iq_prediction.py` | deterministic scalar oracle | ALGEBRAICALLY_VERIFIED | Не доводить ADR-012 complex-axis/sample convention авторську |
| C09 | Прямокутний ZOH із 8 samples/symbol використано в receiver profiles | 2.3.3 | `MATHEMATICAL_MODEL.md`; [A] повідомляє 8 samples/element | `receiver/reconstruction_forward.py` | M5–M10 approved configs | PROJECT_RECONSTRUCTION | ZOH і символне вирівнювання не встановлені статтею |
| C10 | M5–M9 evaluation використовують L=1, real gain 0.75 і ADR-015 circular AWGN | 2.3.4, 4 | M5/M9 configs and reports | evaluation channel/noise adapters | M5j/M9b manifests/checkpoints | PROJECT_RECONSTRUCTION | Не фізичний HF-канал або physical Eb/N0 |
| C11 | M10 задає P0/P1/P2 piecewise real gain profiles | 2.3.4, 4.6 | `M10_VARIABLE_GAIN_EVALUATION_REPORT.md` | M10 evaluation adapter | M10 configs/checkpoints | INDEPENDENT_EVALUATION | Synthetic schedules; profile contrast має обмеження |
| C12 | [A](1) містить weighted observed-minus-predicted residual update та full=fluctuating+regular | 2.6 | [A], стор. 4; `M11D_SOURCE_FIDELITY_AUDIT.md` | `receiver/paper_recursion.py` | — | SOURCE_DOCUMENTED | Source operands, init, clock і posterior semantics unresolved |
| C13 | One-step recursion арифметично відповідає явним project operands | 2.6 | `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md` | `paper_recursion.py`, estimator tests | fixed scalar M6c fixture | ALGEBRAICALLY_VERIFIED | Не підтверджує source identity operand arrays |
| C14 | [A](2) прямо не визначає square/norm/modulus residual; production uses squared residual | 2.4 | [A], стор. 4 scan; `M11D_SCIENTIFIC_GAPS.md` | `reconstruction_aggregate.py`, metric tests | — | UNRESOLVED | SCI-METRIC-02 OPEN; production form — reconstructed interpretation |
| C15 | Project uses L∝exp(−βF) and normalized edge weights | 2.5 | ADR-003/004/005 docs | `receiver/reconstruction_posterior.py`, tests | M6 traces / M11 fixture | PROJECT_RECONSTRUCTION | Не підтверджено як author HMM posterior/likelihood |
| C16 | B4d update at f can influence next symbol's prediction/metric | 2.6.1, 3.2, 4.3 | `M6_FRESH_TRACE_DIAGNOSTIC_REPORT.md` | sequence/metric/estimator modules and causality tests | M6b three F=32 traces | DETERMINISTICALLY_VERIFIED | Не доводить причинність M5j errors |
| C17 | Conditional Viterbi minimizes additive frozen branch costs under project tie/start/end rules | 2.7 | `M11D_SOURCE_FIDELITY_AUDIT.md` | `decoding/reconstruction_viterbi.py`, tests | M5–M10 saved evaluation paths | DETERMINISTICALLY_VERIFIED | Whole contract not established by [A] |
| C18 | BER and SER use separately retained integer denominators | 2.8, 3.2 | project metric contracts | `evaluation/error_metrics.py`, tests | M5–M10 records | DETERMINISTICALLY_VERIFIED | SER defined for coded symbols in cited experiments |
| C19 | M5j pooled B/C counts and rates as listed | 4.2 | `M5_CONFIRMATORY_EVALUATION_REPORT.md`; `M5_POST_CONFIRMATORY_SCIENTIFIC_AUDIT.md` | checkpoint count fields | 100 EVALUATION checkpoints; M5k recount | INDEPENDENT_EVALUATION | Only fixed reconstructed profile and policy pair |
| C20 | M5j ΔBER CI excludes zero for its B/C contrast | 4.2 | M5j report / M5k audit | ADR-014 bootstrap implementation | frozen bootstrap summary and audit | INDEPENDENT_EVALUATION | No universality, mechanism, or physical HF claim |
| C21 | M6 traces demonstrate implementation sensitivity/dependencies | 4.3 | M6 trace, factorial and mechanism reports | evaluation-only trace adapters | M6b/e/f/g/h deterministic records | DETERMINISTICALLY_VERIFIED | No root-cause attribution for M5j |
| C22 | M7 selected frozen B on 40 TRAIN sequences | 4.4 | `M7_TRAIN_POLICY_SEARCH_REPORT.md` | checkpoint recount code (read-only) | M7b TRAIN checkpoints | EXPLORATORY_TRAIN | No VALIDATION/FINAL; selection-biased |
| C23 | Original M8 attempt had no BER because all rows failed pre-decode | 4.4 | `M8_ANCHORED_TRAIN_REPORT.md` | runner failure record | original M8b attempt checkpoints | DETERMINISTICALLY_VERIFIED | Errors unavailable, not zero |
| C24 | M8 recovery selected frozen B on repeated same TRAIN IDs | 4.4 | `M8_TRAIN_RECOVERY_REPORT.md` | reference/decoded-bit recount | M8 recovery TRAIN checkpoints | EXPLORATORY_TRAIN | Same sample replay; not independent validation |
| C25 | M9b anchored−B ΔBER and 95% CI | 4.5 | `M9_FIXED_POLICY_EVALUATION_REPORT.md` / closeout | saved ref/decoded arrays recounted | 100 EVALUATION checkpoint pairs | INDEPENDENT_EVALUATION | CI crosses zero; M9 is not M8 validation |
| C26 | M10 P1 ΔBER and 95% CI | 4.6 | `M10_VARIABLE_GAIN_EVALUATION_REPORT.md` | saved ref/decoded arrays recounted | 100 run clusters, 3 profiles, 2 policies | INDEPENDENT_EVALUATION | CI crosses zero; synthetic variable real gain |
| C27 | M11e GUI shows deterministic F=32 trace and internals | 5 | M11e report and presentation docs | studio server/static assets | 293/293 Edge QA, 36 actual screenshots | DEMONSTRATION_ONLY | One fixture; not an independent statistical sample |
| C28 | M5j per-symbol estimator history is unavailable | 4.2–4.3 | M5k audit | Checkpoint schema inspection | M5j checkpoints | SOURCE_DOCUMENTED | Cannot reconstruct historical rows from final coefficients |
| C29 | A universal adaptive receiver advantage is established | Throughout | No supporting source/artifact | — | M5/M9/M10 evidence does not establish it | UNRESOLVED (claim excluded) | The thesis explicitly rejects this conclusion |
| C30 | The paper's reported 1.5 dB result is reproduced here | Abstract, 4.8, conclusions | [A], стор. 7 | No matching complete protocol implemented | No HF-TCM-SIM result establishes this | UNRESOLVED (claim excluded) | No independent evidence; do not attribute to project |
| C31 | The model is a full physical HF channel | 2.3.4, 4.6 | Source describes richer multipath model | project code/configs | M5–M10 use limited profiles | UNRESOLVED (claim excluded) | No ionospheric/field validation |
| C32 | Historical M5–M10 artifacts remained unchanged at M11e | 3.3, conclusions | `M11E_FINAL_PATCH_REPORT.md` | historical fingerprints | 694/694 match | DETERMINISTICALLY_VERIFIED | Integrity is not scientific replication |

