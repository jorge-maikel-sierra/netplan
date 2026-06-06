"""Unit tests for the pure Kruskal MST core (no IO, no mocks).

The core (app.core.mst_algorithm) is a deterministic pure function:
takes NodeDict and EdgeDict lists, returns MSTResult. These tests
cover every REQ-MST-001 and REQ-MST-002 scenario using literal
constructors — no MagicMock, no patches, no async.
"""
from __future__ import annotations

import uuid
from typing import List

import pytest

from app.core.mst_algorithm import (
    DisconnectedGraphError,
    EdgeDict,
    InsufficientNodesError,
    MandatoryCycleError,
    NodeDict,
    calculate,
)


# ---------------------------------------------------------------------------
# Helpers — small builders for node/edge literals with stable UUIDs.
# ---------------------------------------------------------------------------


def _node(idx: int, type_: str = "city", name: str | None = None) -> NodeDict:
    """Build a NodeDict with a deterministic UUID derived from idx."""
    return NodeDict(
        id=uuid.UUID(int=idx),
        name=name or f"node-{idx}",
        type=type_,  # type: ignore[arg-type]
    )


def _edge(idx: int, a: int, b: int, cost: float, kind: str = "normal") -> EdgeDict:
    """Build an EdgeDict with a deterministic UUID derived from idx."""
    return EdgeDict(
        id=uuid.UUID(int=10_000 + idx),
        node_a_id=uuid.UUID(int=a),
        node_b_id=uuid.UUID(int=b),
        cost=cost,
        constraint_type=kind,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# REQ-MST-001: Happy path & constraint handling
# ---------------------------------------------------------------------------


def test_calculate_simple_triangle() -> None:
    """REQ-MST-001 happy: 3 nodes triangle, MST = 2 cheapest edges (cost 1+2=3)."""
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 1.0),
        _edge(2, 2, 3, 2.0),
        _edge(3, 1, 3, 3.0),
    ]

    result = calculate(nodes, edges)

    assert result.total_cost == pytest.approx(3.0)
    assert len(result.edges) == 2
    edge_costs = sorted(e.cost for e in result.edges)
    assert edge_costs == [1.0, 2.0]
    # The two chosen edges must connect all three nodes.
    connected = {1, 2, 3}
    touched: set[int] = set()
    for e in result.edges:
        touched.add(int(e.node_a_id.int))
        touched.add(int(e.node_b_id.int))
    assert touched == connected


def test_calculate_mandatory_force_included() -> None:
    """REQ-MST-001 mandatory: edge X-Y (cost 100) is force-included even
    though cheaper alternatives exist."""
    # Triangle: cheapest is 1-2 (1.0), then 2-3 (2.0), then 1-3 (100.0 mandatory).
    # The mandatory 1-3 must appear; total cost = 1+2+100 = 103.
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 1.0),
        _edge(2, 2, 3, 2.0),
        _edge(3, 1, 3, 100.0, kind="mandatory"),
    ]

    result = calculate(nodes, edges)

    edge_ids = {e.id for e in result.edges}
    assert edges[2].id in edge_ids, "mandatory edge must be in MST"
    assert result.total_cost == pytest.approx(103.0)
    assert len(result.edges) == 3  # 3 nodes, 3 edges (mandatory forces triangle)


def test_calculate_mandatory_cycle_rejected() -> None:
    """REQ-MST-001 cycle: 3 mandatory edges forming a cycle raises
    MandatoryCycleError with the conflicting edge IDs."""
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 5.0, kind="mandatory"),
        _edge(2, 2, 3, 5.0, kind="mandatory"),
        _edge(3, 1, 3, 5.0, kind="mandatory"),
    ]

    with pytest.raises(MandatoryCycleError) as excinfo:
        calculate(nodes, edges)

    assert set(excinfo.value.conflicting_edge_ids) == {edges[0].id, edges[1].id, edges[2].id}


def test_calculate_forbidden_excluded() -> None:
    """REQ-MST-001 forbidden: the cheapest edge (0.5) is forbidden, so the
    MST must pick the next two cheapest (1.0 + 2.0 = 3.0)."""
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 0.5, kind="forbidden"),
        _edge(2, 1, 2, 1.0),  # alternate normal edge
        _edge(3, 2, 3, 2.0),
    ]

    result = calculate(nodes, edges)

    edge_ids = {e.id for e in result.edges}
    assert edges[0].id not in edge_ids, "forbidden edge must never be in MST"
    assert result.total_cost == pytest.approx(3.0)
    assert len(result.edges) == 2


def test_calculate_insufficient_nodes_zero() -> None:
    """REQ-MST-001 0 nodes: raises InsufficientNodesError."""
    with pytest.raises(InsufficientNodesError):
        calculate([], [])


def test_calculate_insufficient_nodes_one() -> None:
    """REQ-MST-001 1 node: raises InsufficientNodesError."""
    nodes: List[NodeDict] = [_node(1)]
    with pytest.raises(InsufficientNodesError):
        calculate(nodes, [])


def test_calculate_two_nodes_one_edge() -> None:
    """REQ-MST-001 minimal valid: 2 nodes + 1 edge, MST has exactly that edge."""
    nodes: List[NodeDict] = [_node(1), _node(2)]
    edges: List[EdgeDict] = [_edge(1, 1, 2, 5.0)]

    result = calculate(nodes, edges)

    assert result.total_cost == pytest.approx(5.0)
    assert len(result.edges) == 1
    assert result.edges[0].id == edges[0].id


# ---------------------------------------------------------------------------
# REQ-MST-002: Disconnected graph
# ---------------------------------------------------------------------------


def test_calculate_disconnected_returns_unreachable() -> None:
    """REQ-MST-002: 2 disconnected subgraphs (A-B and C-D) raises
    DisconnectedGraphError with the unreachable node IDs in the exception."""
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3), _node(4)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 1.0),
        _edge(2, 3, 4, 1.0),
    ]

    with pytest.raises(DisconnectedGraphError) as excinfo:
        calculate(nodes, edges)

    # The smaller component is reported as unreachable (or the larger — either
    # is acceptable; the spec only requires that the two groups be partitioned).
    unreachable = excinfo.value.unreachable_nodes
    assert len(unreachable) == 2
    assert {uuid.UUID(int=1), uuid.UUID(int=2)}.issubset(set(unreachable)) or \
           {uuid.UUID(int=3), uuid.UUID(int=4)}.issubset(set(unreachable))
