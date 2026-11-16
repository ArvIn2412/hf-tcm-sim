# REPRO-06B — два приймачі на спільному спостереженні

Reference script: `scripts/run_repro06b_reference.py`. Він створює для кожного розміру незалежний deterministic seeded transmitter, один REPRO-03 static channel result з `d=[0,3]`, а потім окремо викликає REPRO-06B joint ISI-aware decoder і REPRO-04 separate hard/Hamming receiver. Обом передається той самий `ReceiverObservation`; SHA-256 порівнюється перед оцінюванням. Evaluation references записуються тільки після обох receiver calls.

Для `F=32`, `F=256`, `F=20000` число transmitter samples дорівнює `8F`, received samples — `8F+3`; обидва arms оцінюють однаковий payload і phase boundary. Три tail samples не стають окремим символом. Evaluation BER/SER позначено `single_frame_descriptive_only_not_statistical_evidence`.

У цих трьох безшумних project-defined static runs обидва декодери мали 0 bit/symbol errors. Це лише перевірка інтеграції для обраних коефіцієнтів і seed. Вона не демонструє перевагу joint receiver, не валідує fading/channel robustness і не є результатом статті. За шумового/переінтерпретованого каналу Hamming arm не враховує delayed ISI так, як joint arm.

Reference observation SHA-256 для F=20000: `8a1a86fd4cc6362e5b100ae3a1c157b122085da51b8bcbed0df2a266057cb958`. Повні конфігурації, hashes, NPZ, графіки й runtime знаходяться в `outputs/repro06b/reference_static_2path/`.
