# REPRO-01 — реєстр джерел

Перевірено 2026-11-06. Формули звірялися візуально зі сканами доступних сторінок.

| ID | Фактичний шлях | SHA-256 | Версія/стан |
|---|---|---|---|
| S1 | references/source_paper_2026.docx | a03ff0b41a79d1fe9b4051c2e94c4ea78f72ac5f7fc30269e590150b2ed653c8 | Локальна редакція не підтверджена як v7; metadata revision 14, modified 2026-10-26 |
| S2 | references/supervisor/Яковів_Гриненко_2026_в7 27-10-26(4).docx | ВІДСУТНІЙ | Точний v7 не знайдено, іншою редакцією не замінено |
| S3 | references/supervisor/Раздел_4.doc | ВІДСУТНІЙ | Запитаний DOC відсутній |
| S4 | references/supervisor/Раздел_4.pdf | fa802b480e6d49089847867aacb2702231df758d1c990320b3d471202951f77d | PDF 42 сторінки; переглянуто PDF 18–21 / друковані 126–129 |
| S5 | references/supervisor/4.pdf | 97b8868bbb3cd48a7113fa89615bac5286f185957f9441d7159b9f7d548a5904 | 6 рукописних сторінок; усі візуально переглянуті; робочі нотатки |
| S6 | references/supervisor/Яковів_Гриненко_2026_в3_24_10_2026.docx | 2f070e438f1d8fa4a6cd84e3e6cab24c560ba55670c93ec759a6f4fe82e76b58 | Інша редакція v3, не замінює v7 |
| S7 | references/Автореферат_1-1.pdf | 4976650c8b66dcb19591fe994123273bad44554fa316ed1ccfaa56e4ba17d2c7 | Контекст, не заміна статті |

Скани references/key_pages, друковані стор.4–7: SHA-256 відповідно 9badaf252cf49f39966ac1df95cfa4abf8ce588c8914a5fc5b363e290b9a89ee, 1cf330cf21eee47035fc2b6dba57c9e34a8b6150d55106b06c1f8a85b27aa791, 571b196c7496e5de2ded8923ff10168c7b2f0fe13ecb278f602ae946abc16053, 404ea3a6a6728771e360f70b064e13af6dc7eac0c4c5df0a8e56f41dbd28bc3e. Сканів стор.1–3 немає. Посилання у документах наведені як source ID + друкована сторінка + equation/figure/table; DOI та бібліографічні реквізити не вигадувалися. Metadata S1 не доводять, що це v7.

Зіставлений код: src/hf_tcm/coding/encoder.py, trellis.py; modulation/labeling.py, psk8.py; decoding/paper_metric.py та reconstruction_viterbi.py; channels/rician.py, multipath.py, fluctuating_noise.py, awgn.py.

S4 — окреме джерело: Code 2, рис.4.6, має G₂=[[D²+D,1,0],[1,D²,D]], чотири delay registers, 16 станів/64 переходи, табл.4.2. Для відповідної методики розділу 4 використано 4 samples/symbol, тоді як стаття S1 задає 8. Не зливати ці профілі.
