# REPRO-06C: channel model and causality

REPRO-03 створює `h_l[n]` на кожному receive sample. REPRO-06C також прогнозує та оновлює коефіцієнти на sample rate; воно не вважає h сталим усередині восьми відліків. Для AR(1) використано фактичний публічний контракт генератора: `g[n]=ρg[n−1]+sqrt(1−ρ²)u[n]`, із LOS/diffuse decomposition. `slow_fading_rician_ar1` додатково обмежує проєктний профіль `ρ≥0.98`; цей поріг є validation policy, а не значенням статті.

Для кожного отриманого індексу n та path delay d_l регресор містить саме переданий waveform `x[n−d_l]`. Поточний candidate phase використовується для source symbol k, phase history augmented node — для попередніх символів, а індекси поза переданим кадром дорівнюють нулю. Вікно останнього decoded step включає multipath tail. Немає RF carrier, автоматичних pilots, hidden-state sequence чи доступу до fading/noise realization.

Причинний порядок зафіксований у результаті: pre-update прогноз → branch metric → destination survivor comparison → winner-only filter measurement updates. Rician transition mean поширюється між сусідніми samples без спостереження для candidate score; covariance weighting не додається до евклідової метрики. Припущення про sample-domain complex noise variance записане окремо у receiver config.
