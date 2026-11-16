# REPRO-01 — реєстр рівнянь

S1 — references/source_paper_2026.docx; візуально звірені друковані стор.4–7. Точна редакція v7 не підтверджена.

## A(1), стор.4
\[
\tilde\mu_{j,i+1}^{*(l)}=\alpha'\tilde\mu_{j,i}^{*(l)}+\tilde K_{\mu,j}^{(l)}
\sum_{\alpha=1}^{m}P_{i+1}^{(l)}(\theta_{i+1}^{(l),\alpha}\mid\bar\mu_{i+1}^{0(l)})
[U_{j,i+1}^{(l)}-U_{j,i+1}^{0(l)}(b_{i+1}^{(l)}(\theta_{i+1}^{(l),\alpha}))]
\]
та \(\mu_{j,i+1}^{*(l)}=\tilde\mu_{j,i+1}^{*(l)}+\mu_{j0}^{(l)}\), j=1,2; l=1…L. j — квадратура; i — індекс часу/символу; l — промінь; θ — кандидат прихованого стану; P — posterior; U/U⁰ — observation/prediction. Значення α′, K̃, μ₀, ініціалізація, prior, одиниці й alignment не задані повністю. Майбутні тести мають перевіряти нормування posterior, явний порядок кандидатів і незалежний oracle.

## A(2), стор.4 — SOURCE_UNRESOLVED
Скан показує:
\[
\theta^*_{r-\eta}=\operatorname{Arg\,min}_{\theta}F(r)=\operatorname{Arg\,min}_{\theta}
\sum_{f=r-\eta}^{r}\sum_{l=1}^{L}\sum_{i=i'^{(l)}}^{i''^{(l)}}
[\sum_{j=1}^{2}(U_{j,i}^{(l)}-U_{j,i}^{**, (l)}(\alpha))].
\]
У видимому джерелі немає квадрата, модуля, норми чи кореня. Literal signed residual sum допускає взаємне скорочення й не є автоматично distance. Euclidean norm має одиниці амплітуди; squared Euclidean — квадрат амплітуди й additive nonnegative cost. Наявний paper_metric.py використовує squared residual: це project reconstruction, не підтверджена author formula. Межі f=r−η…r містять η+1 індексів; словесна depth η може означати η переходів. Межі i′/i″ та sample alignment невизначені. Конфігурація повинна мати metric_profile та endpoint_profile; рекомендовано η transitions як project baseline, а η+1 як окрему sensitivity. Тестувати literal, Euclidean і squared варіанти окремо.

## A(3), стор.5
\(S(t_i)=A(t_i)\cos[\omega_0t_i+b(t_i)\Delta\varphi+\psi(t_i)]\). t — секунди, ω₀ — rad/s, b∈{0,…,7}, фаза — rad. Δφ=π/4 є фазовим приростом, не обов'язково абсолютною φ₀. Complex baseband не є RF carrier waveform.

## A(4), стор.5
\(Y(t_i)=\sum_{l=1}^{L}(U_{s,i}^{(l)}\sin\omega_0t_i+U_{c,i}^{(l)}\cos\omega_0t_i)+\xi(t_i)\). Дійсне спостереження — сума променевих квадратур і завади; нормування неповне.

## A(5), стор.5
\(U_s=\mu_1[-\sin(b\Delta\varphi)]\), \(U_c=\mu_2[\cos(b\Delta\varphi)]\). Структурно частково відповідає IQ prediction; точне phase labeling 16 переходів невідоме.

## A(6), стор.5
\(\mu_1=A(t-\tau_l)\mu_s\{-\sin[\psi(t-\tau_l)-\omega_0\tau_l]\}\);
\(\mu_2=A(t-\tau_l)\mu_c\{\cos[\psi(t-\tau_l)-\omega_0\tau_l]\}\).
τ — середня затримка відносно першого променя. Числові delay, time grid, law μs/c і initial state не наведені.

## A(7), стор.6
\(p_n\approx p_n^*=N_n/N\), p*=5·10⁻². Точне error event/denominator для BER/SER не встановлено; нова система має окремо рахувати bit та symbol errors.

## A(8), стор.6
\(\xi_i=\xi_{s,i}\sin(\omega_0t_i)+\xi_{c,i}\cos(\omega_0t_i)\). Компоненти названі zero-mean Gaussian, envelope — Rayleigh; variance/correlation неповні, це не автоматично complex AWGN.

## A(9), стор.6
\(\xi_{s,i+1}=\alpha_{фп}\xi_{s,i}+\sigma_{фп}\eta_{фп,s,i}\), аналогічно c. Innovation law/covariance/initialization не повністю встановлені. Наявні independent N(0,1) innovations та zero initialization — project choices.

## A(10), стор.6
\(\alpha_{фп}=\exp(-4/n)\), \(\sigma_{фп}=\sqrt{(2/n^2)[1-\exp(-8/n)]}\). n — samples per signal element, article n=8. Тестові властивості: n>0, 0<α<1, σ>0 та числова відповідність.

S4, друк.стор.126–129 (PDF 18–21), рис.4.5/4.6, табл.4.1/4.2 — інша модель. Її γ²=1, ε=0.001, L=1:2, delay assumptions та n=4 не переносити в S1.
