'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const s = require('../src/hf_tcm/studio/static/stages_compare.js');

test('3-bit labels follow natural labeling', () => {
  assert.deepEqual([0, 1, 5, 7].map(s.bits3), ['000', '001', '101', '111']);
});

test('Hamming label metrics are popcounts of the XOR with the hard label', () => {
  assert.deepEqual(s.hammingLabelMetrics(5), [2, 1, 3, 2, 1, 0, 2, 1]);
  assert.deepEqual(s.hammingLabelMetrics(0), [0, 1, 1, 2, 1, 2, 2, 3]);
  // 8 labels but only values 0..3: ties are unavoidable
  assert.deepEqual(s.ties(s.hammingLabelMetrics(5)), [[1, 3], [2, 3]]);
});

test('Euclidean label metrics scale squared distances by the CSI weight', () => {
  assert.deepEqual(s.euclidLabelMetrics([0.5, 2], 8), [4, 16]);
  assert.deepEqual(s.euclidLabelMetrics([0.5, 2], undefined), [0.5, 2]);
  assert.deepEqual(s.ties([0.1, 0.2, 0.3]), []);
});

test('error navigation finds the next flagged symbol', () => {
  const mask = [false, true, false, false, true];
  assert.equal(s.nextIndex(mask, 0), 1);
  assert.equal(s.nextIndex(mask, 1), 4);
  assert.equal(s.nextIndex(mask, 4), -1);
  assert.equal(s.nextIndex(mask, 4, -1), 1);
});
