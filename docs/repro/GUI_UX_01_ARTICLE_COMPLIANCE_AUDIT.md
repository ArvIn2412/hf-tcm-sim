# GUI-UX-01: аудит відповідності статті

Дата: 2026-11-10. Висновок: **ARTICLE COMPLIANCE: PARTIAL**. Математичний backend під час GUI-UX-01 не змінювався. `paper_exact:false`, `ARTICLE_REPRODUCTION_INSUFFICIENT_DATA` та `ENERGY_GAIN_NOT_ESTIMABLE` залишаються чинними.

## Джерела

Основне джерело — `references/Яковів_Гриненко_2026_в7 27-10-26(4).docx`, SHA-256 `4e41d33a898d2bfec2118a0cd11d3879ac01d4095264b14f7123bc9840d5f1e3`. Альтернативна редакція `(6).docx`: `190163b9f123e99648ce9dc2d57cb4fdcc24a8a675001009da41cb0ecf6f9a87`. Допоміжний `Раздел_4.doc`: `e877a9272da0e8baa0e4eb21256acf1e2112428d3dbf14472d9b12d3239cfd59`. Хеші збігаються з inventory `outputs/gui_ux_01/source_audit/source_hashes.json`.

Формули перевірялися також візуально з вбудованих оригінальних WMF/EMF, а не лише з текстового витягу. Контактний аркуш формул і рисунки кодера/маркування збережені в `outputs/gui_ux_01/source_audit/`. Вбудовані `image23.wmf`, `image38.wmf`, `image66.emf`, `image67.emf` у двох редакціях v7 побайтно однакові. Binary DOC оглянуто через окремий companion PDF; тотожність цих документів не припускається.

## Матриця відповідності

| Елемент | Першоджерело | Код / незалежне свідчення | Статус |
|---|---|---|---|
| R=2/3 convolutional TCM | v7 §4, рис. 2 | `repro/encoder.py`, encoder transition tests | `CONCEPTUAL_MATCH`; використовуються source-derived структура та проєктний API |
| Encoder A: чотири стани | v7, рис. 2 | `repro/trellis.py`; transition-vector tests | `EXACT_MATCH` для числа станів/структури рисунка |
| Encoder A: 16 входо-станних переходів | v7, рис. 2 | `repro/encoder.py`; 16 незалежних transition vectors | `EXACT_MATCH` для перевірених переходів |
| Породжувальні співвідношення | v7, рис. 2: c₂=u₀, c₁=u₁⊕D²u₁, c₀=Du₁ | `repro/encoder.py`; encoder reference tests | `EXACT_MATCH` для відображення згідно з рисунком |
| ADR-002 coded triple → phase index | У v7 рисунок 3 позначає гілки 0…7, але повна однозначна таблиця в доступному джерелі не встановлена | `repro/labeling.py`; mapping fingerprint tests | `PROJECT_DEFINED`; не заявляється як авторське маркування |
| 8PSK, Δφ=π/4 | v7 §4, текст біля модулятора | `repro/labeling.py`, `repro/modulator.py`; constellation tests | `EXACT_MATCH` лише для кількості точок/кроку фази; абсолютний phase offset — `PROJECT_DEFINED` |
| 8 відліків на елемент | v7 §4, після (10), n=8 | `repro/waveform.py`; ZOH/index tests | `EXACT_MATCH` для числового значення 8; прямокутний ZOH — `PROJECT_DEFINED` |
| Модель багатопроменевого сигналу | v7 §2–4, (6) | `repro/multipath_channel.py`; independent convolution fixtures | `CONCEPTUAL_MATCH`; дискретний complex-baseband, integer-delay профіль є проєктним |
| Delays [0,3], zero extension | Джерело не фіксує повний набір цих чисел для поточного кадру | `repro/channel_config.py`, `repro/isi_predictor.py`; ручний oracle | `PROJECT_DEFINED`; дробові затримки не підтримані |
| Rician fading | v7 §2–4, променеві квадратури | `repro/rician_fading.py`; marginal/K/correlation tests | `CONCEPTUAL_MATCH` для типу розподілу; AR(1), K=[4,1], ρ=.98 — `PROJECT_DEFINED` |
| Незалежність tap processes | Не встановлена повна joint covariance | `repro/channel_runner.py`; seed-separation tests | `INSUFFICIENT_EVIDENCE` щодо авторської covariance |
| Source noise recursion (9)–(10) | v7, (8)–(10): корельовані гаусові квадратури | REPRO complex `noise.py` генерує iid complex AWGN | `MISMATCH` для буквального процесу (9)–(10); AWGN profile коректний у власній конвенції |
| Noise normalization | v7 дає квадратурні формули, але фізичний baseband sample interval тут не закриває повну конверсію | `repro/noise.py`; незалежні квадратурні variance tests | `PROJECT_DEFINED` sample-domain; це не фізичне Eb/N0 |
| Адаптивне оцінювання каналових квадратур | v7 (1)–(2) | `repro/adaptive_multipath_receiver.py`; estimator recursion/causality tests | `CONCEPTUAL_MATCH`; Kalman/RLS survivor-specific реалізація не є буквальним source recursion |
| Евклідова метрика, формула (2) | Візуальний оригінал `image38.wmf` | `repro/euclidean_metric.py`, `repro/isi_metrics.py`; ручні residual fixtures | `MISMATCH`: production Σ|r|² або sqrt(Σ|r|²); видимий друкований вираз має signed residual sum без квадрата/нормування. Причина (описка чи інше означення) невідома |
| ISI-aware trellis | Viterbi і багатопроменева структура описані концептуально | `repro/augmented_trellis.py`, `repro/expanded_viterbi.py`; exhaustive small-frame tests | `PROJECT_DEFINED`; для D=3 реалізовано augmented 17 states/68 transitions |
| η=20 | v7 §4 задає значення 20 | `repro/finite_viterbi.py`; latency/flush tests | `EXACT_MATCH` для числа 20; конвенція «20 переходів, latency 19» — `PROJECT_DEFINED` (надрукований індексний інтервал може містити 21 позицію) |
| Separate B0 | Окремий hard demodulation/decode є предметом порівняння; точні front-end деталі не повністю задані | `repro/hard_8psk_demodulator.py`, `repro/hamming_viterbi.py`; independent tests | `CONCEPTUAL_MATCH`; receiver не компенсує невідомий multipath |
| Separate B1 | Авторська точна channel-aware hard front-end структура не встановлена | `repro/repro08_channel_aware_hard.py`; static public-tap tests | `PROJECT_DEFINED`; тільки підтримувані публічні статичні tap профілі |
| Paired comparison | Вимога порівнювати алгоритми за спільних умов | REPRO-07 runner; identical observation hash tests | `EXACT_MATCH` для фактичної пари спостережень у завершених trials |
| BER інформаційних бітів | Стаття в доступному матеріалі не дає всіх denominator/frame-flush деталей для сучасного API | `repro/receiver_evaluation.py`; independent error-count fixtures | `CONCEPTUAL_MATCH`; визначення й знаменник явно зафіксовані проєктом |
| Information-pair SER | Source metric p* не доведено тотожним decoded pair SER | `repro/information_pair_metrics.py`; pair/bit invariant tests | `PROJECT_DEFINED`; не ототожнюється з phase-symbol SER |
| p*=5·10⁻² | Позначення у статті не доводить, що це decoded payload BER | REPRO-08 crosswalk та evaluation code | `INSUFFICIENT_EVIDENCE` |
| N*=20000 | v7 §4 | Transmitter/experiment configs | `EXACT_MATCH` для заявленого frame-size number; тотожність до payload denominator не доведена |
| Energy gain 1.5 dB | Результат статті | У REPRO-08 крива не перетнула спільну цільову BER за фізично підтвердженої осі | `INSUFFICIENT_EVIDENCE`; `ENERGY_GAIN_NOT_ESTIMABLE` |

## Позначення, які показує інтерфейс

| UI назва | Символ | Джерело / одиниця | Пояснення `?` |
|---|---|---|---|
| Кількість елементів сигналу | F (програмний параметр) | одиниці решітки; джерельне N* окреме | Так; не прирівнює автоматично F до author payload length |
| Номер елемента сигналу | k (індекс GUI) | цілий індекс, без одиниць | Так; проєктний zero-based індекс |
| Номер комплексного відліку | n (абсолютний GUI index) | цілий індекс | Так; абсолютний sample index — програмна координата |
| Відліків на елемент | n=8 у статті; UI константа | відліки/елемент | Так; ZOH — проєктна схема |
| Глибина декодування | η | переходи решітки | Так; η=20, окремо від 20 samples |
| Дисперсія комплексного шуму | Без авторського символу в UI | потужність на complex sample | Так; sample-domain, не Eb/N0 |
| Коефіцієнт променя | h_l (кодова модель) | безрозмірний комплексний коефіцієнт | Так; проєктне позначення |
| Затримка променя | d_l (кодова модель) | комплексні відліки | Так; ціле число, не секунди |
| Rician K та кореляція | K_l, ρ (опис UI) | безрозмірні проєктні параметри | Так; не приписуються джерелу як точні числа |

## Висновки щодо ключових питань

1. Програмна структура відповідає загальній постановці спільного та роздільного приймання, але не є повністю source-exact.
2. Encoder A відповідає чотиристановій схемі рисунка 2 за незалежно перевіреними переходами.
3. Реалізовано вісім рівновіддалених фаз; точне авторське absolute labeling не доведено.
4. Канал є дискретною комплексною baseband реконструкцією з integer delays і AR(1) fading, не повною фізичною HF моделлю.
5. Оцінювач є causal/adaptive за принципом, але не буквальною реалізацією всіх формул (1)–(2).
6. Squared Euclidean профіль не збігається з видимим записом формули (2); потрібне авторське уточнення.
7. Viterbi працює з перевіреними trellis/metric rows, finite-depth має незалежні latency/flush тести; source convention для η індексації лишається неоднозначною.
8. Joint/B0/B1 є порівнюваними за observation hash; B1 має більше дозволеної інформації про статичні taps, тому не є чистим порівнянням метрик.
9. BER та information-pair SER тепер мають окремі визначення й незалежні підрахунки; phase-symbol SER — інша величина.
10. 1.5 dB не підтверджено, фізичний виграш зараз не оцінюється.
11. Критичні відкриті відмінності: метрика (2), джерельна корельована шумова рекурсія, фізична нормалізація, phase labeling, повні channel parameters і p*/N* знаменники.
12. Для точнішого відтворення потрібні однозначна таблиця mapping, авторські параметри каналу/дискретизації/шуму та визначення error target; математичні зміни не входили до GUI-UX-01.

Аудиторські незалежні тести: 65 math fixtures і 65 receiver fixtures пройшли; їхні журнали в `outputs/gui_ux_01/source_audit/`. Ці перевірки доводять локальні кодові інваріанти, а не повну відповідність статті.
