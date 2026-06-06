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
    """REQ-MST-001 mandatory: edge X-Y (cost 100) is force-included in the
    spanning tree even though cheaper alternatives exist.

    The result is a spanning tree of n-1 edges: the mandatory edge is fixed
    in place, then Kruskal picks the cheapest non-mandatory edge that
    connects the remaining components. The total cost is HIGHER than the
    unconstrained optimal (3.0 in this case) because the mandatory edge
    locks in a suboptimal connection.
    """
    # Triangle: cheapest is 1-2 (1.0), then 2-3 (2.0), then 1-3 (100.0 mandatory).
    # The mandatory 1-3 is fixed; the cheapest other edge that connects the
    # rest is 1-2 (1.0). Result: {1-3 mandatory, 1-2}, total = 101.0.
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 1.0),
        _edge(2, 2, 3, 2.0),
        _edge(3, 1, 3, 100.0, kind="mandatory"),
    ]

    result = calculate(nodes, edges)

    edge_ids = {e.id for e in result.edges}
    assert edges[2].id in edge_ids, "mandatory edge must be in MST"
    # Unconstrained optimal is 1+2=3.0; the result with mandatory is 1+100=101.0.
    assert result.total_cost == pytest.approx(101.0)
    assert result.total_cost > 3.0, "mandatory should make total cost higher than unconstrained optimal"
    # n-1 = 2 edges for a spanning tree of 3 nodes.
    assert len(result.edges) == 2


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


def test_calculate_disconnected_no_partial_result() -> None:
    """REQ-MST-006 (core layer): when DisconnectedGraphError is raised,
    NO MSTResult is constructed. The core must never return partial data
    on failure — the service layer relies on this to know whether to
    persist to mst_results.

    This is the triangulation test that closes the loop on the
    "no write on failure" requirement at the unit level.
    """
    nodes: List[NodeDict] = [_node(1), _node(2), _node(3), _node(4)]
    edges: List[EdgeDict] = [
        _edge(1, 1, 2, 1.0),
        _edge(2, 3, 4, 1.0),
    ]

    # Use a sentinel: if MSTResult were ever returned, the test would
    # still raise the caught exception and the sentinel would be
    # observed. We assert the exception is the only observable outcome.
    sentinel = "MSTResult was unexpectedly returned"
    try:
        result = calculate(nodes, edges)
        # If we get here, MSTResult WAS returned — fail the test.
        pytest.fail(f"{sentinel}: {result!r}")
    except DisconnectedGraphError as exc:
        # The exception path. The MSTResult must NOT be assigned.
        assert exc.unreachable_nodes is not None
        assert len(exc.unreachable_nodes) == 2
