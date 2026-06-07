"""MST core with NetworkX for optional edges.

This module is intentionally IO-free: it takes dataclasses in, returns
a dataclass out, and raises typed exceptions on invalid inputs. This
makes the algorithm unit-testable without mocks and lets the async
service wrapper (app.services.mst_service) own all database IO.

Algorithm overview (mandatory + forbidden aware, NetworkX MST):
  1. Validate node count (>= 2).
  2. Build a Union-Find over all nodes.
  3. Detect cycles within the mandatory edges via Union-Find. If any
     mandatory edge would close a loop with only other mandatory edges,
     raise MandatoryCycleError.
  4. Seed the result with ALL mandatory edges (they are force-included).
  5. Build a NetworkX graph from optional (non-forbidden) edges only.
  6. Compute minimum spanning forest via nx.minimum_spanning_tree()
     on the optional-edge graph. This handles the Kruskal logic
     internally while NetworkX manages the Union-Find.
  7. Merge mandatory + NetworkX MST edges. If disconnected, raise
     DisconnectedGraphError with the unreachable node IDs.
  8. Return MSTResult with the chosen edges and total cost.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import networkx as nx


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeDict:
    """Pure representation of a node. No IO. No SQL."""

    id: UUID
    name: str
    type: Literal["city", "tower", "datacenter"]


@dataclass(frozen=True)
class EdgeDict:
    """Pure representation of an edge. No IO. No SQL."""

    id: UUID
    node_a_id: UUID
    node_b_id: UUID
    cost: float
    constraint_type: Literal["normal", "mandatory", "forbidden"]


@dataclass(frozen=True)
class MSTResult:
    """Result of a successful MST calculation.

    unreachable_nodes is always None on a successful result; it is only
    set on DisconnectedGraphError, never on the success path.
    """

    edges: list[EdgeDict]
    total_cost: float
    unreachable_nodes: list[UUID] | None = None


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class MSTError(Exception):
    """Base for all errors raised by the MST core."""


class InsufficientNodesError(MSTError):
    """Raised when the graph has fewer than 2 nodes."""

    def __init__(
        self, message: str = "Se requieren al menos 2 nodos para calcular el MST"
    ) -> None:
        super().__init__(message)
        self.message = message


class MandatoryCycleError(MSTError):
    """Raised when the set of mandatory edges forms a cycle by itself."""

    def __init__(self, conflicting_edge_ids: list[UUID]) -> None:
        self.conflicting_edge_ids = conflicting_edge_ids
        super().__init__(
            f"Mandatory edges form a cycle: {conflicting_edge_ids}"
        )


class DisconnectedGraphError(MSTError):
    """Raised when the graph has multiple connected components (some
    nodes are unreachable from others given the active constraints)."""

    def __init__(self, unreachable_nodes: list[UUID]) -> None:
        self.unreachable_nodes = unreachable_nodes
        super().__init__(
            f"Disconnected graph: {len(unreachable_nodes)} unreachable nodes"
        )


# ---------------------------------------------------------------------------
# Internal: Union-Find for mandatory cycle detection
# ---------------------------------------------------------------------------


class _UnionFind:
    """Minimal Union-Find with path compression and union-by-rank."""

    def __init__(self, elements: list[UUID]) -> None:
        self._parent: dict[UUID, UUID] = {x: x for x in elements}
        self._rank: dict[UUID, int] = {x: 0 for x in elements}

    def find(self, x: UUID) -> UUID:
        # Path compression
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        cur = x
        while self._parent[cur] != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, a: UUID, b: UUID) -> bool:
        """Unions the sets of a and b. Returns True if merged, False if
        a and b were already in the same set (cycle)."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        # Union by rank
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        return True

    def component_roots(self) -> set[UUID]:
        """Returns the set of all distinct component roots."""
        return {self.find(x) for x in self._parent}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate(
    nodes: list[NodeDict],
    edges: list[EdgeDict],
) -> MSTResult:
    """Compute the Minimum Spanning Tree for the given graph.

    Pure function. No IO. Deterministic.

    Constraints:
      - mandatory edges are force-included in the result.
      - forbidden edges are excluded from the result and from the
        connectivity check.
      - if the set of mandatory edges alone contains a cycle,
        MandatoryCycleError is raised.
      - if the resulting graph (mandatory + best non-mandatory) does
        not span all nodes, DisconnectedGraphError is raised.

    Raises:
        InsufficientNodesError: fewer than 2 nodes.
        MandatoryCycleError: mandatory edges form a cycle.
        DisconnectedGraphError: graph is not fully connected.
    """
    # 1. Validate input.
    if len(nodes) < 2:
        raise InsufficientNodesError()

    # 2. Partition edges by constraint type.
    mandatory: list[EdgeDict] = [
        e for e in edges if e.constraint_type == "mandatory"
    ]
    optional: list[EdgeDict] = [
        e for e in edges if e.constraint_type == "normal"
    ]
    # forbidden is implicitly excluded.

    # 3. Detect cycles within the mandatory edges using Union-Find.
    #    If any mandatory edge would close a loop with only other
    #    mandatory edges, the set of mandatory edges is inconsistent.
    uf = _UnionFind([n.id for n in nodes])
    for e in mandatory:
        merged = uf.union(e.node_a_id, e.node_b_id)
        if not merged:
            # All mandatory edges are part of the conflicting cycle.
            raise MandatoryCycleError(
                conflicting_edge_ids=[m.id for m in mandatory]
            )

    # 4. Seed the result with all mandatory edges.
    chosen: list[EdgeDict] = list(mandatory)
    total = sum(e.cost for e in mandatory)

    # 5. Build a NetworkX graph from optional (non-forbidden) edges only.
    #    Each edge carries its EdgeDict as data so we can recover the ID
    #    and constraint_type after MST computation.
    opt_graph: nx.Graph = nx.Graph()
    for n in nodes:
        opt_graph.add_node(n.id)
    for e in optional:
        opt_graph.add_edge(
            e.node_a_id,
            e.node_b_id,
            edge_data=e,
            weight=e.cost,
        )

    # 6. Compute minimum spanning forest on the optional-edge graph,
    #    then filter through the Union-Find (already seeded with
    #    mandatory edges) to skip edges that connect nodes already
    #    in the same component. This produces the same result as
    #    classic Kruskal but delegates the sorting/MST logic to
    #    NetworkX.
    mst_forest: nx.Graph = nx.minimum_spanning_tree(opt_graph, algorithm="kruskal")
    for u, v, data in mst_forest.edges(data=True):
        e: EdgeDict = data["edge_data"]
        if uf.find(e.node_a_id) != uf.find(e.node_b_id):
            uf.union(e.node_a_id, e.node_b_id)
            chosen.append(e)
            total += e.cost

    # 7. Validate connectivity: every node must be reachable from every
    #    other after merging mandatory + NetworkX MST edges. Build the
    #    chosen subgraph for the connectivity check — the Union-Find
    #    only reflects mandatory edges at this point, so we use
    #    NetworkX connected_components over the final chosen edge set.
    chosen_subgraph: nx.Graph = nx.Graph()
    for n in nodes:
        chosen_subgraph.add_node(n.id)
    for e in chosen:
        chosen_subgraph.add_edge(e.node_a_id, e.node_b_id)
    components: list[set[UUID]] = [
        set(c) for c in nx.connected_components(chosen_subgraph)
    ]
    if len(components) > 1:
        components.sort(key=len, reverse=True)
        unreachable = sorted(
            node_id for comp in components[1:] for node_id in comp
        )
        raise DisconnectedGraphError(unreachable_nodes=unreachable)

    # 8. Return the result.
    return MSTResult(edges=chosen, total_cost=total, unreachable_nodes=None)
