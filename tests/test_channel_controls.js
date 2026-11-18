'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {build} = require('../src/hf_tcm/studio/static/channel_controls.js');
const options = (extra = {}) => ({awgn: true, fading: 'rician', rays: 3,
  variance: 0.05, seed: 123, rho: 0.98, delays: [0, 3, 6],
  powers: [1, 0.25, 0.125], factors: [4, 1, 1], phases: [0, 0.7, 1.4],
  frontend: 'pilot_equalized', ...extra});

test('all 18 independent combinations serialize without changing fading when AWGN toggles', () => {
  for (const fading of ['none', 'rician', 'rayleigh']) for (const rays of [1, 2, 3]) {
    const input = options({fading, rays});
    for (const key of ['delays', 'powers', 'factors', 'phases']) input[key] = input[key].slice(0, rays);
    const on = build(input), off = build({...input, awgn: false});
    assert.equal(on.paths.length, rays);
    assert.deepEqual(on.paths, off.paths);
    assert.equal(off.noise_model, 'none');
    assert.equal(off.noise_complex_variance, 0);
    assert.equal(on.noise_complex_variance, 0.05);
    assert.deepEqual(build(input), on);
    assert.equal(on.fading_seed, 140);
    assert.equal(on.noise_seed, 141);
    if (fading === 'rayleigh') assert.ok(on.paths.every(p => p.k_factor === 0 && p.constant_coefficient === null));
    if (fading === 'none') assert.equal(on.fading_mode, 'constant');
  }
});

test('incompatible frontend, path arrays, noise and unsafe seeds are rejected', () => {
  for (const extra of [
    {frontend: 'awgn_direct_control'}, {frontend: 'oracle_csi'}, {rays: 4},
    {delays: [0, 3, 8]}, {delays: [0, 3, 3]}, {powers: [1]},
    {variance: 0}, {variance: NaN}, {rho: 1}, {seed: Number.MAX_SAFE_INTEGER},
  ]) assert.throws(() => build(options(extra)));
});
