# HF-TCM-SIM: підсумковий науковий аудит GUI-UX-02

## 1. Загальна характеристика

HF-TCM-SIM — офлайнова академічна програма. Розробка SDR або керування БПЛА не входить до реалізації.

## 2. Мета й функції

Реальний передавач, дискретний канал, два основні приймачі, статичний B1, paired Monte Carlo, BER/SER, збереження й GUI.

## 3. Реалізовані алгоритми

Encoder A 2/3, 8PSK, ZOH, integer-delay multipath, Rician AR(1), complex AWGN, PSP Kalman/RLS, hard demodulation, Hamming/Euclidean Viterbi η=20. Математичні модулі не змінювалися.

## 4. Відповідність статті

PARTIAL. Див. ARTICLE_COMPLIANCE_FINAL_AUDIT.md: візуальні source формули, точні функції та тести. Назва методу сама по собі не доводить математичної тотожності.

## 5. Відповідність дисертації

PARTIAL. Наявна застаріла п’ятирозділова чернетка з адміністративними placeholders; офіційне затверджене завдання не знайдено. Див. MASTER_THESIS_READINESS_AUDIT.md.

## 6. Передавач і кодування

Незалежні 16 transition fixtures, нормування 8PSK і ZOH/index tests проходять у повному regression. Авторська phase labeling таблиця лишається невизначеною.

## 7. Модель КХ-каналу

Проєктний complex-baseband integer-delay профіль. Rician AR(1) не є доведеною повною фізичною HF Doppler-моделлю. iid AWGN не відтворює буквальну source-correlated noise recursion.

## 8. Joint receiver

Справжній causal survivor-specific PSP, ISI-aware augmented trellis. Це наближене спільне оцінювання, не глобальний unknown-channel ML. Формули оцінювача не буквальна реалізація джерела.

## 9. Separate B0/B1

B0 працює без multipath compensation. B1 використовує лише дозволені публічні статичні taps, не universal fading estimator. Main comparison — повні алгоритми, не ізольований ефект метрики.

## 10. Viterbi

Finite-depth η=20 має затримку 19 наступних переходів і явний flush. Локальний survivor path відокремлено від emitted decisions. Full-frame та short/exhaustive references перевірені regression tests.

## 11. Математичні й статистичні показники

BER і information-pair SER рахуються по тих самих payload bits; phase SER позначено окремо: Joint після декодування, B0 до нього. Trial-cluster bootstrap є exploratory при малій кількості trials.

## 12. GUI та UX-виправлення

Три колонки, українські підписи, чотири Tx/Rx I/Q, незалежні перемикачі на загальних графіках, фіксоване сузір’я 360×360, один заголовок, метадані й методика в діалогах. Видимі службові коди прибрано. Додано перемикачі BER-кривих. Залишкові обмеження: спеціалізовані графіки gain/phase/estimated/predicted trajectories не всі представлені в поточному workspace; повний UI verdict PARTIAL.

## 13. Контрольне моделювання

П’ять F=32 backend controls і свіжі GUI controls пройшли. Backend Monte Carlo: 2 noise levels × 5 independent pairs, 10/10. Повторний run перевірив resume без дублювання. GUI також завершив 10/10. Нижче — фактичні лічильники.

## 14. Енергоефективність

PHYSICAL_ENERGY_GAIN: NOT_ESTIMABLE. Sample variance та дискретна γ не фізичне Eb/N0. Потрібні sample period, pulse/matched-filter convention, PSD та спільні target-BER crossings. 1,5 дБ не відтворено.

## 15. Невідповідності

Надрукована метрика (2) проти squared norm; active estimator проти source recursion; iid шум проти correlated recursion; phase labeling та повні author channel parameters.

## 16. Критичні й некритичні обмеження

Критичні для article-exact/physical gain: нормалізація, формула метрики, source channel parameters. Для модельних порівнянь: межі B1, короткі trials, pilot uncertainty. GUI: деякі trajectory plots і повторне приймання останніх BER toggles не завершені.

## 17. Готовність до дослідів

EXPERIMENT_INFRASTRUCTURE_READY: READY_WITH_LIMITATIONS. SCIENTIFIC_COMPARISON_READY: READY_WITH_LIMITATIONS. ARTICLE_EXACT_REPRODUCTION_READY: NOT_READY. PHYSICAL_ENERGY_GAIN_READY: NOT_READY. Див. EXPERIMENT_READINESS_ASSESSMENT.md.

## 18. Подальші дії

План A–H із входами, змінами, бюджетом і completion criteria наведений у NEXT_SCIENTIFIC_STEPS.md. Основна серія не запускалася.

## 19. Рекомендації для дисертації

Відокремити source claims від model results, актуалізувати чернетку, погодити енергетичну нормалізацію до confirmatory study. Не називати нижчий BER за однієї variance фізичним енергетичним виграшем.

## 20. Загальний висновок

Перевірено працездатний модельний симулятор, проте GUI і відповідність статті залишаються PARTIAL. Для bounded exploratory дослідів інфраструктура придатна; фінальні фізичні та author-exact твердження не доведені.

| Контроль | Rx відліків | Joint bit errors | B0 bit errors | Joint pair SER | B0 pair SER | Observation SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| identity | 256 | 0/64 | 0/64 | 0 | 0 | 77368ccf45e4fe8e3defcd61f3233fba25b3bf027f6960ed98fbe0212fa0d50b |
| awgn | 256 | 0/64 | 0/64 | 0 | 0 | 2a70ec20300b5719198dc63e5e920e3b2554d66b5269042da9262f1f11ddfda7 |
| static_single_path | 256 | 0/64 | 0/64 | 0 | 0 | a6b854cfde14768b857ce8ff817a32e452014c2967e09b4510d9915e787aff46 |
| static_multipath | 259 | 0/64 | 0/64 | 0 | 0 | 26d616777f2a0ebdbeae109e1405aeaf40db17f16daf1ef4795678615a88928f |
| rician_ar1_multipath | 259 | 0/64 | 17/64 | 0 | 0.53125 | 40468aba2ee25c7416be9ac715fce96f6cb774a963059fc3640485233f9af636 |

## Фактичні перевірки

1182 pytest passed (64.65 s); targeted article audit: 109 passed; Ruff check/format src tests passed; Node syntax passed; 694/694 historical fingerprints; Edge QA 12/12 checks, 22 screenshots at 1366×768 and 1920×1080. Окремий повтор Edge після остаточних BER-toggle/color правок завис; він не зарахований.

Запуск: `python -m hf_tcm.repro.scientific_studio --port 18802 --no-browser`, адреса `http://127.0.0.1:18802/scientific`.
