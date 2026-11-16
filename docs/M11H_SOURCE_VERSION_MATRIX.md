# M11h — реєстр версій джерел і source-to-code відповідність

Дата preflight: 2026-11-04. SHA-256 обчислено з фактичних байтів у робочій копії.

## Файли джерел

| Файл | Наявність / опис версії | Розмір, байт | SHA-256 | Використання та межа висновку |
|---|---|---:|---|---|
| `references/supervisor/Раздел_4.doc` | **Відсутній** | — | — | Не можна перевірити Word-оригінал; для доступного розділу використано PDF нижче. |
| `references/supervisor/Раздел_4.pdf` | Є, 42 сторінки, текстовий PDF | 1 313 542 | `fa802b480e6d49089847867aacb2702231df758d1c990320b3d471202951f77d` | Доступна копія розділу; переглянуто Code 2, рис. 4.6 і таблицю 4.2 у межах попереднього аудиту. Це не підміна `.doc`. |
| `references/supervisor/4.pdf` | Є, 6 сканованих рукописних сторінок; PDF creation/modification metadata: 2026-11-03 UTC; текстове вилучення не дає надійного машинного транскрипту | 33 594 192 | `97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904` | Переглянуто візуально як рукописні нотатки. Не використовувався для домислювання повної таблиці переходів чи фазових міток. |
| `references/supervisor/Яковів_Гриненко_2026_в7 27-10-26(4).docx` | **Відсутній** | — | — | Стаття v7 прямо не перевірена в цьому preflight; старішу статтю не використано як її заміну. |
| `references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx` | Є, версія v3 за назвою файла; DOCX core metadata: revision 17, created 2026-10-21T12:49Z, modified 2026-10-27T05:52Z | 228 353 | `2f070e438f1d8fa4a6cd84e3e6cab24c560ba55670c93ec759a6f4fe82e76b58` | Застаріліша наявна редакція; не використана як мовчазний доказ положень v7. |
| `references/supervisor/Yakoviv_Hrynenko_UA v2(1).rtf` | **Відсутній** | — | — | Перекладена редакція v2 не перевірена. |
| `references/source_paper_2026.docx` | Є у спільній теці references; у назві немає номера v7 | 228 348 | `a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8` | Зафіксовано як окремий наявний документ, не прирівнюється до запитаного файла v7. |

Файли джерел не редагувалися. Старіша стаття або рукописні нотатки не використані для заповнення відсутніх авторських означень.

## Fingerprints перевіреного implementation snapshot

Хеші наведені для точного стану після presentation-only M11h змін; це fingerprints робочих файлів, не версійні теги релізу.

| Код | SHA-256 |
|---|---|
| `src/hf_tcm/coding/encoder.py` | `6883e760a43903c1cbad6615cb7a70cb1193696d8243450da335111cd7c08405` |
| `src/hf_tcm/coding/encoder_b.py` | `f21c795ac6acc81816cebc6dd5df0ba3d127d9a5cdbb6d474b8961cfa08b45d8` |
| `src/hf_tcm/modulation/psk8.py` | `7d2c83892ddb10a955e21c39cf0085e120f107dd0879407aea18c8b4ff52739a` |
| `src/hf_tcm/studio/server.py` | `706f4779b044d99a8ef06b2082df9875bd4922bd2c7e1853479074640a9389b9` |
| `src/hf_tcm/studio/static/studio.js` | `a9163f637eb301828ae61df22b5769412f0d9ee865b636b184d66bdf271fa9c8` |
| `src/hf_tcm/studio/static/studio_ux.js` | `ba857f11d3bf273f77b71075131d935995e7b2381425303ae5cfa4823251508e` |
| `src/hf_tcm/studio/static/signal_window.js` | `c0fda66efe9f3f2122ab5dbf4ace524b7b7573234fbc557a44d35b92aedf4c03` |
| `src/hf_tcm/studio/static/studio_ux.css` | `115399f456009674512b8ef126e2c50f643406fdd5440411c13361a8eb8904ad` |

## Матриця відповідності encoder-ів

| Властивість | A — наявний HF-TCM-SIM | B — Code 2, глава 4 | Статус |
|---|---|---|---|
| Джерельна фігура | Рис. 2–3 запитаної статті v7; файл v7 відсутній. Є старіша копія статті, але вона не замінює v7. | Рис. 4.6 і таблиця 4.2 доступного `Раздел_4.pdf`. | A source match для саме v7 — неповний; B прив'язаний до наявної PDF-копії. |
| Кількість станів / переходів | 4 / 16; код: `src/hf_tcm/coding/encoder.py`, спільний edge catalog та A trellis. | 16 / 64; окремий код: `src/hf_tcm/coding/encoder_b.py`; 16 станів × 4 пари входу. | Кодери ізольовані один від одного. |
| Генераторна структура | Проєктне rate-2/3 кодування: state `(u1[k−1],u1[k−2])`, вихід `(u0,u1⊕u1[k−2],u1[k−1])`. | Доступна таблиця узгоджується з `G(D)=[[D²+D,1,0],[1,D²,D]]`; регістровий порядок `(1,3,2,4)`; вихід `(C2,C1,C0)`. | B генератор реалізований окремим preview; source fidelity статті A лишається частковою. |
| Порядок входу | Послідовні інформаційні пари `(u0,u1)` на TCM-символ. | `X0,X1`; порядок enumeration `00,10,01,11`, branch ID `4Y+X0+2X1`. | Для B підтримано саме зафіксований табличний порядок. |
| Початковий стан | A UI фіксує сумісний reset `(0,0)`; довільна початкова умова не відкрита. | Preview приймає ID 0–15; джерельна таблиця починається з нульового стану. | Custom state B змінює preview; не означає receiver termination contract. |
| Фаза | ADR-002 — реконструйоване project edge-to-phase mapping. | Параметр `B` у таблиці — manipulation value; як абсолютний 8PSK phase label не підтверджений. | Phase mapping B unresolved; фази/IQ/канал для B не показуються. |
| Приймач / Viterbi | Поточний A demo виконує наявний project trace, дві політики та conditional full-frame Viterbi. | Повної метрики, каналу, завершення trellis та сумісного decoder contract немає. | B receiver не реалізований і кнопка запуску для B вимкнена. |
| Тести | Існуючі encoder/trellis/receiver тести; M11g Edge QA виконує детермінований A POST. | `tests/test_encoder_b.py`, `tests/test_encoder_b_preview_api.py`; таблиця 64 ребер і preview API без виклику receiver. | B тестується як encoder/trellis preview, не як end-to-end modem. |

## Часові домовленості та channel

Попередній M11f source audit записав для статті v7 `8 samples/symbol` та `η=20`; доступна методика розділу 4 містить `4 samples/symbol`. Оскільки потрібний окремий файл v7 наразі відсутній, ці значення не позначені як повторно підтверджені саме за v7 у M11h. Signal Explorer проєкту працює з наявним A trace: 8 відліків/символ.

У A decoder працює над усією послідовністю frozen metric rows. Тому visual window у 20 символів не є traceback depth `η=20`. У реалізації не встановлено finite-depth decoder.

Модулі `channels/awgn.py`, `channels/multipath.py`, `channels/rician.py` та `channels/fluctuating_noise.py` існують окремо, але не складають channel path Demo Studio. Значення gain 0.75 і noise fixture належать детермінованому preset; це не загальна physical AWGN/SNR модель і не доказ роботи multipath/Rician у GUI.
