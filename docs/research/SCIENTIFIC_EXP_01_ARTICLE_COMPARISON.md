# SCIENTIFIC-EXP-01: порівняння зі статтею

ARTICLE_1_5_DB_INSUFFICIENT_DATA.

Стаття 2026 повідомляє1,5дБ. Тут прийняті squared residual sum, complex iid AWGN і discrete γ_b,d — погоджені проєктні рішення, а не буквальна тотожність джерела. Приймач Joint використовує survivor-specific adaptive estimator; B0 не компенсує multipath; B1 має exact public static taps. Тому Joint/B0 — системний контраст повних алгоритмів.

Source p*=0.05 не доведено тотожним decoded information-bit BER. Source N*=20000 не встановлює всіх denominator/realization правил. Поточна робота дає independent F256 clusters і окремі F20000 controls. Фізичні sample period/noise PSD/matched filter HF calibration не визначені. Фактичні модельні оцінки й невизначеність див. SCIENTIFIC_EXP_01_ENERGY_GAIN_RESULTS.md; вони не підтверджують і не спростовують фізичний source gain. paper_exact:false.
