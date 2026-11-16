const test = require("node:test");
const assert = require("node:assert/strict");

const {
  calculateSampleWindow,
  symbolIndexAtSample,
  windowStartSampleForSymbol,
} = require("../src/hf_tcm/studio/static/signal_window.js");

test("F=32 first, middle, and last 20-symbol windows are exact", () => {
  const first = calculateSampleWindow(256, 0, 160);
  const middle = calculateSampleWindow(256, 48, 160);
  const last = calculateSampleWindow(256, 500, 160);

  assert.deepEqual([first.startSample, first.endSample, first.length], [0, 160, 160]);
  assert.deepEqual([middle.startSample, middle.endSample, middle.length], [48, 208, 160]);
  assert.deepEqual([last.startSample, last.endSample, last.length], [96, 256, 160]);
  assert.equal(last.maxStartSample, 96);
});

test("short frames show only available samples without padding", () => {
  const window = calculateSampleWindow(32, 17, 160);
  assert.deepEqual([window.startSample, window.endSample, window.length], [0, 32, 32]);
  assert.equal(window.maxStartSample, 0);
});

test("sample positions map to their containing TCM symbol", () => {
  assert.equal(symbolIndexAtSample(0, 32, 8), 0);
  assert.equal(symbolIndexAtSample(15, 32, 8), 1);
  assert.equal(symbolIndexAtSample(255, 32, 8), 31);
});

test("jumping to a symbol keeps its eight samples inside the viewport", () => {
  assert.equal(windowStartSampleForSymbol(0, 32, 8, 160), 0);
  assert.equal(windowStartSampleForSymbol(16, 32, 8, 160), 48);
  assert.equal(windowStartSampleForSymbol(31, 32, 8, 160), 96);
  assert.equal(windowStartSampleForSymbol(3, 4, 8, 160), 0);
});

test("invalid sample-window dimensions are rejected", () => {
  assert.throws(() => calculateSampleWindow(0, 0, 160), /positive integer/);
  assert.throws(() => calculateSampleWindow(64, 0, 0), /positive integer/);
  assert.throws(() => calculateSampleWindow(64, Number.NaN, 32), /integer/);
});
