# REPRO-02 — розмір, одиничне вимірювання та графіки

## Reference configuration

`configs/repro02/n_star_transmitter_only.json` задає 20,000 TCM symbol intervals за explicit project interpretation. Це не твердження, що статейне `N*` означає TCM-символи: REPRO-01 не усунув неоднозначність одиниці `N*`. Для цього запуску отримано 40,000 information bits, 20,000 input pairs, 60,000 coded bits і 160,000 комплексних відліків при 8 samples/symbol.

Configuration використовує чергувальний бітовий pattern, initial state 00, без termination, amplitude 1, `φ₀=0`, `Δφ=π/4`, ADR-002 project mapping. Жодна випадкова channel/noise реалізація тут не створюється.

## Вимірювання

Останній одиничний запуск записав у `outputs/repro02/reference_n_star/performance.json`: transmitter 0.1372 s, SVG plots 0.0771 s, numeric arrays 10,280,002 bytes. Це одна локальна transmitter-only вимірювальна точка, без статистичної інтерпретації і без BER/Monte Carlo висновків.

## Реальні plots

`plots.py` будує десять SVG безпосередньо з `TransmitterResult`: input bits, coded bits, encoder state history, edge sequence, phase indices, 8PSK constellation, phase versus symbol, symbol I, symbol Q, complex ZOH samples. Titles/axes українською, підписані одиниці/індекси та індекси символу/відліку. Доступні 20-symbol viewing window markers і selected-symbol markers. Це графіки лише передавача; plots каналу, приймача чи BER не створюються.

Масштабування та швидкодія майбутнього каналу не вимірювались. REPRO-03 має окремо перевірити пропускну здатність і пам'ять з урахуванням моделей променів та відліків.
