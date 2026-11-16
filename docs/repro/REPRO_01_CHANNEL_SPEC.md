# REPRO-01 — вимоги до каналу

S1 (3)–(6),(8)–(10) задають passband signal, суму L ray quadratures, phase projection, delayed coefficients і рекурсивну quadrature disturbance. Rayleigh fading згадується, але один Rician coefficient не відтворює повну модель.

|Параметр|Джерельний стан|Наявний модуль|
|---|---|---|
|L rays|L є у (4),(6); точна кількість не встановлена|multipath.py структурно корисний, reconstructed|
|τ_l|середня затримка відносно першого променя; значень/time grid немає|integer sample delay — reconstructed|
|μ_s, μ_c|Rayleigh згадано; joint law/normalization неповні|rician.py approximate K/LOS, reconstructed|
|Noise (8),(9)|Gaussian quadratures, correlated/quasi-harmonic опис|fluctuating_noise.py partial; innovations/init — проєктні|
|α,σ (10)|явна формула, n=8|алгебра коефіцієнтів source-match|
|SNR/energy|нормування не повне|awgn.py — project Eb/N0, не source match|
|RNG/seeds|не визначені|явний Generator є extension|

ARTICLE_FORMULA_PROFILE має вимагати невідомі параметри, не вигадувати article defaults. PROJECT_RECONSTRUCTION_PROFILE дозволяє запуск з названими values, provenance та sensitivity. Channel і noise генеруються один раз на пару приймачів; truth sidecar недоступний receiver API.

Майбутній RNG контракт: deterministic labeled streams для bits/fading/disturbance; зберігати алгоритм, версію, seeds і draw order. S4 залишається окремим профілем.
