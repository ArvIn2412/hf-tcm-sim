"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { renderSvg } = require("../src/hf_tcm/studio/static/trellis_projector.js");

function branchFixture() {
  const stateIds = Array.from({ length: 16 }, (_, id) => id);
  const edges = stateIds.flatMap(sourceId => Array.from({ length: 4 }, (_, inputId) => ({
    id: sourceId * 4 + inputId,
    sourceId,
    targetId: (sourceId * 3 + inputId) % 16,
    inputId,
    input: inputId.toString(2).padStart(2, "0"),
    output: "000",
  })));
  return { stateIds, edges };
}

test("projector overview retains all 16 states and 64 transitions without edge labels", () => {
  const { stateIds, edges } = branchFixture();
  const svg = renderSvg({
    stateIds,
    edges,
    mode: "overview",
    selectedEdgeId: 9,
    selectedSymbolEdgeId: 5,
    viterbiEdges: [1, 9],
    referenceEdges: [5, 9],
  });
  assert.equal((svg.match(/data-projector-edge=/g) || []).length, 64);
  assert.equal((svg.match(/class="p-state"/g) || []).length, 16);
  assert.equal((svg.match(/<text class="p-edge-label"[^>]*hidden/g) || []).length, 64);
  assert.match(svg, /p-edge-viterbi/);
  assert.match(svg, /p-edge-reference/);
  assert.match(svg, /p-edge-symbol/);
});

test("detail mode labels only the selected edge and preserves accessible edge controls", () => {
  const { stateIds, edges } = branchFixture();
  const svg = renderSvg({ stateIds, edges, mode: "detail", selectedEdgeId: 7 });
  assert.equal((svg.match(/<text class="p-edge-label"[^>]*hidden/g) || []).length, 63);
  assert.equal((svg.match(/<text class="p-edge-label"[^>]*>ee7<\/text>/g) || []).length, 1);
  assert.equal((svg.match(/role="button" tabindex="0"/g) || []).length, 64);
});

test("zoom bounds are validated without dropping transitions", () => {
  const { stateIds, edges } = branchFixture();
  assert.throws(() => renderSvg({ stateIds, edges, zoom: 1.7 }), /zoom/);
  const svg = renderSvg({ stateIds, edges, zoom: 1.4 });
  assert.match(svg, /width:1750px/);
  assert.equal((svg.match(/data-projector-edge=/g) || []).length, 64);
});
