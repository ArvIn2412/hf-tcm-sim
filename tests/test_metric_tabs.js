'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../src/hf_tcm/studio/static/metric_tabs.js');

test('window is centred on k and clamped to the frame', () => {
  assert.deepEqual(m.windowAround(50, 512, 96), [2, 98]);
  assert.deepEqual(m.windowAround(0, 512, 96), [0, 96]);
  assert.deepEqual(m.windowAround(510, 512, 96), [416, 512]);
  assert.deepEqual(m.windowAround(5, 40, 96), [0, 40]);
});

test('event summary counts events, symbol errors and lengths', () => {
  const s = m.summarizeEvents([{start: 1, stop: 3}, {start: 10, stop: 15}], [false, true, false, true, true]);
  assert.deepEqual(s, {count: 2, symbols: 3, meanLength: 3.5, maxLength: 5});
  assert.deepEqual(m.summarizeEvents([], []), {count: 0, symbols: 0, meanLength: 0, maxLength: 0});
});

test('masked mean skips missing values', () => {
  assert.equal(m.meanWhere([1, 2, null, 4], [true, false, true, true]), 2.5);
  assert.equal(m.meanWhere([1], [false]), null);
});

test('event-length histogram caps long events into the last bucket', () => {
  const events = [{start: 0, stop: 1}, {start: 5, stop: 8}, {start: 9, stop: 12}, {start: 20, stop: 40}];
  assert.deepEqual(m.lengthHistogram(events, 4), [1, 0, 2, 1]);
  assert.deepEqual(m.lengthHistogram([], 3), [0, 0, 0]);
});
