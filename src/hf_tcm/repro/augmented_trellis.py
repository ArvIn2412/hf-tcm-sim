"""Reachable trellis expanded by the minimum delayed phase-symbol history."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from hf_tcm.repro.encoder import STATE_ORDER, State, transition_table
from hf_tcm.repro.identifiers import ENCODER_ID, MAPPING_ID

MAX_PREVIOUS_SYMBOLS = 2
MAX_AUGMENTED_STATES = 256
MAX_AUGMENTED_EDGES = 2048


@dataclass(frozen=True, slots=True)
class AugmentedNode:
    node_id: int
    encoder_state: State
    phase_history: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AugmentedTransition:
    expanded_edge_id: int
    source_node_id: int
    target_node_id: int
    base_edge_id: int
    source_state: State
    target_state: State
    input_pair: tuple[int, int]
    coded_triple: tuple[int, int, int]
    phase_index: int


@dataclass(frozen=True, slots=True)
class AugmentedTrellis:
    nodes: tuple[AugmentedNode, ...]
    edges: tuple[AugmentedTransition, ...]
    initial_node_id: int
    memory_symbols: int
    initial_state: State
    delays_samples: tuple[int, ...]
    encoder_id: str = ENCODER_ID
    mapping_id: str = MAPPING_ID

    @property
    def state_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def outgoing(self, node_id: int) -> tuple[AugmentedTransition, ...]:
        return tuple(edge for edge in self.edges if edge.source_node_id == node_id)


def build_augmented_trellis(
    initial_state: State,
    delays_samples: tuple[int, ...],
    *,
    samples_per_symbol: int = 8,
    max_nodes: int = MAX_AUGMENTED_STATES,
    max_edges: int = MAX_AUGMENTED_EDGES,
) -> AugmentedTrellis:
    """Build reachable nodes using `ceil(max_delay/samples_per_symbol)` prior phases."""
    if initial_state not in STATE_ORDER:
        raise ValueError("initial_state must be an Encoder A state")
    if (
        not isinstance(delays_samples, tuple)
        or not delays_samples
        or any(type(delay) is not int or delay < 0 for delay in delays_samples)
    ):
        raise ValueError("delays_samples must be a nonempty tuple of nonnegative integers")
    if type(samples_per_symbol) is not int or samples_per_symbol != 8:
        raise ValueError("samples_per_symbol must equal 8")
    if type(max_nodes) is not int or max_nodes < 1 or type(max_edges) is not int or max_edges < 1:
        raise ValueError("graph caps must be positive integers")
    memory = (max(delays_samples) + samples_per_symbol - 1) // samples_per_symbol
    if memory > MAX_PREVIOUS_SYMBOLS:
        raise ValueError("channel delay requires at most 2 previous symbols")

    phase = {
        edge_id: 4 * output[0] + 2 * output[1] + output[2]
        for edge_id, _state, _pair, output, _target in transition_table()
    }
    canonical = transition_table()
    initial_history = (-1,) * memory
    nodes: list[AugmentedNode] = [AugmentedNode(0, initial_state, initial_history)]
    node_by_key: dict[tuple[State, tuple[int, ...]], int] = {(initial_state, initial_history): 0}
    pending: deque[int] = deque([0])
    edges: list[AugmentedTransition] = []
    while pending:
        source_id = pending.popleft()
        source_node = nodes[source_id]
        for base_edge_id, source, pair, coded, target in canonical:
            if source != source_node.encoder_state:
                continue
            phase_index = phase[base_edge_id]
            target_history = (
                (phase_index, *source_node.phase_history[: memory - 1]) if memory else ()
            )
            key = target, target_history
            target_id = node_by_key.get(key)
            if target_id is None:
                if len(nodes) >= max_nodes:
                    raise ValueError("expanded trellis exceeds configured cap")
                target_id = len(nodes)
                node_by_key[key] = target_id
                nodes.append(AugmentedNode(target_id, target, target_history))
                pending.append(target_id)
            if len(edges) >= max_edges:
                raise ValueError("expanded trellis exceeds configured cap")
            edges.append(
                AugmentedTransition(
                    expanded_edge_id=len(edges),
                    source_node_id=source_id,
                    target_node_id=target_id,
                    base_edge_id=base_edge_id,
                    source_state=source,
                    target_state=target,
                    input_pair=pair,
                    coded_triple=coded,
                    phase_index=phase_index,
                )
            )

    return AugmentedTrellis(
        nodes=tuple(nodes),
        edges=tuple(edges),
        initial_node_id=0,
        memory_symbols=memory,
        initial_state=initial_state,
        delays_samples=delays_samples,
    )
