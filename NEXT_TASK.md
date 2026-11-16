# Наступне завдання

SCIENTIFIC-EXP-03A завершено як підготовка контрольованого metric-isolation експерименту. Реалізовано A-E/A-H з однаковими observations/frontend результатами та η=20; AWGN direct лишається окремим контрольним режимом. Збережено 205 незалежних пілотних пар, які пройшли незалежний перерахунок. Послідовна регресія: 1 256 passed; scoped Ruff/format і Node пройшли; Edge QA 5/5; історичні fingerprints 694/694. Деталі: `docs/research/SCIENTIFIC_EXP_03A_FINAL_REPORT.md` та `HF_TCM_SIM_SCIENTIFIC_EXP_03A_PREPARATION_AUDIT.zip`.

Основні обмеження: clean-tail combiner математично точний лише для 8-sample ZOH та causal integer delays `D<8`; у Rician лишаються tracking residual і корельований ефективний шум. Пілоти не дають стабільної оцінки виграшу; Rician BER=0,05 не перетинається в виміряному діапазоні. Дискретна шкала не є фізичним Eb/N0; `paper_exact:false`; 1,5 дБ зі статті не підтверджено.

**Рекомендований наступний крок:** перед авторизацією SCIENTIFIC-EXP-03B провести окремий design review пілотної cadence/оцінювання Rician каналу та завершити виміряний F=1024 budget preflight. Поточний runner блокує confirmatory фазу, тому основна серія не запускалася. Жоден наступний milestone не розпочинається автоматично.
