(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.HFTCMTrellisProjector = api;
})(typeof globalThis === "undefined" ? this : globalThis, function () {
  "use strict";

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  }

  function layout(stateIds) {
    const count = stateIds.length;
    const columns = count <= 4 ? 2 : 4;
    const rows = Math.ceil(count / columns);
    const xGap = count <= 4 ? 360 : 330;
    const yGap = count <= 4 ? 260 : 245;
    const left = 130;
    const top = 105;
    const points = new Map(stateIds.map((id, i) => [id, { x: left + (i % columns) * xGap, y: top + Math.floor(i / columns) * yGap }]));
    return { points, width: left * 2 + (columns - 1) * xGap, height: top * 2 + (rows - 1) * yGap };
  }

  function pathFor(edge, points, index) {
    const source = points.get(edge.sourceId);
    const target = points.get(edge.targetId);
    const input = Number(edge.inputId ?? index % 4);
    if (edge.sourceId === edge.targetId) {
      const side = source.x < 500 ? -1 : 1;
      const offset = 70 + (input - 1.5) * 18;
      return `M ${source.x - 18} ${source.y - 24} C ${source.x + side * offset} ${source.y - 100 - input * 9} ${source.x + side * offset} ${source.y + 75 + input * 7} ${source.x + 18} ${source.y + 24}`;
    }
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const lane = (input - 1.5) * 22;
    const cx = (source.x + target.x) / 2 - (dy / distance) * lane;
    const cy = (source.y + target.y) / 2 + (dx / distance) * lane;
    return `M ${source.x} ${source.y} Q ${cx} ${cy} ${target.x} ${target.y}`;
  }

  function renderSvg({ stateIds, stateLabels = {}, edges, mode = "overview", selectedEdgeId = 0, selectedSymbolEdgeId = null, viterbiEdges = [], referenceEdges = [], zoom = 1, idPrefix = "trellis" }) {
    if (!Array.isArray(stateIds) || !Array.isArray(edges) || !stateIds.length) throw new TypeError("stateIds and edges must be non-empty arrays");
    if (mode !== "overview" && mode !== "detail") throw new RangeError("mode must be overview or detail");
    const scale = Number(zoom);
    if (!Number.isFinite(scale) || scale < 1 || scale > 1.6) throw new RangeError("zoom must be between 1 and 1.6");
    const { points, width, height } = layout(stateIds);
    const viterbi = new Set(viterbiEdges);
    const reference = new Set(referenceEdges);
    const svgEdges = edges.map((edge, index) => {
      const selected = edge.id === selectedEdgeId;
      const selectedSymbol = edge.id === selectedSymbolEdgeId;
      const classes = ["p-edge", viterbi.has(edge.id) ? "p-edge-viterbi" : "", reference.has(edge.id) ? "p-edge-reference" : "", selectedSymbol ? "p-edge-symbol" : "", selected ? "p-edge-selected" : ""].filter(Boolean).join(" ");
      const title = `ee${edge.id}: ${edge.sourceLabel ?? edge.sourceId} → ${edge.targetLabel ?? edge.targetId}; ${edge.input ?? ""} / ${edge.output ?? ""}`;
      const labelHidden = mode !== "detail" || !selected;
      return `<path class="${classes}" data-projector-edge="${escapeHtml(edge.id)}" d="${pathFor(edge, points, index)}" marker-end="url(#${idPrefix}-arrow)" role="button" tabindex="0" aria-label="${escapeHtml(title)}"><title>${escapeHtml(title)}</title></path><text class="p-edge-label" x="${(points.get(edge.sourceId).x + points.get(edge.targetId).x) / 2}" y="${(points.get(edge.sourceId).y + points.get(edge.targetId).y) / 2 - 5}" text-anchor="middle" data-label-edge="${escapeHtml(edge.id)}" ${labelHidden ? "hidden" : ""}>ee${escapeHtml(edge.id)}</text>`;
    }).join("");
    const nodes = stateIds.map(id => {
      const p = points.get(id);
      return `<g class="p-state" data-state-id="${escapeHtml(id)}"><circle class="p-state-node" cx="${p.x}" cy="${p.y}" r="34"/><text class="p-state-label" x="${p.x}" y="${p.y + 7}" text-anchor="middle">${escapeHtml(stateLabels[id] ?? id)}</text></g>`;
    }).join("");
    return `<svg class="trellis-svg projector-trellis" role="img" aria-label="Trellis: ${stateIds.length} states, ${edges.length} transitions" viewBox="0 0 ${width} ${height}" style="width:${Math.round(width * scale)}px" data-mode="${mode}"><defs><marker id="${idPrefix}-arrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0L10 4L0 8z"/></marker></defs>${svgEdges}${nodes}</svg>`;
  }

  return Object.freeze({ renderSvg, layout });
});
