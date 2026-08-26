"""A directed lineage graph over data assets.

Edges point *upstream -> downstream* (from a dependency to the thing that
depends on it), so "what does a change affect?" is a downstream traversal.

Backed by ``networkx`` — an in-process graph is more than enough at the scale of
a dbt project; no graph database is required.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from .exposure import Exposure, derive_criticality


class LineageGraph:
    """Wraps a ``networkx.DiGraph`` with lineage-oriented traversals."""

    def __init__(self) -> None:
        self._g = nx.DiGraph()

    @property
    def nodes(self) -> set[str]:
        return set(self._g.nodes)

    def add_node(self, node: str, **attrs: object) -> None:
        self._g.add_node(node, **attrs)

    def add_edge(self, upstream: str, downstream: str) -> None:
        """Record that ``downstream`` depends on ``upstream``."""
        self._g.add_edge(upstream, downstream)

    def downstream(self, node: str, transitive: bool = True) -> set[str]:
        """Assets affected by a change to ``node``."""
        if node not in self._g:
            return set()
        if transitive:
            return set(nx.descendants(self._g, node))
        return set(self._g.successors(node))

    def upstream(self, node: str, transitive: bool = True) -> set[str]:
        """Assets that ``node`` derives from."""
        if node not in self._g:
            return set()
        if transitive:
            return set(nx.ancestors(self._g, node))
        return set(self._g.predecessors(node))

    def is_downstream_of(self, node: str, source: str) -> bool:
        """True if ``node`` is (transitively) affected by ``source``."""
        return node in self.downstream(source)

    def node_kind(self, node: str) -> str | None:
        """``"data"`` | ``"exposure"`` | ``None`` if the node is unknown."""
        if node not in self._g:
            return None
        return self._g.nodes[node].get("kind")

    def _reachable(self, assets: set[str]) -> set[str]:
        out: set[str] = set()
        for asset in assets:
            out |= self.downstream(asset)
        return out

    def exposures_downstream_of(self, assets: set[str]) -> list[Exposure]:
        """Exposure objects reachable downstream from any of ``assets``.

        Sorted by criticality (worst first), then name, then ``unique_id`` as a
        total tiebreaker so the order never falls back to set/hash iteration.
        """
        found = [
            self._g.nodes[n]["exposure"]
            for n in self._reachable(assets)
            if self._g.nodes[n].get("kind") == "exposure"
        ]
        return sorted(found, key=lambda e: (-int(e.criticality), e.name, e.unique_id))

    def data_downstream_of(self, assets: set[str]) -> set[str]:
        """Descendants of ``assets`` that are data nodes (exposures excluded)."""
        return {n for n in self._reachable(assets) if self._g.nodes[n].get("kind") != "exposure"}


def load_dbt_manifest(manifest: dict | str | Path) -> LineageGraph:
    """Build a :class:`LineageGraph` from a dbt ``manifest.json``.

    Accepts a parsed dict or a path to the manifest file. Uses the ``nodes``
    map and each node's ``depends_on.nodes`` to reconstruct the DAG. If the
    manifest has an ``exposures`` map, each exposure becomes an ``exposure``-
    kind node with a ``model -> exposure`` edge for every known dependency.
    """
    if isinstance(manifest, (str, Path)):
        manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))

    graph = LineageGraph()
    nodes: dict[str, dict] = manifest.get("nodes", {})
    for unique_id, node in nodes.items():
        graph.add_node(
            unique_id,
            kind="data",
            resource_type=node.get("resource_type"),
        )
    for unique_id, node in nodes.items():
        for dependency in node.get("depends_on", {}).get("nodes", []):
            if dependency in nodes:
                graph.add_edge(dependency, unique_id)

    exposures: dict[str, dict] = manifest.get("exposures", {})
    for unique_id, raw in exposures.items():
        owner = raw.get("owner") or {}
        exposure = Exposure(
            unique_id=unique_id,
            name=raw.get("name", unique_id),
            type=raw.get("type", ""),
            criticality=derive_criticality(
                raw.get("type", ""), raw.get("maturity", ""), raw.get("meta", {})
            ),
            owner=owner.get("name") or owner.get("email") or "",
            url=raw.get("url", ""),
            depends_on=frozenset(raw.get("depends_on", {}).get("nodes", [])),
        )
        graph.add_node(unique_id, kind="exposure", exposure=exposure)
        for dependency in exposure.depends_on:
            if dependency in nodes:
                graph.add_edge(dependency, unique_id)
    return graph
