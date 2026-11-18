/* [ПРОЄКТ] UI configuration adapter; sampling remains in REPRO-03. */
(() => {
  'use strict';
  function build({awgn, fading, rays, variance, seed, rho, delays, powers, factors, phases, frontend, doppler = null}) {
    if (typeof awgn !== 'boolean' || !['none', 'rician', 'rayleigh'].includes(fading) || ![1, 2, 3].includes(rays))
      throw new Error('Некоректні параметри AWGN, завмирань або кількості променів.');
    if (!Number.isSafeInteger(seed) || seed < 0 || !Number.isSafeInteger(seed + 18))
      throw new Error('Seed має бути безпечним невід’ємним цілим числом.');
    if (!Number.isFinite(variance) || variance < 0 || (awgn && variance === 0))
      throw new Error('Для увімкненого AWGN потрібна додатна дисперсія шуму.');
    if (!Number.isFinite(rho) || rho < 0 || rho >= 1)
      throw new Error('Кореляція має бути в межах 0 ≤ ρ < 1.');
    if ([delays, powers, factors, phases].some(a => !Array.isArray(a) || a.length !== rays || a.some(v => !Number.isFinite(v))))
      throw new Error('Кількість значень параметрів кожного променя має відповідати вибраному L.');
    if (delays.some(d => !Number.isInteger(d) || d < 0 || d >= 8) || new Set(delays).size !== rays || delays[0] !== 0)
      throw new Error('Затримки: перший промінь 0, решта унікальні цілі 0…7 відліків.');
    if (powers.some(p => p <= 0) || factors.some(k => k < 0))
      throw new Error('Потужності мають бути додатними, K-фактори — невід’ємними.');
    if (frontend === 'awgn_direct_control' && (fading !== 'none' || rays !== 1))
      throw new Error('Прямий AWGN frontend підтримує лише один промінь без завмирань.');
    if (frontend === 'oracle_csi' && fading !== 'none')
      throw new Error('Oracle-CSI цього режиму підтримує лише статичний канал; для завмирань оберіть «Відомий тракт».');
    const coefficients = [[1, 0], [0.3, -0.2], [0.15, 0.1]];
    const dynamic = fading !== 'none';
    const useDoppler = dynamic && doppler !== null;
    if (useDoppler && !(Number.isFinite(doppler.spreadHz) && doppler.spreadHz > 0
      && Number.isFinite(doppler.baud) && doppler.baud > 0 && doppler.spreadHz < doppler.baud))
      throw new Error('Доплерівське розширення має бути додатним і меншим за символьну швидкість.');
    const config = {
      profile_id: dynamic ? 'rician_ar1_multipath' : rays === 1 ? 'awgn' : 'static_multipath',
      paths: delays.map((delay, i) => ({delay_samples: delay,
        average_power: dynamic ? powers[i] : coefficients[i][0] ** 2 + coefficients[i][1] ** 2,
        k_factor: dynamic && fading === 'rician' ? factors[i] : 0,
        los_phase_rad: dynamic ? phases[i] : 0,
        constant_coefficient: dynamic ? null : coefficients[i]})),
      fading_mode: dynamic ? 'rician_ar1' : 'constant', correlation: dynamic ? rho : 0,
      noise_model: awgn ? 'complex_awgn_sample_domain' : 'none',
      noise_complex_variance: awgn ? variance : 0,
      fading_seed: seed + 17, noise_seed: seed + 18, reveal_noise_variance: true,
      boundary_policy: 'zero_extension', output_length_policy: 'tx_plus_max_delay',
      rng_algorithm: 'numpy.PCG64', schema_version: 'repro03-channel-v1',
    };
    if (useDoppler) {
      config.profile_id = 'rician_doppler_multipath';
      config.fading_mode = 'rician_doppler';
      config.correlation = 0;
      config.doppler_spread_hz = doppler.spreadHz;
      config.symbol_rate_baud = doppler.baud;
    }
    return config;
  }
  function attach(form) {
    const $ = id => document.getElementById(id);
    const panel = document.createElement('div');
    panel.className = 'simulation-channel-controls';
    panel.innerHTML = '<label>AWGN<select id="channel-awgn"><option value="on">Увімкнено</option><option value="off">Вимкнено</option></select></label><label>Завмирання<select id="channel-fading"><option value="none">Немає</option><option value="rician">Rician</option><option value="rayleigh">Rayleigh (K=0)</option></select></label><label>Кількість променів<select id="channel-rays"><option>1</option><option>2</option><option>3</option></select></label>';
    form.prepend(panel);
    const arrays = {'model-delays': [0, 3, 6], 'model-powers': [1, 0.25, 0.125],
      'model-k': [4, 1, 1], 'model-los': [0, 0.7, 1.4]};
    function resize() {
      const count = Number($('channel-rays').value);
      for (const [id, defaults] of Object.entries(arrays)) {
        const current = $(id).value.split(',');
        $(id).value = defaults.slice(0, count).map((v, i) => current[i] ?? v).join(',');
      }
      $('model-delays').dispatchEvent(new Event('input'));
    }
    function legacy() {
      const scenario = $('mx-scenario').value;
      $('channel-fading').value = scenario === 'rician' ? 'rician' : 'none';
      $('channel-rays').value = ['awgn', 'awgn-pilot'].includes(scenario) ? '1' : '2';
      $('channel-awgn').value = Number($('mx-noise').value) > 0 ? 'on' : 'off';
      resize();
    }
    function sync() {
      const old = $('mx-scenario').value;
      $('mx-scenario').value = $('channel-fading').value !== 'none' ? 'rician'
        : $('channel-rays').value !== '1' ? (old === 'oracle' ? 'oracle' : 'static')
        : old === 'awgn-pilot' ? 'awgn-pilot' : 'awgn';
      $('mx-scenario').dispatchEvent(new Event('input', {bubbles: true}));
    }
    panel.addEventListener('change', () => { resize(); sync(); });
    $('mx-scenario').addEventListener('change', legacy);
    $('article-profile').addEventListener('change', () => {
      if ($('article-profile').value === 'article') legacy();
    });
    // Restore already persists all form controls, including the independent ones.
    $('restore-article').addEventListener('click', () => {
      const saved = JSON.parse(localStorage.getItem('hf-tcm-article-settings') || '{}');
      if (saved['channel-fading']) sync();
      else legacy();
    });
    legacy();
  }
  const api = {build, attach};
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof window !== 'undefined') window.channelControls = api;
})();
