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


def load_dbt_manifest(manifest: dict | str | Path) -> LineageGraph:
    """Build a :class:`LineageGraph` from a dbt ``manifest.json``.

    Accepts a parsed dict or a path to the manifest file. Uses the ``nodes``
    map and each node's ``depends_on.nodes`` to reconstruct the DAG.
    """
    if isinstance(manifest, (str, Path)):
        manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))

    graph = LineageGraph()
    nodes: dict[str, dict] = manifest.get("nodes", {})
    for unique_id, node in nodes.items():
        graph.add_node(
            unique_id,
            resource_type=node.get("resource_type"),
        )
    for unique_id, node in nodes.items():
        for dependency in node.get("depends_on", {}).get("nodes", []):
            if dependency in nodes:
                graph.add_edge(dependency, unique_id)
    return graph
