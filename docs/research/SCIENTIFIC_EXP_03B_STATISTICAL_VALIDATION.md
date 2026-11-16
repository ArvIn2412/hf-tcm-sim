# SCIENTIFIC-EXP-03B — статистична валідація

## Обсяг і цілісність даних

- A, ізольовані метрики: 22,800 завершених парних trials (5 сценаріїв × два sweep-и; 300 незалежних trial clusters на energy point).
- B, повні системи: 8,300 завершених парних кадрів (AWGN 2900, static 2900, Rician 2500; 100 кадрів на energy point).
- Разом: 31,100 confirmatory trials. Pilot/preflight не входить до інференції.
- Frozen protocol SHA-256: `d553e65fdad020f4887d252bb29bd88311b84b596bbba1e14fd4a806e71068c6`; аналіз обмежений confirmatory observations.
- Analysis JSON SHA-256: `7d363ce85d5c77c4573406b66971da402b5a3e8b497c969e9cfc2429a7e98dc7`.
- Усі 13 confirmatory study manifests мають planned=completed і status=completed; trial IDs у межах кожної серії унікальні.
- Незалежний replay counts: A `PASS`; B `PASS`. B nested record/array hashes, checkpoint chain і парні observation hashes пройшли loader verification.
- Системні сітки згруповано за замороженим `point_index`, а не exact float equality; виміряна \(\gamma_{b,d}\) перевірялась на допуск 1e−9 дБ. Це усунуло некоректне дроблення однієї енергетичної точки через floating-point roundoff без зміни records.

## Методи

BER = помилкові decoded payload bits / усі payload bits; SER = частка помилкових двобітових інформаційних пар; FER = частка кадрів щонайменше з однією помилкою. A paired \(\Delta BER=BER_E-BER_H\). У B парні різниці визначені між приймачами на одному observation.

Для інтервалів кривих використано 5 000 paired independent-trial cluster bootstrap повторів. Для gain bootstrap resamples усієї незалежної парної реалізації, не окремих бітів. Первинне перетинання — log₁₀(BER) проти виміряної енергії; linear BER наведено як sensitivity. Немає згладжування чи екстраполяції. Gain проходить критерій лише за обох суміжних bracketing points, не менше 200 errors на кожному arm у bracket і ≥95% допустимих bootstrap перетинів.

## Невизначеність та обмеження

Нульові виміряні помилки не трактуються як BER=0 probability; графіки мають нижню межу/попередження, а перетин target з нульовою помилкою в bracket є невизначеним за protocol. Rician cadence-32 A демонструє plateau у межах наявної сітки, але protocol не допускає називати його асимптотичним error floor. Серійна залежність усередині кадру не маскується псевдоресемплінгом бітів: одиницею bootstrap є trial/frame cluster.

Два confirmatory каталоги містять 6 272 661 612 байтів первинних даних разом із manifests і checkpoints (5,842 GiB). Незавершений повторний full scan через повільний OneDrive I/O було зупинено; trial outputs не змінено. Попередній незалежний analyzer provenance підтверджує повний array recount усіх metric records, парність і енергію для A, а для B — nested SHA manifests, checkpoint chain та independent count replay. Архівний пакет повторно перевірить CRC і SHA-256 кожного включеного файла.
