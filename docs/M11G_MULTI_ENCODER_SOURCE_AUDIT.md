# M11g — аудит джерел і коду двох encoder modes

## Перевірені джерела й реалізація

Аудит спирається на наявний у репозиторії `references/Раздел_4.pdf` (рис. 4.6 і табл. 4.2), `references/source_paper_2026.docx`, наявний файл статті Яковів–Гриненко v3 та попередні M11d/M11f source reports. Файли з буквальними назвами `Раздел_4.doc`, `4.pdf` і окремий v7 файл у `references/` не знайдені; висновки про розділ 4 обмежено наявним PDF. M11f зафіксував 8 samples/symbol і η=20 для статті v7; методика відповідного фрагмента розділу 4 — 4 samples/symbol.

| Властивість | Encoder A: стаття v7 / чинна реконструкція | Encoder B: Code 2, розділ 4 | Реалізація M11g |
|---|---|---|---|
| Вхід | Пара інформаційних бітів за TCM symbol | `X0,X1`, повні 2-бітові групи | B приймає послідовність пар; padding/truncation заборонено |
| Пам’ять / стани | 4 стани | 4 регістрові комірки `1,3,2,4`, 16 станів | Окремі state spaces; B state ID — таблиця Y |
| Генератор | Project/article-v7 mapping з наявного A ядра | `G(D)=[[D²+D,1,0],[1,D²,D]]` | B: `C2=X1⊕cell1⊕cell2`, `C1=X0⊕cell4`, `C0=cell3`; комірки — регістри (1,3,2,4) |
| Next state | Визначений наявним A trellis | `(X0,X1,cell1,cell3)` у порядку (1,3,2,4) | Виконаний окремо в `coding/encoder_b.py` |
| Input ordering | Наявний A edge catalog | Таблиця перебирає `00,10,01,11`; ID входу `X0+2X1` | B branch ID `4Y + X0 + 2X1` |
| Branches | 4×4 = 16 | 16×4 = 64 | Тести enumerують усі 64 ребра |
| Reset | A receiver contract: canonical `00` | Таблиця 4.2 починається з нульового стану | A UI fixed reset; B preview дозволяє state ID 0–15 і явно надсилає його API |
| Phase labels | 8PSK mapping у A — ADR-002 реконструкція | Таблиця B містить manipulation parameter `B`, але не встановлює його як абсолютний phase index | B UI не обчислює фази, IQ або samples |
| Receiver/Viterbi | У A є project receiver і conditional full-frame Viterbi | Повної metric/receiver/termination домовленості в джерелі та поточному A receiver немає | B `Run receiver` вимкнений; жодної підміни A receiver не зроблено |
| Часові домовленості | Стаття v7: 8 samples/symbol; η=20 | Розділ 4: у відповідній методиці 4 samples/symbol | Signal Explorer A лишає 8 samples/symbol; 20-symbol view не є Viterbi depth |

У B вихідна трійка записана у джерельному порядку `(C2,C1,C0)`. Параметр `B` preview обчислює як двійкове числове представлення цієї трійки, узгоджене з таблицею 4.2. Це не твердження про абсолютну фазу 8PSK.

## Статус

`SOURCE_ALIGNMENT_REVIEWED` для наявних документів і зафіксованих conventions. `ENCODER_B_PARTIAL`: матриця G, state/transition table і encoder перевірені, але фазове відображення, channel path та receiver/Viterbi для B не встановлені. Повна source fidelity лишається `PAPER_PARTIAL`; `paper_exact:false`.
