'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const r = require('../src/hf_tcm/studio/static/exp04_results.js');

const bundle = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'research', 'SCIENTIFIC_EXP_04_RESULTS.json'), 'utf8'));
const cell = id => bundle.cells.find(c => c.id === id);

test('uncoded QPSK reference matches the Python theory curve', () => {
  assert.ok(Math.abs(r.qpskBer(4.32319) - 0.01) < 1e-6);
  assert.ok(Math.abs(r.qpskRequiredDb(1e-3) - 6.7895) < 1e-3);
  assert.ok(Math.abs(r.qFunction(0) - 0.5) < 1e-7);
});

test('BER labels use Ukrainian superscript notation', () => {
  assert.equal(r.berLabel(0.05), '5·10⁻²');
  assert.equal(r.berLabel(0.01), '10⁻²');
  assert.equal(r.berLabel(0.001), '10⁻³');
});

test('rows derive BER from stored error counts', () => {
  const rows = r.cellRows(cell('A1-awgn'));
  assert.equal(rows.length, 19);
  const p = cell('A1-awgn').points[0];
  assert.equal(rows[0].hamming, p.hamming_errors / p.bits);
});

test('gain summary marks the primary target and verdict', () => {
  const g = r.gainSummary(cell('A1-awgn'), 0.001);
  assert.equal(g.primary, true);
  assert.equal(g.verdict, 'PRECISION_CRITERIA_MET');
  assert.ok(g.positive);
  assert.match(g.text, /^5,51 дБ$/);
  const weak = r.gainSummary(cell('A3-itu-moderate'), 0.001);
  assert.equal(weak.primary, false);
  assert.equal(weak.verdict, 'INSUFFICIENT_PRECISION');
  assert.equal(r.gainSummary({targets: {}}, 0.05).verdict, 'ENERGY_GAIN_NOT_ESTIMABLE');
});

test('hypothesis summary follows the protocol', () => {
  const h = r.hypotheses(bundle);
  assert.equal(h.h1, true);
  assert.ok(h.h2DifferenceDb < 0.05);
  assert.ok(h.h3.positive);
  const failed = structuredClone(bundle);
  failed.cells[0].targets['0.001'].ci95_db[0] = -0.1;
  assert.equal(r.hypotheses(failed).h1, false);
});

test('log plot model maps the axis ends to the frame', () => {
  const m = r.logPlotModel(r.cellRows(cell('A1-awgn')));
  assert.equal(m.lx(0), m.pad.left);
  assert.equal(m.lx(14), m.width - m.pad.right);
  assert.equal(m.ly(0.5), m.pad.top);
  assert.equal(m.ly(1e-9), m.height - m.pad.bottom);
});

test('typical frame point is the level where Euclid BER is closest to the primary target', () => {
  const cell = {primary_target_ber: 1e-2, points: [
    {bits: 1000, euclidean_errors: 200}, {bits: 1000, euclidean_errors: 12}, {bits: 1000, euclidean_errors: 1}, {bits: 1000, euclidean_errors: 0}]};
  assert.equal(r.typicalPoint(cell), 1);
  assert.equal(r.typicalPoint({primary_target_ber: 1e-3, points: [{bits: 10, euclidean_errors: 0}]}), -1);
  const a3 = bundle.cells.find(c => c.id === 'A3-itu-moderate');
  const i = r.typicalPoint(a3);
  assert.ok(i >= 0 && a3.points[i].euclidean_errors > 0);
});
