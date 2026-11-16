# M11h — невирішені наукові та інтеграційні прогалини

| Питання | Поточний факт | Що потрібно для закриття |
|---|---|---|
| Стаття Яковів–Гриненко v7 | Запитаний файл `Яковів_Гриненко_2026_в7 27-10-26(4).docx` у supervisor directory відсутній; доступна v3 не є заміною. | Надати саме v7, зафіксувати hash/version, зіставити рисунки/формули із A code. |
| Розділ 4 Word source | `Раздел_4.doc` відсутній; доступний тільки PDF. | Надати оригінал `.doc` та перевірити відмінності рендерингу/таблиць. |
| Encoder B phase mapping | Code 2 generator/table дозволяє encoder preview; absolute 8PSK phase labels не підтверджені. | Джерельне правило, яке однозначно переводить B/output/manipulation value у phase index, із прикладами автора. |
| Encoder B receiver | Немає погодженої channel observation, branch metric, termination чи decoder contract. | Окреме наукове рішення/ADR, сумісний receiver і незалежні scalar/trellis tests до інтеграції. |
| A source fidelity | Production A є 4-state/16-edge реконструкцією; джерельні ambiguity зберігаються. | Верифікувати саме v7 та отримати підтвердження unresolved author mapping/innovation. |
| Samples-per-symbol | Доступна методика глави 4: 4; M11f audit для v7: 8. У поточному Signal Explorer A: 8. | Узгоджений source section і обґрунтований режим між джерельними версіями; не змішувати моделі. |
| Viterbi depth | Decoder реалізовано на повному кадрі; `η=20` не реалізовано як traceback depth. | Окреме визначення finite-depth алгоритму та окремий acceptance/test set. |
| Channel model | Demo gain/noise — deterministic fixture. AWGN/multipath/Rician/fluctuating modules не підключені. | Визначити units, normalization, sample cadence, channel state та receiver contract; нова наукова модель потребує окремого рішення. |
| SCI-02 / SCI-03 / SCI-METRIC-02 | Залишаються OPEN; source semantics/metric не однозначні. | Першоджерельне уточнення або формальне документування меж reconstruction за прийнятою процедурою. |
| Projector trellis labels | Структурні QA проходять, але частина `ee#` labels у state graph візуально перекривається. | Окрема UI геометрія/label placement та повторне візуальне acceptance без зміни trellis data. |

Залишаються `paper_exact:false` та `receiver_enabled:false`. Немає доведеної універсальної переваги адаптивного receiver, equivalence/noninferiority, фізичного HF channel fidelity або нової stochastic evidence. Historical M5–M10 зафіксовані й не переосмислювалися.
