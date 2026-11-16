(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.HFTCMMinimalistState = api;
})(typeof globalThis === "undefined" ? this : globalThis, function () {
  "use strict";

  const PRIMARY_VIEWS = Object.freeze([
    { id: "simulation", label: "Моделювання" },
    { id: "stages", label: "Етапи сигналу" },
    { id: "samples", label: "Відліки сигналу" },
    { id: "hidden", label: "Приховані стани" },
    { id: "decoding", label: "Декодування" },
    { id: "results", label: "Результати" },
  ]);

  const SIGNAL_STAGES = Object.freeze([
    { id: "information", label: "Джерело інформації", chart: "input_bits", status: "ACTUAL IMPLEMENTED", formula: "u[k] ∈ {0,1}", source: "trace.input.information_bits" },
    { id: "encoder", label: "Кодер", chart: "encoded_bits", status: "ACTUAL IMPLEMENTED", formula: "c_f = encoder(u_f,q_f)", source: "trace.transmitter.encoded_output_bits" },
    { id: "tcm", label: "Маніпуляційне кодування", chart: "states_edges", status: "ACTUAL IMPLEMENTED", formula: "(q_f,u_f) → q_{f+1}", source: "trace.arms[].symbols[].selected_encoder_edge_id" },
    { id: "modulation", label: "Модуляція 8PSK", chart: "constellation", status: "ACTUAL IMPLEMENTED", formula: "x_f = I_f + jQ_f", source: "trace.transmitter.transmitted_symbols" },
    { id: "zoh", label: "Формування сигналу / прямокутний ZOH", chart: "tx", status: "DERIVED VISUALIZATION", formula: "x[n] = x_f, n=8f…8f+7", source: "trace.transmitter.transmitted_samples; project trace convention" },
    { id: "tx-output", label: "ВЧ передавач / модельний вихід", chart: "tx", status: "ACTUAL IMPLEMENTED", formula: "x_f = I_f + jQ_f", source: "trace.transmitter.transmitted_symbols; complex-envelope model" },
    { id: "gain", label: "Канал / модельне підсилення", chart: "gain", status: "ACTUAL IMPLEMENTED", formula: "x_g[n] = a·x[n]", source: "trace.transmitter.channel_contribution_samples; fixed-gain fixture only" },
    { id: "noise", label: "Детермінований шум", chart: "noise", status: "ACTUAL IMPLEMENTED", formula: "y[n] = a·x[n] + w[n]", source: "trace.transmitter.noise_samples" },
    { id: "received", label: "ВЧ приймач / модельний вхід", chart: "received", status: "ACTUAL IMPLEMENTED", formula: "y[n] = a·x[n] + w[n]", source: "trace.transmitter.received_samples; complex-envelope model only" },
    { id: "observed", label: "Спостереження I/Q", chart: "observed_iq", status: "ACTUAL IMPLEMENTED", formula: "Y_f = ADR-012 project transform", source: "trace.arms[].symbols[].observed_iq" },
  ]);

  function createUiState() {
    return { activeView: "simulation", activeRunId: null, runConfig: null, stale: false, selectedEncoder: "A", selectedReceiver: null, selectedSymbol: 0, windowStart: 0, currentStage: "information", displayMode: "simple", decodeTab: "metrics", hiddenTab: "tcm", runSequence: 0 };
  }
  function setActiveView(state, viewId) {
    if (!PRIMARY_VIEWS.some(view => view.id === viewId)) throw new RangeError(`Unknown view: ${viewId}`);
    state.activeView = viewId;
    return state;
  }
  function markConfigurationStale(state) {
    if (state.activeRunId !== null) state.stale = true;
    return state.stale;
  }
  function commitRun(state, runId, config) {
    if (!runId) throw new TypeError("runId is required");
    state.activeRunId = runId;
    state.runConfig = structuredClone(config);
    state.stale = false;
    state.selectedSymbol = 0;
    state.windowStart = 0;
    return state;
  }
  function selectSymbol(state, index, symbolCount) {
    const maximum = Math.max(0, Number(symbolCount) - 1);
    state.selectedSymbol = Math.max(0, Math.min(maximum, Math.trunc(Number(index) || 0)));
    return state.selectedSymbol;
  }
  function sampleWindow(sampleCount, mode, requestedStart = 0) {
    const count = Math.max(0, Math.trunc(Number(sampleCount) || 0));
    if (mode === "full") return { start: 0, end: count, length: count };
    const requestedLength = mode === "detail" ? 20 : mode === "window" ? 160 : null;
    if (requestedLength === null) throw new RangeError(`Unknown sample-window mode: ${mode}`);
    const length = Math.min(count, requestedLength);
    const start = Math.max(0, Math.min(Math.max(0, count - length), Math.trunc(Number(requestedStart) || 0)));
    return { start, end: start + length, length };
  }
  return Object.freeze({ PRIMARY_VIEWS, SIGNAL_STAGES, createUiState, setActiveView, markConfigurationStale, commitRun, selectSymbol, sampleWindow });
});
