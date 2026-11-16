# M4 — таблиця відповідності формул джерелам і коду

**Мета:** звірити доступні формули основної статті 2026 року з кодом M1–M3 та зафіксувати межі достовірності старіших джерел. Це аудит, не специфікація реалізації M4.

**Примітка щодо [A](2) / [B](20):** у доступному зображенні стор. 4 попередньої редакції [A] після залишку не видно показника `2`; так само його не видно після залишку на скані [B](20), друк. с. 11 (PDF p. 13). Повідомлення користувача вказує, що у в7 [A](2) теж показано без цього показника, але сам DOCX в7 ще не надано для незалежної перевірки. Тому буквальний запис відокремлено від реконструктивної інтерпретації squared-residual і фактичної реалізації M4.6; див. SCI-METRIC-02 у `M4_OPEN_QUESTIONS.md`.

## Доступність джерел

Основна стаття [A] доступна як `references/source_paper_2026.docx` і скани `references/key_pages/page-4.png`–`page-7.png`. Перевірені також оригінали [B] `references/Автореферат_1-1.pdf` та [C] `references/Раздел_4.pdf`. Для точного пошуку сторінок нижче вказано **друковану сторінку** та, у дужках, **номер PDF-сторінки** (рахунок від першої сторінки файла). Рівняння [B]/[C] підтверджують лише те, що надруковано в цих роботах; самі по собі вони не доводять, що [A] запозичує їхні параметри.

У таблиці «частково відповідає» означає структурну схожість або відповідність проєктному baseline, а не точне відтворення статті.

| Джерело / формула | Зміст і залежності | Поточний код | Відповідність та повнота позначень |
|---|---|---|---|
| [A], (1), с. 4 | Алгебраїчна рекурсія: α′ множить попередню флуктуючу оцінку; K̃ множить posterior-зважену суму U−U⁰; повна оцінка додає μ₀. Індекси у скані: α=1…m, j=1,2, l=1…L. | `receiver/paper_recursion.py:update_quadrature_estimates` реалізує окреме ядро з явними входами. | Exact algebraic recursion kernel, NOT complete paper-exact estimator. Знаки, індекси й порядок звірено за [A](1), с. 4, та [B](15), друк. с. 10 (PDF p. 12). Параметри, posterior, прогнози та initial state функція не визначає; SCI-03 OPEN. |
| [ПРОЄКТ] M4.4 — ядро рекурсії I/Q | Явні попередні флуктуючі оцінки, α′, K̃, posterior, спостережувані/передбачені I/Q та μ₀. | `receiver/paper_recursion.py`; модуль не підключений до likelihood, posterior, Viterbi чи pipeline. | Exact algebraic recursion kernel, NOT complete paper-exact estimator. Параметри та початковий стан лишаються явними входами; SCI-03 OPEN. |
| [ПРОЄКТ] M4.7h/B3a — snapshot state оцінювача | `fluctuating_iq: (L,2)` = флуктуюча `\(\widetilde{\mu}^{*}\)`; `full_iq: (L,2)` = повна `\(\mu^{*}\)`; `mu0` — окремий регулярний параметр; абсолютний integer `time_index`. `L≥1`, остання вісь `(I,Q)`. | `receiver/reconstruction_estimator_state.py::ReconstructionEstimatorState`; immutable snapshots, не викликає recursion, config loader, predictor чи pipeline. | Семантика звірена за видимими [A](1), с. 4, і [B](15), друк. с. 10 (PDF p. 12): `\(\mu^{*}=\widetilde{\mu}^{*}+\mu_0\)`. Форму `(L,2)` підтверджує фактичний `paper_recursion.py` batch API. Це project reconstruction state, NOT complete paper-exact estimator. |
| [ПРОЄКТ] M4.7i/B3b-0 — explicit-operand state step, `L=1` | State та `k_tilde`/`mu0` `(1,2)`; explicit `observed_iq (2,)`, `predicted_iq (M,2)`, `posterior (M,)`, `time_index=i`, `next_time_index=i+1`, scalar `alpha_prime`. | `receiver/reconstruction_estimator_step.py::advance_reconstruction_estimator_state()` додає batch axes, делегує `paper_recursion.update_quadrature_estimates()` і повертає immutable state `(1,2)` на `i+1`. | Ручні тести рахують [A](1) окремо від kernel; adapter не формує operands, не обчислює posterior/prediction і не читає channel output/truth. **Explicit-operand reconstruction state-step adapter, NOT paper-exact estimator.** Повний B3b blocked by per-path operand, posterior/prediction provenance, time/noise decisions. |
| [ПРОЄКТ] M4.7j/B3c-0 — explicit-operand sequential reconstruction estimator, `L=1` | Явний initial state `(1,2)` + послідовні step operands `time_index=i`, `next_time_index=i+1`, `alpha_prime`, `k_tilde`, `mu0`, `observed_iq (2,)`, `predicted_iq (M,2)`, `posterior (M,)`; optional history flag. | `receiver/reconstruction_estimator_sequence.py::run_reconstruction_estimator_sequence()` перевіряє типи/порядок через B3b-0 та делегує кожен крок `advance_reconstruction_estimator_state()`. | History, якщо запитана, — immutable tuple initial + all successor states з absolute labels. Кожен крок читає попередній `fluctuating_iq`; його `full_iq=next fluctuating_iq + this step's mu0`. **Explicit-operand sequential reconstruction estimator, NOT complete paper-exact estimator.** Не формує/отримує operands і не інтегрується з aggregate received, forward model, CLI/pipeline чи decoder. |
| [ПРОЄКТ] M4.7k/B3c-1 — one-path state-to-forward coefficient snapshot | `ReconstructionEstimatorState.full_iq (1,2)` + explicit matching `estimator_time_index`; distinct from `fluctuating_iq`. | `receiver/reconstruction_forward_snapshot.py::snapshot_full_iq_for_forward()` returns an immutable copy as `estimated_path_coefficients (1,2)` tagged with the estimator index. | Value/time-label adapter is isolated. It does not select a forward frame or establish physical equivalence to [A](6). ADR-012 later defines causal symbol availability; forward frame scheduling remains external. |
| [ПРОЄКТ] M4.7n/B3c-4 — causal one-path explicit-posterior reconstruction step | Aggregate complex `received`, explicit contiguous absolute sample labels, buffer origin, symbol origin `O`, absolute symbol `f`, explicit pre-observation estimator `time_index=i`, exact ADR-012 profile, and explicit `posterior (M,)`, `predicted_iq (M,2)`, their absolute sample cutoffs, `alpha_prime`, `k_tilde/mu0 (1,2)`. Observation is mean of `(-Im,Re)` over exactly `n=O+8f…O+8f+7`; one update after the final sample. | `receiver/reconstruction_observation.py::extract_adr012_observed_iq()` plus `receiver/reconstruction_causal_step.py::advance_real_one_path_symbol()`, delegating to `reconstruction_estimator_step.py` and then `snapshot_full_iq_for_forward()`. | Caller explicitly pairs estimator and symbol clock origins; no implicit `i=f` conversion. Step validates declared operand cutoffs do not exceed sample `O+8f+7`. Result step `i→i+1` is available after sample `O+8f+7`; copied snapshot uses `full_iq` and is eligible only for `f+1` or later. No future samples, truth, predictions/posterior generation, or forward/CLI integration. ADR-012 is a project assumption, not an [A]-confirmed observation algorithm. Noise covariance stays open. **Causal one-path explicit-posterior reconstruction step, NOT complete paper-exact receiver.** |
| [A], (2), с. 4 | Буквально видимий запис — сума за `f`, `l`, `i`, `j=1,2` від різниці `U−U**`; на доступному зображенні після залишку показника `2` не видно. У с. 6 наведено `η=20`. squared-residual — окрема реконструктивна математична інтерпретація, не буквальне відтворення видимого символу; авторське уточнення відкрите (SCI-METRIC-02). | `decoding/paper_metric.py::compute_paper_metric()` обчислює тільки scalar суму для однієї вже заданої траєкторії. M2 Viterbi лишається окремим алгоритмом. | **PROJECT interpretation kernel, NOT source-literal confirmation or integrated author receiver.** Реалізовано суму квадратів залишків, включні `f=r−η…r` і `i=i′[l]…i″[l]`; `η=20` дає 21 позицію. API приймає явні вирівняні I/Q, f/i labels і per-ray bounds; не додає нормування/ваг, не будує `U**` та не виконує `argmin`/traceback. |
| [ПРОЄКТ] M4.6 — незалежна сума критерію [A](2) | Одна явна траєкторія, `r`, `η`, точний `f_indices`, вкладені per-f/per-ray спостереження й прогнози `(N_l,2)`, labels `i` та включні per-ray bounds. | `src/hf_tcm/decoding/paper_metric.py::compute_paper_metric()` повертає scalar `F(r)`; використовує `math.fsum`. `N_l` може різнитися між променями. | `f` labels відповідають зовнішньому Python offset `f−(r−η)`; `i` label `i` відповідає рядку `i−i′[l]`; `j=1,2` відповідає останньому axis offset `0,1`. Фізичні sample-to-symbol перетворення не виконуються. | Реалізовано **exact algebraic metric kernel, NOT integrated author receiver**. Це не `argmin` за траєкторіями й не інтеграція з Viterbi. `U**`, labeling, per-path observations та SCI-02…04 лишаються невирішеними. |
| [A], (3)–(6), с. 5 | Passband модель 8PSK, `Δφ=π/4`, сума внесків `L` променів та I/Q коефіцієнти, залежні від амплітуди/фази, затримки `τ_l` і символу `b_i`. | `psk8.py` генерує точки з інтервалом `2π/8`; `multipath.py` складає затримані комплексні символи; `receiver/iq.py` — окреме наближення rectangular ZOH. Окремий `receiver/iq_prediction.py` реалізує лише алгебраїчне перетворення (5). | Фазовий крок `π/4` збігається з кроком constellation у коді. Нове ядро дослівно реалізує множники (5), але не моделі (3), (4), (6), затримки, оцінювання коефіцієнтів або повний receiver. Таблицю `b↔(C₂,C₁,C₀)` [A] доступні матеріали однозначно не встановлюють. |
| [ПРОЄКТ] M4.5b — перетворення I/Q за [A](5), с. 5 | Для явно заданого `b∈{0,…,7}` і двох коефіцієнтів променя: `U₁=μ₁·[-sin(bπ/4)]`, `U₂=μ₂·cos(bπ/4)`. | `src/hf_tcm/receiver/iq_prediction.py:iq_quadratures_from_index`; підтримує скалярний промінь або вектори індексів/коефіцієнтів однакової форми. | **Exact algebraic I/Q transform, NOT complete paper-exact prediction/receiver.** `b` не виводиться з `hypothesis_id` чи coded bits; коефіцієнти передаються явно. Модуль не читає `ChannelTruth`, не формує per-path спостереження та не інтегрується з estimator/pipeline. |
| [ПРОЄКТ] M4.7g/B2b-2 — isolated forward path | Candidate `(c2,c1,c0)` → accepted project labeling adapter → local [A](5) I/Q → 8-sample rectangular ZOH → explicit integer-delay/frame alignment with `zero_padding` → sum over paths. | `receiver/reconstruction_forward.py::predict_reconstructed_aggregate_iq`, composing `reconstruction_labeling.py`, `iq_prediction.py`, `reconstruction_alignment.py`, and `reconstruction_aggregate.py`. | **PROJECT RECONSTRUCTION forward model.** One explicit receiver-side `(μ₁,μ₂)` pair per path is held constant over the frame. The 8-sample ZOH, labeling, and aggregate baseband interpretation are project conventions; this does not establish [A](3)–(6) passband waveform, `U⁰=U**`, author `θ` correspondence, or a paper-exact receiver. No `ChannelTruth`, estimator, likelihood, posterior, or decoder is involved. |
| [A], породжувальна матриця, с. 5; схема, с. 6 | `G(x)=[[1,0,0],[0,1+x²,x]]`, швидкість `2/3`; схема задає прямий вихід і дві затримки другого входу. | `encoder.py`, `trellis.py`. | Структурний baseline узгоджується: чотири стани та вихід `(u0, u1 XOR u1[k−2], u1[k−1])`. Порядок індексів стану/бітів, labeling і межі кадру лишаються проєктними припущеннями SCI-02. |
| [ПРОЄКТ] M4.1 — простір структурних гіпотез | Для кожного з 4 станів і 4 пар входу задано одну гілку; поля — `current_state`, `input_bits`, `output_bits`, `next_state`, `hypothesis_id`. Це дає 16 гілок. | `coding/hypotheses.py` будує незмінну таблицю в порядку `build_trellis()` і перевіряє дозволеність конкретної трійки (стан, вхід, наступний стан). | Конвенція успадкована буквально від M1 `encoder.py`: стан `(u1[k−1],u1[k−2])`; вихід `(u0,u1 XOR u1[k−2],u1[k−1])`; наступний стан `(u1,u1[k−1])`. ID `0…15` — індекс рядка в порядку станів/входів trellis. Це 16 структурних state/input гіпотез, не 16 станів пам'яті; пам'ять має 4 стани. Таблиця й функція не задають імовірностей, posterior або відповідності індексації авторському `θ`. SCI-02/SCI-03 лишаються відкритими. |
| [ПРОЄКТ] M4.2 — матриця дозволів і Bayes update | Дозволений перехід між послідовними гіпотезами `i→j` структурний тоді й лише тоді, коли `next_state(i)=current_state(j)`. Один загальний крок має вигляд `p⁺_j ∝ L_j Σ_i p_i T_{ij}`. | `coding/posterior.py`: матриця `ALLOWED_HYPOTHESIS_TRANSITIONS` містить тільки 0/1; `posterior_update(initial_distribution, transition_matrix, likelihoods)` вимагає всі три масиви явно. | Рекурсія працює в log-space; перевіряє розмір і невід'ємність, нормований prior, рядково-стохастичну `T`, нульові значення на заборонених ребрах та ненульове evidence. Значення `T`, prior і likelihood не задаються модулем. Це інфраструктурна математична рекурсія, не доказ точної реалізації [B], (7), для 8PSK TCM і не реалізація estimator [A], (1). Не доводить відповідність `hypothesis_id` авторському `θ`; SCI-02/SCI-03 залишаються відкритими. |
| [ПРОЄКТ] M4.7o/B4a — reconstruction transition/prior/likelihood adapter | Канонічний простір — локальні 16 edge hypotheses у `HYPOTHESES` order. ADR-003: `T[h,k]=A[h,k]/d(h)` для фактичної структурної маски `A`; рядок `h` — previous edge, стовпець `k` — next edge. ADR-004 prior: `1/4` на `current_state=(0,0)`, інакше 0. ADR-005: relative `L_h∝exp(-beta*F_rx,h)`, explicit `beta>0`, `F_rx` aggregate project metric. | `receiver/reconstruction_posterior.py`: `build_reconstruction_transition_matrix()`, `build_initial_reconstruction_prior()`, `reconstruction_likelihood()`, `initial_reconstruction_observation_update()`, `transition_reconstruction_posterior()`. Transition-plus-emission delegates to `coding/posterior.posterior_update()`; first observation update is explicit no-transition multiply/normalize. | Degrees are counted from actual mask (currently 4 each, not hardcoded); order, support and row stochasticity are checked. Common log-shift preserves normalized weights; reachable support is used in posterior update to avoid all-zero evidence under large relative metrics. First edge prior belongs to the first edge; first observation does not transition and therefore does not skip an edge. Later update applies transition then emission at next edge. `F_rx` is not `[A](2)`/`paper_metric.py`; pseudo-likelihood is not author-exact/statistically proven. Permuted hypothesis ordering is explicit and equivariant. SCI-02/SCI-03/SCI-METRIC-02 remain open. **Isolated reconstruction posterior adapter, NOT author-exact posterior, NOT integrated adaptive receiver.** |
| [ПРОЄКТ] M4.3b — компонент показника [B](7) | [B], друк. с. 6 (PDF p. 8), у `exp{ C·Σ_k [Σ_{j=1}²(U_{j,k}−U⁰_{j,k}(θ^α))²]^{1/2} }` задає I/Q норму для кожного `k` і її суму; `k₁=n(f−1)+1`, верхня межа `i+1`. | `coding/likelihood.py::log_likelihood_component()` обчислює тільки `C·Σ_k hypot(r_I[k],r_Q[k])` з явно переданих масивів і `coefficient_c`. | У [B] перед `C` стоїть множення без явного мінуса; під формулою `C` названий відомим коефіцієнтом, але його значення і знак не визначено на перевіреній сторінці. Реалізація зберігає будь-який переданий знак і повертає лише log-компонент (показник експоненти), не `exp(·)`, не всю `V` і не posterior. Перевірки форми/скінченності та `hypot`/`fsum` забезпечують коректну чисельну область; еквівалентність Gaussian likelihood не заявляється. Інтеграції з M4.2, estimator і Viterbi немає. |
| [A], (9)–(10), с. 7 | Флуктуючі I/Q параметри мають рекурсію `ξ_{i+1}=α_fp ξ_i+σ_fp η_i`; `α_fp=exp(−4/n)`, `σ_fp=√(2/n²·(1−exp(−8/n)))`; `n` — число відліків на тривалість елемента сигналу `T`. | `channels/fluctuating_noise.py` обчислює коефіцієнти й генерує незалежні нормальні інновації I/Q за цією рекурсією. `awgn.py` лишається незалежним circular AWGN baseline; `rician.py` моделює інший процес. | Формули (9)–(10) реалізовані окремим процесом. Початкові значення стаття однозначно не задає; код явно обирає `ξ_I[0]=ξ_Q[0]=0` як проєктне припущення. Це не реалізує повний passband/channel model [A]. |
| [B], (7), друк. с. 6 (PDF p. 8) | Двостановий posterior для бінарної ОФМ: `P(θᵅᵢ₊₁|x⁰ᵢ₊₁)=V(ᵢ₊₁,θᵅᵢ)/Σᵦ₌₁²V(ᵢ₊₁,θᵦᵢ)`. `V` є добутком `exp{+C·Σ_k sqrt(Σ_{j=1}²(U_{j,k}−U⁰_{j,k}(θᵅ))²)}` та `Σ_{β=1}² π_{β,α}P(θᵝᵢ|μ⁰ᵢ)`. | `coding/likelihood.py` обчислює тільки показник `C·Σ_k sqrt(r_I[k]²+r_Q[k]²)`; `coding/posterior.py` лишається загальним Bayes update з явними likelihood/transition/prior. | PDF підтверджує додатний знак множення перед символом `C` в експоненті, але текст під формулою лише називає `C` відомим коефіцієнтом; знак і значення самого `C` не задані. M4.3b не обчислює `exp`, перехідний множник, prior, нормувальник `V` або posterior. [B](7) — двостановий OPM-приклад і не доводить likelihood для 8PSK TCM чи [A](1). Норма обчислюється окремо на кожен відлік до суми за `k`; Gaussian еквівалентність не встановлена. |
| [B], (15), друк. с. 10 (PDF p. 12) | Та сама рекурсивна структура: α′ μ̃ плюс K̃ на posterior-зважену суму U−U⁰, далі μ̃+μ₀. Верхня межа суми надрукована як мала m. | `receiver/paper_recursion.py` відтворює алгебраїчну операцію з явними параметрами. | [B](15) підтверджує структуру, не визначає невідомі параметри, гіпотезне відображення чи алгоритм прогнозу для [A]. |
| [B], (16)–(19), друк. с. 10–11 (PDF pp. 12–13) | (16) перемикає `K`/`K′` за порогом `A_{j,i+1}`; (17) формує віконне усереднення довжини `Z`; (18) визначає posterior-зважену інновацію; (19) фіксує її на межах інтервалів `n·f`. | В M1–M3 перемикача та обчислення цих кумулянтів немає. | Первинний [B] підтверджує визначення свого квазістаціонарного `K̃`. У [A], (1), `K̃` названо квазістаціонарним кумулянтом, але на доступних с. 4–7 немає формул (16)–(19), `Z` чи порога. Тому конкретний перемикач [B] — підтверджена формула [B], але його застосування в [A] не доведено цими сторінками. |
| [B], (20), друк. с. 11 (PDF p. 13), проти [A], (2), с. 4 | Обидві формули мають однакову структуру мінімізації накопиченого залишку за вікном `η`, променями та відліками. У доступному скані [B](20), як і на зображенні [A](2), показник `2` після залишку візуально не читається. Квадрат залишку залишається реконструктивною інтерпретацією, а не підтвердженим буквальним записом цих сканів. | `paper_metric.py` реалізує лише незалежне scalar сумування квадратів залишків за прийнятою реконструктивною інтерпретацією; M2 Viterbi не змінений. | Візуально підтверджена структурна аналогія формул, але не явний квадрат в їх доступному записі. Уточнення задуму автора та високоякісного оригіналу формул відкрите в SCI-METRIC-02; це не доводить однакових prediction/trajectory mappings і не означає інтеграції kernel з M2 decoder. |
| [B], визначення `M` після (15), друк. с. 10 (PDF p. 12) та узагальнення на друк. с. 11 (PDF p. 13); [A], пояснення до (1), с. 4 | `M=2^(ν+k)` — число станів дискретного параметра `θ`; [B] описує `θ` як залежний від інформаційних символів і стану кодера. | `trellis.py` має 4 стани пам'яті, що кодують два memory bits. | `M` і 4 — **різні множини/поняття**: чотири — стани пам'яті кодера; `M` — гіпотези дискретного параметра, що також враховують інформаційні символи. За `ν=2` (два елементи пам'яті) і `k=2` (два інформаційні входи) формула дає `M=16`, не 4. Якщо авторське `ν` означає constraint length 3, тоді `M=32`; [A] не пояснює цю конвенцію досить однозначно, тому числове значення лишається умовним. |
| [C], (4.9)–(4.10), друк. с. 113 (PDF p. 5), проти [A], (9)–(10), с. 7 | Обидва задають AR(1) рекурсії для квадратурних компонент additive disturbance. Обидва друкують `α=exp(−4/n)`. У [C] `σ=√(2/h̄²·(1−exp(−8/n)))`, `h̄²` визначено як signal/noise ratio, за умови `P̄_s=1`; в [A] `σ=√(2/n²·(1−exp(−8/n)))`. | `fluctuating_noise.py` реалізує [A] формулу окремо; `awgn.py` залишається baseline. Формула [C] не використана. | **Підтверджений збіг лише коефіцієнта `α`; нормалізації `σ` різні.** Вони рівні алгебраїчно лише за `h̄²=n²`; такого зв'язку джерела не встановлюють. Не переносити σ з [C] до реалізованого [A] профілю. |
| [C], (4.19)–(4.22), друк. с. 116 (PDF p. 8) | Задають fading-параметри: `α_μ=exp(−ε_μ/n)`, `σ_μ^(l)=σ_{0μ}^(l)√(1−exp(−2ε_μ/n))`; regular amplitude `A₀^(l)=√(2γ_l²σ_{0μ}^(l)²)`, її I/Q розклад через `φ₀^(l)` та `σ_{0μ}^(l)²=β_l²/(1+γ_l²)`. | `rician.py` задає свій Rician K/power/phase та optional approximate AR(1). | Це математично визначена модель [C], але [A] на с. 4–7 не задає `ε_μ`, `β_l`, `γ_l`, `φ₀` або рівняння (4.19)–(4.22). Наявність у [A] fluctuating/regular coefficient components — лише змістова подібність; числову чи формульну відповідність не доведено. Не використовувати [C] для заповнення невідомих параметрів [A]. |
| [C], табл. 4.1, друк. с. 127 (PDF p. 19) | Для таблиці коду 1 стовпці `C₂,C₁,C₀,B` дотримуються `B=4C₂+2C₁+C₀`. Напр., рядок `X₀=0,X₁=1`, пам'ять `00` друкує `C₂C₁C₀=011`, `B=3`. | M1 використовує natural-binary `m=4c₂+2c₁+c₀` як явно проєктний baseline. | Таблиця підтверджує цю арифметику маркування **в [C]**, але не доводить, що [A] явно приймає її. Крім того, [C] p. 126, рис. 4.5a й `G₁` показують delayed `C₀`, тоді як p. 127 таблиця для того ж входу й memory `00` друкує `011`; це суперечить буквальному pre-shift читанню рисунка/матриці, яке дає `010`. Рядок не є достатнім доказом часової конвенції [A]. |
| [D], стаття 2023 року, за аудитом | Контекст радіолінії; аудит не знаходить означень потрібної рекурсії, posterior TCM або таблиці згорткового кодера. | Не використовується. | Файл [D] відсутній, тому твердження аудиту не перевірено за [D]. Не використовувати його як підтвердження M4 без безпосередньої звірки. |

## Підсумок коду

M1–M3 містять відтворювані проєктні baselines: генератор коду з чотиристанною решіткою, natural-binary 8PSK labeling, звичайний hard/soft Viterbi, AWGN, конфігурований приблизний multipath/Rician канал і rectangular 8-відліковий waveform helper. Коду adaptive recursion / posterior estimator / adaptive metric з [A], (1)–(2) немає; M1–M3 не заявляються paper-exact. Пряме зіставлення [B]/[C] уточнило структурні збіги, але не довело перенесення їхніх posterior-матриць, порогів кумулянтів чи fading-параметрів у [A].

M4 містить окремі математичні ядра з явними входами: posterior-інфраструктуру, рекурсію [A](1), exact algebraic I/Q transform [A](5) і exact algebraic metric kernel [A](2). Вони не утворюють інтегрованого author receiver: `b↔output_bits`, `U**`, оцінки коефіцієнтів і per-path спостереження лишаються невизначеними за SCI-02…04.

| [PROJECT] M4.7p/B4b ? isolated causal candidate metrics | For each of 16 local edges `h`, take `output_bits(h)`, map them with the explicit assumed natural-binary adapter to `b_h`, form the pre-observation forward prediction `Yhat_h[k]` for the target symbol's 8 sample labels using `state.full_iq`, and compute `F_rx,h = sum_{k=0..7} sum_{j=1..2} (Y_j[k]-Yhat_j[h,k])^2`. `Y[k]=(-Im(received[n_k]), Re(received[n_k]))` under accepted ADR-012. | `receiver/reconstruction_candidate_metrics.py::generate_reconstruction_candidate_metrics()` reuses `HYPOTHESES`, `hypothesis_to_phase_index()`, `predict_reconstructed_aggregate_iq()`, `extract_adr012_observed_iq_samples()`, and `compute_project_reconstruction_metric()`. | Immutable `candidate_metrics (16,)` follows the explicit hypothesis ID order, canonical by default as in B4a. Prediction cutoff is the sample before the target window; metric is available after its eighth sample. This aggregate eight-sample project metric is not [A](2), `paper_metric.py`, a likelihood, or a paper-exact metric. The vector is an emission operand for B4a, not a complete sequence decoder. `paper_exact:false`, `receiver_enabled:false`; SCI-METRIC-02 remains open. |

| [PROJECT] M4.7q/B4c ? isolated causal single-path posterior-estimator step | For current edge `t`, first edge: `p_t(h) ? p_init(h) exp(-?F_rx,t(h))`, with no transition. Later edge: `q_t(k)=sum_h p_{t-1}(h)T[h,k]`, then `p_t(k) ? q_t(k) exp(-?F_rx,t(k))`. Candidate recursion operands are `Yhat_t(h)=iq_quadratures_from_index(b_h, pre_state.full_iq[0,0], pre_state.full_iq[0,1])`, `Ybar_t=mean_{n=O+8f..O+8f+7}(-Im(received[n]),Re(received[n]))`; the existing [A](1) kernel receives current `p_t`, `Yhat_t (16,2)`, and `Ybar_t (2,)`. | `receiver/reconstruction_posterior_estimator_step.py::process_reconstruction_posterior_estimator_step()` calls B4b, one of the two B4a posterior functions, `iq_prediction.py`, and `reconstruction_causal_step.py`; [A](1) remains delegated to `paper_recursion.py`. It verifies row order and that each recursion prediction repeats to the B4b `(16,8,2)` predictions under ZOH. | Exact explicit cutoffs: prediction data through `O+8f-1`; current observation/metric/posterior through `O+8f+7`; successor state tick `i+1` usable at `f+1` or later. `i` and `f` are independently supplied. Project assumptions only; no current-symbol posterior leaks into its own predictions. Does not decode bits or autonomously process a sequence. **Isolated causal single-path reconstruction posterior-estimator step, NOT paper-exact receiver, NOT decoded-bit output.** |

| [PROJECT] M4.7r/B4d ? causal sequence scheduler | For consecutive absolute symbols `f_k=f_0+k`, sample labels are `n=O+8f_k+r`, `r=0..7`; estimator labels are independently `i_k=i_0+k`. Each step consumes the previous step's posterior/state. New-run first edge applies initial prior ? emission without transition; continuation first edge and all later edges apply one transition then current emission. | `receiver/reconstruction_posterior_estimator_sequence.py::run_reconstruction_posterior_estimator_sequence()` calls B4c for each symbol and passes only the current available received prefix. | Requires exact contiguous `8N` sample buffer starting `O+8f_0`, explicit symbol schedule and initial `(f_0,i_0)` pair. Prediction cutoff `O+8f-1`; observation/posterior/update cutoff `O+8f+7`; returned state usable from `f+1`. New independent sequence vs continuation are distinct; frame boundaries do not reset. Split-run equivalence is tested. One continuous-run project scheduler only; no frame-constant forward scheduling, decoded bits, or paper-exact claim. |

## M4.7s/B5a — trellis/path traceability

| Contract item | Implemented source | Traceability / limit |
|---|---|---|
| Four states, input pairs, output triples, successor state | `coding/encoder.py::encode_step`, `coding/trellis.py::build_trellis` | M1 source-faithful encoder transition. |
| Canonical 16 edges and IDs | `coding/hypotheses.py::HYPOTHESES` | Built directly from M1 trellis order; ID is row metadata, not article phase. |
| Edge-to-phase label | `receiver/reconstruction_labeling.py::hypothesis_to_phase_index` | ADR-002 project assumption uses edge `output_bits`; does not establish paper labeling. |
| Structural edge adjacency | `coding/posterior.py::ALLOWED_HYPOTHESIS_TRANSITIONS` | 0/1 support: previous edge row to next edge column. |
| Edge transition probabilities | `receiver/reconstruction_posterior.py::build_reconstruction_transition_matrix` | ADR-003 row-stochastic model, distinct from the structural mask. |
| B4b local metrics | `receiver/reconstruction_candidate_metrics.py::generate_reconstruction_candidate_metrics` | Causal aggregate eight-sample squared residual; depends on pre-observation estimator state. Not [A](2). |
| B4a posterior | `receiver/reconstruction_posterior.py` | Normalized reconstruction pseudo-posterior; history-dependent and not an additive path cost. |
| Explicit edge path validation | `coding/hypothesis_path.py::validate_hypothesis_edge_path` | Checks only initial edge state and pairwise trellis adjacency; no decoder/search. |
| [A](2) metric | `decoding/paper_metric.py` | Separate author formula implementation; SCI-METRIC-02 remains open and this phase makes no changes. |

## M4.7t/B5b — conditional full-trellis dynamic program

For state `s`, row/time `t`, and canonical edge `h`, the decoder uses `D_before((0,0))=0`, other initial states `+∞`, and

`candidate(t,h) = D_previous(h.current_state) + candidate_metrics[t,h]`

It retains the least candidate for `h.next_state`. On exact equality it keeps the lowest hypothesis ID. After F rows it selects the reachable state minimizing `(cumulative_cost, canonical_state_index)`, then traces the stored predecessor edge IDs backward. It recomputes the selected path's sequential cumulative sum and validates adjacency through `validate_hypothesis_edge_path()`.

| Contract item | Implemented source | Traceability / limit |
|---|---|---|
| Frozen branch-cost matrix | `decoding/reconstruction_viterbi.py::_validated_costs` | Requires finite nonnegative `(F,16)` real values; does not generate costs or normalize them. |
| Survivor recursion and ties | `decoding/reconstruction_viterbi.py::decode_reconstruction_viterbi` | Uses canonical M1 `STATES` and `HYPOTHESES`; exact numeric equality, minimum edge ID for same-state tie. |
| Final-state selection | Same | Free reachable final state; exact tie by minimum canonical state index; no tails or forced termination. |
| Full traceback and bits | Same plus `coding/hypothesis_path.py` | Returns edge IDs, `(F,2)` input pairs, `(2F,)` information bits, `(F+1)` states, and `(F,4)` diagnostics. |
| Time provenance | Same | Requires separate consecutive edge, absolute-symbol, and estimator-time labels; no equality or mapping is inferred. |

The DP is exact for the sum of frozen B4b rows, conditional on the causal estimator history that generated those rows. It is not a joint channel-estimator trajectory optimum, B4a posterior recursion, or [A](2) implementation. ADR-013 is accepted as project policy; ADR-009/011 remain proposed. `paper_exact:false`, `receiver_enabled:false`, and SCI-METRIC-02 remain unchanged/open.

## M4.7u/B5c — end-to-end frozen metric provenance

| Stage | Operands / output | Equation and cutoff trace |
|---|---|---|
| B4b candidate metrics | For each symbol, exact B4c `candidate_result.metrics (16,)` from immutable B4d history | `F_rx,h = Σ[k=0..7]Σ[j=1..2](Y_j[k]-Ŷ_j[h,k])²`; pre-state prediction cutoff `O+8f-1`, metric available at `O+8f+7`. |
| B4a posterior | Current edge posterior from first-edge prior or previous posterior, current metrics, explicit beta | First edge: initial prior × current emission with no transition. Later edge: one accepted transition then current emission. This is not B5b cost. |
| [A](1) estimate | Current posterior, explicit observed mean-of-eight I/Q, predictions, `alpha_prime`, `K_tilde`, `mu0` | Updates state `i→i+1` after the last target sample; next state only available to subsequent symbols. |
| B5b conditional path | Frozen history rows stacked as `candidate_metrics (F,16)` | Full four-state DP minimizes the sum along a valid path, once after B4d completes. It uses no estimator update and no posterior as branch cost. |

The integration copies the candidate metric arrays from B4d's retained B4c
history and validates row-to-symbol, estimator-time, sample-window, cutoff,
profile, and canonical hypothesis-order provenance. The frozen matrix is not
recomputed from the final estimate. `[A](2)` remains separate and
SCI-METRIC-02 remains open.

## M4.7v/B5d — segmented causal pass and frozen conditional decode

| Stage | Segmented execution | Invariant |
|---|---|---|
| Segment sample window | Segment `s` contains `8*N_s` samples at explicit buffer offset `q_s`; its first absolute symbol is `f_s`. | `q_0=0`; `q_(s+1)=q_s+8*N_s`; `f_(s+1)=f_s+N_s`; complete labels are contiguous. |
| B4d start/continuation | First segment: initial prior and first likelihood without transition. Later segments: previous posterior, one transition, and previous final estimator state. | Initial prior occurs once, at the first symbol of the independent sequence. Segment boundaries do not reset state, posterior, or trellis. |
| Per-symbol prediction and observation | For absolute symbol `f`, prediction cutoff `O+8f-1`; observed window `O+8f…O+8f+7`. | Current metric/posterior/update available only after `O+8f+7`; updated state applies from `f+1`. |
| Frozen metric/posterior history | Exact B4c values from each segment's B4d history, joined by sequence position. | Metric matrix and posterior history each have shape `(F,16)` and canonical hypothesis order; no post-pass recomputation. |
| Final B5b | One full four-state Viterbi call after the last segment. | One independent sequence, initial state `(0,0)`, free final state, no tail bits, full traceback. |

Monolithic/segmented equivalence is asserted in deterministic tests for the
listed partitions. This checks continuation composition; it does not assert
general frame-constant channel equivalence or joint optimization over unknown
channel trajectories. B4b costs, B4a posterior, [A](1), B5b cumulative path
cost, and [A](2) retain distinct meanings.

## M5a — post-decode error measurement

For reference/decoded information sequences of equal length `2F`, the
evaluation layer counts unequal input bits and divides by `2F` for BER. For
reference/decoded coded-symbol index sequences of equal length `F`, it counts
unequal ADR-002 indices derived from M1 output triples and divides by `F` for
coded-symbol SER. It never compares three coded output bits against information
bits, uses hypothesis IDs as phases, trims lengths, or counts edge mismatches as
SER. For pooled runs, each raw numerator and denominator is summed before
division. These are measurement definitions, not receiver branch costs or
paper metric [A](2). No performance experiment is claimed.

## M6a trace provenance note

The M6a evaluation adapter copies the operands and outputs returned by the
actual B4d/B4c sequence for each symbol. The [A](1) innovation is not exposed
as a named B4c result field; the trace derives its weighted residual from the
returned posterior, observed-IQ mean, and predicted-IQ operands without
reapplying the update. The intermediate transition prediction before the
current likelihood is also not returned and remains unavailable. Thus the
trace can check the implementation algebra and lifecycle but cannot resolve
the scientific meaning of [A](1), SCI-03, or source-paper fidelity.

## M6c — independent [A](1)/(5) and quadrature-convention audit

M6c checked original scans `references/key_pages/page-4.png` and
`page-5.png` (printed pp. 4–5) against independent scalar controls and actual
API. [A](5), p. 5, prints `U_s=μ_1[-sin(b Δφ)]`,
`U_c=μ_2[cos(b Δφ)]`, with `Δφ=π/4`; `iq_prediction.py` matches signs and
component order for all eight `b` values and unequal, zero, and negative
coefficient controls. This is **ALGEBRA_MATCH** for explicit `b, μ1, μ2` only.

ADR-012's `(-Im(y),Re(y))` is algebraically `(-a sin θ,a cos θ)` for the
selected `y=a exp(jθ)` convention. This does not establish that [A] defines
that complex envelope, quadrature axes, time origin, or sample mean. ADR-012
remains a project assumption, not an author mapping.

[A](1), p. 4, contains the posterior-weighted residual sum
`Σ_α P_{i+1}(…)[U_{j,i+1}-U^0_{j,i+1}(…)]`. The explicit update kernel applies
`α′` to prior fluctuating state, `K̃` to the weighted residual sum, and adds
`μ0` only to form the full estimate. An independent scalar-loop fixture
matched `paper_recursion.py`. For normalized `p_h` and common observation
`Y`, `Σ p_h(Y-U_h)=Y-Σ p_h U_h`; the literal 16-entry loop confirms it.
B4c exposes posterior, prediction, and observation operands, but not
transition-predicted `q`; M6b's weighted innovation is derived, not a raw
B4c field.

The canonical 16 M1 edges and ADR-002 natural-binary phase indices were
checked using a literal independent table. [A] defines `b∈0…7` but the audited
pages do not provide a verified `edge/θ ↔ b` table. Author mapping is
**SOURCE_UNRESOLVED**; the implementation table is **RECONSTRUCTION_ONLY**.
See `M6_SOURCE_EQUATION_ALGEBRA_AUDIT.md` for transcription, operand matrix,
tests, and hypothesis status. SCI-02, SCI-03, and SCI-METRIC-02 remain open;
receiver mathematics is unchanged.

## M6d — source-evidence audit and clarification gate

The local article [A] is identified as `references/source_paper_2026.docx`
(SHA-256 and page-scan hashes are recorded in
`M6_AUTHOR_MAPPING_EVIDENCE_AUDIT.md` and
`configs/m6d_source_evidence_matrix.json`). Readable scans pp. 4–7 were
visually checked. DOCX text/structure was inspected; embedded equations are
not all text-extractable and page scans pp. 1–3 are absent, so visual-only
content on pp. 1–3 is marked SOURCE_UNAVAILABLE.

[A](3)/(5), printed p. 5, explicitly defines `b` in 0…7 and its additive
phase increment `bπ/4`, along with `U_s=-μ_1 sin(bπ/4)` and
`U_c=μ_2 cos(bπ/4)`. Figures 2–3 on p. 6 show `X₀/X₁`, `C₂/C₁/C₀` and a
four-node trellis, but do not provide an adequate complete 16-transition
legend/table linking state/input/output tuple to `b`. Natural-binary ADR-002
therefore remains project-only. `[C]` table 4.1 and `[B](15)` are
EXTERNAL_REFERENCE_ONLY; they are not imported into [A].

Source [A](4)/(5) names sine and cosine passband components but does not define
an equivalent complex-baseband I/Q convention. The source states 8 samples per
signal element (p. 6) and defines `n` over duration `T` (p. 7); it does not
establish rectangular ZOH, symbol/sample origin, B4d's eight-sample mean, or
its causal cutoff. [A](1) gives the explicit algebraic update structure;
`U⁰` is described from prior estimates and a discrete state, while [A](2)
uses `U**` in the decoder metric. No equality or conversion between them is
stated in the audited text.

Verdicts: author edge-to-`b` mapping is
`AUTHOR_MAPPING_NOT_IDENTIFIABLE_FROM_AVAILABLE_SOURCE_EVIDENCE`; `b` to its
phase increment is SOURCE_DERIVABLE; full author complex-I/Q and clock
conventions remain SOURCE_UNRESOLVED. The ready-to-send clarification is
`M6_AUTHOR_CLARIFICATION_REQUEST.md`; no message was sent and no author reply
is recorded. No ADR was accepted and no receiver/config/output was changed.
