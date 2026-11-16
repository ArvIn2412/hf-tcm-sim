# REPRO-03 — дискретний канал комплексної огинаючої

## Модель і походження

Канал працює з `TransmitterResult.tx_samples` — комплексними відліками baseband, а не з RF carrier/passband voltage. Дискретна проєктна модель:

\[
m_l[n]=n-d_l,\qquad
c_l[n]=\begin{cases}h_l[n]x[m_l[n]],&0\le m_l[n]<N_x,\\0,&\text{інакше},\end{cases}
\]
\[
y_{\rm sig}[n]=\sum_{l=1}^{L}c_l[n],\quad
r[n]=y_{\rm sig}[n]+w[n],\quad 0\le n<N_x+\max_l d_l.
\]

`n` і `d_l` мають одиниці абсолютних дискретних відліків; `N_x=len(tx_samples)`. Затримки тільки невід'ємні цілі відліки. Boundary policy — zero extension; довжина включає delayed tail. Дробові відліки, секунди, sample period, pulse shaping і RF carrier не інтерполюються й не моделюються.

REPRO-01 S1 A(4)/(6) структурно вказують багатопроменеву суму та затримані quadrature components; точні L, delay values, часовий grid, carrier projection і fading law не задані повністю. Rician, integer sample delays, complex-envelope convolution та числові profile values нижче — `[ПРОЄКТ]` реконструкція, не підтверджена фізична HF propagation model. S1 A(8)–A(10) — correlated real quadrature disturbance; у цьому етапі її не ототожнено з complex baseband AWGN.

## Код і профілі

- `channel_config.py`: strict `ChannelConfig` / `ChannelPathConfig`, schema `repro03-channel-v1`; profiles `identity_profile`, `single_path_rician_awgn_profile`, `multipath_rician_awgn_profile`, плюс `s1_structure_reconstruction_profile(...)` із обов'язковими caller-defined numeric parameters.
- `multipath_channel.py`: прямий kernel для `h_l[n]x[n-d_l]` і zero extension.
- `rician_fading.py`: незалежні path coefficients; використовує перевірений існуючий Rician generator з його явним контрактом.
- `noise.py`: окремий complex sample-domain circular Gaussian noise.
- `channel_runner.py`: `run_channel(transmitter_result, channel_config) -> ChannelResult`.
- `channel_result.py`: окремі `ReceiverObservation` та `EvaluationTruth`.
- `channel_io.py`: завантажує REPRO-02 NPZ лише після перевірки manifest/dtype/shape/SHA.
- `channel_serialization.py`, `channel_cli.py`, `channel_plot_adapter.py`: isolated artifacts, CLI і read-only SVG.

Three JSON profiles у `configs/repro03/`: identity control, one-path Rician+AWGN, two-path Rician+AWGN. Приклади використовують n=8 REPRO-02 sample alignment; single profile: `L=1`, `P=1`, `K=3`, `ρ=0.98`, `σc²=0.02`; multi profile: `(d,P,K,φ)=(0,1,4,0)` та `(3,0.25,1,0.7)`, `ρ=0.98`, `σc²=0.02`. Ці K/power/delay/noise/phase/correlation/seeds — engineering reconstruction values. `profile_id` робить їх версійованими; їх не можна цитувати як авторські.

## Модельний коефіцієнт і випадкові потоки

Для Rician profile:
\[
h_l[n]=\sqrt{P_l}\left(\sqrt{\frac{K_l}{K_l+1}}e^{j\phi_l}+\sqrt{\frac{1}{K_l+1}}g_l[n]\right),
\quad E|g_l|^2=1.
\]
Отже, K — відношення потужності LOS до diffuse power; очікувані складові дорівнюють `P_l K/(K+1)` та `P_l/(K+1)`, а `E|h_l|²=P_l`. `rician_static` тримає один випадковий коефіцієнт сталим на весь кадр. `rician_ar1` використовує стаціонарний комплексний Gaussian AR(1): `g[0]=z[0]`, `g[n]=ρg[n−1]+sqrt(1−ρ²)z[n]`, `z~CN(0,1)`. Для нього `E[g[n]g*[n−k]]=ρ^k`; це filtered-Gaussian approximation, не Jakes/Doppler.

Root `fading_seed` через `SeedSequence.spawn(L)` утворює окремий PCG64 stream на промінь. `noise_seed` задає окремий PCG64 незалежний stream. Manifest фіксує дочірні seeds, алгоритм, observation hash, `tx_samples` SHA-256 та information-bit SHA-256. Зміна noise seed не змінює coefficients і навпаки.

## Контракт, індексація та безпека

`ReceiverObservation` містить лише `received_samples`, absolute sample index, receive symbol index `n//8`, local index `n%8`, 8 samples/symbol та обмежені публічні model/noise metadata. Комплексний шумовий variance розкривається тільки за `reveal_noise_variance=true`. У ньому немає transmitter bits/symbols, fading coefficients, path contributions, delays або noise realization.

`EvaluationTruth` окремо містить переданий сигнал/bits/symbols, delays/power/K/LOS phases, `source_sample_indices`, coefficients `(L,N_out)`, contributions `(L,N_out)`, faded signal та generated noise. Тримати `ChannelResult` дозволено evaluator/visualizer; майбутньому receiver передавати тільки `result.receiver_observation`. `receiver_observation.npz` і `evaluation_truth.npz` зберігаються різними файлами; весь bundle є evaluation artifact і не повинен цілком передаватися receiver.

Вихідний закон `received=faded_signal+noise` перевіряється числово. Channel length дорівнює `N_x+max(delay)`, а transmitter відліки із затримками лишаються прив'язаними через `source_sample_indices`; tail має той самий absolute sample clock і коректний receive symbol/local index. Channel запускається тільки явним API/CLI викликом; імпорт нічого не рахує.

## Запуск

```powershell
python -m hf_tcm.repro.channel_cli --config configs/repro03/multipath_rician_awgn.json --transmitter-dir outputs/repro02/reference_n_star --output outputs/repro03/reference_n_star --print-summary
```

`--validate-only` не завантажує transmitter і не запускає channel. Результати пишуться тільки в `outputs/repro03/`. `paper_exact:false`, `receiver_enabled:false`; приймачів, BER/SER, SNR sweep і Monte Carlo немає.
