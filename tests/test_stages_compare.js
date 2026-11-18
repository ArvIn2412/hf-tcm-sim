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

test('add-compare-select keeps the minimum, flags ties and honours pilot constraints', () => {
  const states = [[0], [1]];
  // [id, from, input, output, to]
  const edges = [
    [0, [0], [0], [0, 0, 0], [0]],
    [1, [0], [1], [0, 0, 1], [1]],
    [2, [1], [0], [0, 1, 0], [0]],
    [3, [1], [1], [0, 1, 1], [1]],
    [4, [1], [1], [1, 1, 1], [1]],
  ];
  const branch = [1, 2, 0, 1, 2];
  const [to0, to1] = s.acsCandidates(edges, states, [3, 4], branch, null);
  assert.equal(to0.winner, 0);                       // 3+1=4 vs 4+0=4: tie, first edge wins
  assert.deepEqual(to0.candidates.map(c => [c.total, c.winner, c.tied]), [[4, true, false], [4, false, true]]);
  assert.equal(to1.winner, 1);                       // 3+2=5 < 4+1=5? tie again -> edge 1; edge 4: 6
  assert.deepEqual(to1.candidates.map(c => c.total), [5, 5, 6]);
  assert.equal(to1.candidates.find(c => c.edge === 4).tied, false);

  const pilot = s.acsCandidates(edges, states, [3, 4], branch, [1]);
  assert.deepEqual(pilot[0].candidates, []);         // no input-1 edge reaches state 0
  assert.equal(pilot[0].winner, null);
  assert.deepEqual(pilot[1].candidates.map(c => c.edge), [1, 3, 4]);

  const unreachable = s.acsCandidates(edges, states, [null, 4], branch, null);
  assert.deepEqual(unreachable[0].candidates.map(c => c.edge), [2]);
});
