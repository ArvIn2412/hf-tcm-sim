"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const ui = require("../src/hf_tcm/studio/static/minimalist_state.js");

test("primary navigation exposes the six requested views in order", () => {
  assert.deepEqual(ui.PRIMARY_VIEWS.map(view => view.id), ["simulation", "stages", "samples", "hidden", "decoding", "results"]);
  assert.equal(ui.PRIMARY_VIEWS[0].label, "Моделювання");
});

test("signal stages carry factual status and map only supported chart adapters", () => {
  assert.equal(ui.SIGNAL_STAGES.length, 10);
  assert.equal(ui.SIGNAL_STAGES[4].status, "DERIVED VISUALIZATION");
  assert.equal(ui.SIGNAL_STAGES[4].chart, "tx");
  assert.equal(ui.SIGNAL_STAGES[6].chart, "gain");
  assert.ok(ui.SIGNAL_STAGES.every(stage => stage.source && stage.formula));
});

test("run lifecycle preserves a single result and marks edited configuration stale", () => {
  const state = ui.createUiState();
  assert.equal(state.activeRunId, null);
  ui.commitRun(state, "run-1", { encoder: "A", bits: "01" });
  ui.markConfigurationStale(state);
  assert.equal(state.activeRunId, "run-1");
  assert.equal(state.stale, true);
  assert.deepEqual(state.runConfig, { encoder: "A", bits: "01" });
  ui.commitRun(state, "run-2", { encoder: "A", bits: "10" });
  assert.equal(state.activeRunId, "run-2");
  assert.equal(state.stale, false);
});

test("navigation and symbol selection do not create or replace a run", () => {
  const state = ui.createUiState();
  ui.commitRun(state, "run-1", { encoder: "A" });
  ui.setActiveView(state, "samples");
  ui.selectSymbol(state, 31, 32);
  assert.equal(state.activeView, "samples");
  assert.equal(state.selectedSymbol, 31);
  assert.equal(state.activeRunId, "run-1");
});

test("sample windows clamp at frame boundaries and do not pad short frames", () => {
  assert.deepEqual(ui.sampleWindow(256, "window", 0), { start: 0, end: 160, length: 160 });
  assert.deepEqual(ui.sampleWindow(256, "window", 400), { start: 96, end: 256, length: 160 });
  assert.deepEqual(ui.sampleWindow(64, "window", 0), { start: 0, end: 64, length: 64 });
  assert.deepEqual(ui.sampleWindow(256, "detail", 41), { start: 41, end: 61, length: 20 });
  assert.deepEqual(ui.sampleWindow(256, "full", 50), { start: 0, end: 256, length: 256 });
});
