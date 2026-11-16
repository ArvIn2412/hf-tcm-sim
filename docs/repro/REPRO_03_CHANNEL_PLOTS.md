# REPRO-03 — графіки каналу

Read-only `channel_plot_adapter.py` будує 16 SVG безпосередньо з `ChannelResult`: Tx I/Q; per-path gain magnitude; per-path phase; coefficient real/imag; delays; average path powers; path contributions у synchronized window; sum channel contribution; generated noise I/Q; received I/Q; Tx-vs-Rx; received magnitude; received phase; impulse-response coefficients на вибраному відліку; 20-symbol window; 20-sample detail.

На графіках є українські назви й осі, числові одиниці/конвенції, легенди, абсолютні sample markers, вибраний symbol і межі visual window. Для коротких кадрів вікно обмежується реальною довжиною кадру. Вікно прив'язане до transmitted timeline, а channel tail видно на full-frame графіках. Довгі ряди для SVG downsample-уються індексованим зрізом лише для відображення; числові NPZ дані не змінюються.

Графіків BER/SER, декодування чи вигаданого RF carrier немає. Перевірка XML підтверджує синтаксис усіх згенерованих SVG.
