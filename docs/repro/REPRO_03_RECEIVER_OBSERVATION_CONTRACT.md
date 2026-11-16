# REPRO-03 — контракт майбутнього приймача

```python
ReceiverObservation(
    received_samples, absolute_sample_index, sample_symbol_index,
    sample_local_index, samples_per_symbol, profile_id, model_id,
    sampling_convention, boundary_policy, output_length_policy,
    noise_model, noise_complex_variance,
)
```

Це єдине поле `ChannelResult`, яке слід передавати receiver A або B. Обидва трактати отримують один immutable buffer, однакові timing arrays і однакову public metadata; `ReceiverObservation.sha256` покриває dtype/shape/bytes усіх масивів і public metadata. `noise_complex_variance` є `None`, якщо його не оголошено приймачеві.

`EvaluationTruth` ізольований окремо: transmitter references, hidden coefficients, delays, contributions і generated noise. У receiver observation dataclass немає відповідних полів, це перевіряється тестами. `evaluation_truth.npz` не є входом receiver. Full output bundle містить evaluation data; майбутня реалізація receiver має приймати лише typed observation (або його receiver-only NPZ), ніколи не `ChannelResult`/truth sidecar.

У identity профілі однаковий serialized receiver input/hash можна подати обом майбутнім arms без повторного виконання каналу. REPRO-03 не реалізує жоден з receiver algorithms.
