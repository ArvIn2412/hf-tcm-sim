'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {build} = require('../src/hf_tcm/studio/static/channel_controls.js');
const {buildMetricConfig, scenarioFor, payloadSymbols, referenceEbN0Db} = require('../src/hf_tcm/studio/static/metric_mode.js');

const input = (extra = {}) => ({comparisonMode: 'single', tract: 'known', metric: 'csi_weighted',
  awgn: true, variance: 0.05, fading: 'rician', rays: 2, rho: 0.9999, seed: 7, frameSymbols: 256,
  amplitude: 1, delays: [0, 3], powers: [0.8, 0.2], factors: [4, 1], phases: [0, 0.7],
  grid: '-3, 0, 3', trials: 5, target: 0.05, budget: 120, sweep: 'amplitude', bootstrap: 500, now: 1, ...extra});

test('known tract with weighted metric maps to the metric-study API', () => {
  const c = buildMetricConfig(input(), build);
  assert.equal(c.frontend_mode, 'known_channel');
  assert.equal(c.euclidean_metric, 'csi_weighted');
  assert.equal(c.scenario, 'rician');
  assert.deepEqual(c.energy_grid_db, [0]);
  assert.equal(c.trials_per_point, 1);
  assert.equal(c.channel_config.fading_mode, 'rician_ar1');
});

test('series mode uses the energy grid and pilot tract', () => {
  const c = buildMetricConfig(input({comparisonMode: 'series', tract: 'pilot', metric: 'unweighted'}), build);
  assert.equal(c.frontend_mode, 'pilot_equalized');
  // the grid is absolute Eb/N0; the API receives offsets from the base level of sigma^2
  const ref = referenceEbN0Db(256, 1, 0.05);
  c.energy_grid_db.forEach((offset, i) => assert.ok(Math.abs(offset + ref - [-3, 0, 3][i]) < 1e-9));
  assert.equal(c.trials_per_point, 5);
});

test('scenario mapping and validation', () => {
  assert.equal(scenarioFor('none', 1), 'awgn');
  assert.equal(scenarioFor('none', 2), 'static');
  assert.equal(scenarioFor('rayleigh', 1), 'rician');
  assert.throws(() => buildMetricConfig(input({frameSymbols: 100001}), build));
  assert.throws(() => buildMetricConfig(input({tract: 'x'}), build));
  assert.throws(() => buildMetricConfig(input({comparisonMode: 'series', grid: '1,1'}), build));
  assert.throws(() => buildMetricConfig(input({comparisonMode: 'series', sweep: 'noise', awgn: false}), build));
});

test('Q-function and QPSK reference agree with analytic values', () => {
  const {qFunction, qpskReferenceBer} = require('../src/hf_tcm/studio/static/metric_mode.js');
  assert.ok(Math.abs(qFunction(0) - 0.5) < 1e-7);
  assert.ok(Math.abs(qFunction(1.959963984540054) - 0.025) / 0.025 < 1e-5);
  // Python reference: qpsk_bit_error_probability(10**0.6) = 2.3883e-3; (10**0.96) = 9.736e-6
  assert.ok(Math.abs(qpskReferenceBer(6) - 2.3882e-3) / 2.3882e-3 < 2e-3);
  assert.ok(Math.abs(qpskReferenceBer(9.6) - 9.736e-6) / 9.736e-6 < 0.01);
});

test('Doppler model produces a rician_doppler channel and physical summary', () => {
  const {dopplerSummary, ITU_PRESETS} = require('../src/hf_tcm/studio/static/metric_mode.js');
  const c = buildMetricConfig(input({fadingModel: 'doppler', dopplerHz: 0.5, baud: 2400}), build);
  assert.equal(c.channel_config.fading_mode, 'rician_doppler');
  assert.equal(c.channel_config.correlation, 0);
  assert.equal(c.channel_config.doppler_spread_hz, 0.5);
  assert.equal(c.channel_config.symbol_rate_baud, 2400);
  assert.equal(c.scenario, 'rician');
  const ar1 = buildMetricConfig(input(), build);
  assert.equal(ar1.channel_config.fading_mode, 'rician_ar1');
  assert.ok(!('doppler_spread_hz' in ar1.channel_config));
  assert.throws(() => buildMetricConfig(input({fadingModel: 'doppler', dopplerHz: 0, baud: 2400}), build));
  const s = dopplerSummary(1.0, 2400);
  assert.ok(Math.abs(s.coherenceSeconds - Math.sqrt(Math.LN2 / (2 * Math.PI ** 2 * 0.25))) < 1e-12);
  assert.ok(s.rhoSymbol > 0.999999 && s.rhoSample > s.rhoSymbol);
  assert.deepEqual(ITU_PRESETS, {good: 0.1, moderate: 0.5, poor: 1.0, flutter: 10.0});
});

test('static channel ignores the Doppler option', () => {
  const c = build({awgn: true, fading: 'none', rays: 2, variance: 0.05, seed: 1, rho: 0.98,
    delays: [0, 3], powers: [1, 0.25], factors: [4, 1], phases: [0, 0.7], frontend: 'known_channel',
    doppler: {spreadHz: 1, baud: 2400}});
  assert.equal(c.fading_mode, 'constant');
});

test('reference Eb/N0 matches the study engine (pilot overhead counted)', () => {
  assert.equal(payloadSymbols(256), 224);          // 4 preamble + 7 bursts x 4
  assert.equal(payloadSymbols(20000), 17500);      // 4 + 624 x 4 pilots
  // saved study metric-known-*: N = 20000, sigma^2 = 0.05, offset 0 -> 19.611 dB
  assert.ok(Math.abs(referenceEbN0Db(20000, 1, 0.05) - 19.6115) < 1e-3);
});

test('long metric frames keep full arrays only for frame 0 of each point', () => {
  const long = buildMetricConfig(input({comparisonMode: 'series', frameSymbols: 50000, trials: 4, grid: '0, 4'}), build);
  assert.equal(long.full_array_stride, 4);
  const short = buildMetricConfig(input({comparisonMode: 'series', frameSymbols: 20000}), build);
  assert.equal(short.full_array_stride, undefined);
  assert.throws(() => buildMetricConfig(input({frameSymbols: 100001}), build), /100/);
  assert.throws(() => buildMetricConfig(input({comparisonMode: 'series', awgn: false, variance: 0}), build), /шум/);
});

test('default Eb/N0 grid follows the channel type', () => {
  const {defaultGrid, GRID_AWGN, GRID_FADING} = require('../src/hf_tcm/studio/static/metric_mode.js');
  assert.equal(defaultGrid('none'), GRID_AWGN);
  assert.equal(defaultGrid('rician'), GRID_FADING);
  assert.equal(defaultGrid('rayleigh'), GRID_FADING);
  assert.equal(GRID_FADING.split(',').map(Number).at(-1), 40);
});

test('clean samples left to the combiner by the path delays', () => {
  const {cleanSamples} = require('../src/hf_tcm/studio/static/metric_mode.js');
  // the user's run: delays 0,3,6 -> 2 of 8 samples, 6 dB lost
  const three = cleanSamples(['0', '3', '6'], 3);
  assert.equal(three.clean, 2);
  assert.ok(Math.abs(three.lossDb - 6.0206) < 1e-3);
  assert.equal(cleanSamples(['0', '3', '6'], 2).clean, 5);   // only the first two rays used
  assert.equal(cleanSamples(['0'], 1).lossDb, 0);
  assert.equal(cleanSamples(['0', '8'], 2).clean, 0);
});

test('series use common random numbers; a single run does not need them', () => {
  const series = buildMetricConfig(input({comparisonMode: 'series'}), build);
  assert.equal(series.common_random_numbers, true);
  const single = buildMetricConfig(input(), build);
  assert.equal(single.common_random_numbers, undefined);
});
