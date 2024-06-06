"""
The classes and functions in this module are related to requisite
handling and ordering of chunks by the State compiler
"""

from __future__ import annotations

import fnmatch
import logging
import sys
from collections import defaultdict
from collections.abc import Generator, Iterable, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import networkx as nx

log = logging.getLogger(__name__)

# See https://docs.saltproject.io/en/latest/ref/states/layers.html for details on the naming
LowChunk = dict[str, Any]

if TYPE_CHECKING or sys.version_info >= (3, 10):
    staticmethod_hack = staticmethod
else:
    # Python < 3.10 does not support calling static methods directly from the class body
    # as is the case with enum _generate_next_value_.
    # Since @staticmethod is only added for static type checking, substitute a dummy decorator.
    def staticmethod_hack(f):
        return f


def _gen_tag(low: LowChunk) -> str:
    """
    Generate the a unique identifer tag string from the low data structure
    """
    return "{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}".format(low)


def trim_req(req: dict[str, Any]) -> dict[str, Any]:
    """
    Trim any function off of a requisite reference
    """
    reqfirst, valfirst = next(iter(req.items()))
    if "." in reqfirst:
        return {reqfirst.split(".", maxsplit=1)[0]: valfirst}
    return req


class RequisiteType(str, Enum):
    """Types of direct requisites"""

    # Once salt no longer needs to support python < 3.10,
    # remove this hack and use @staticmethod
    @staticmethod_hack
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[Any]
    ) -> tuple[str, int]:
        return name.lower(), count

    def __new__(cls, value, weight):
        member = str.__new__(cls, value)
        member._value_ = value
        member.weight = weight
        return member

    def __init__(self, value, weight):
        super().__init__()
        self._value_ = value
        self.weight = weight

    # The items here are listed in order of precedence for determining
    # the order of execution, so do not change the order unless you
    # are intentionally changing the precedence
    ONFAIL = auto()
    ONFAIL_ANY = auto()
    ONFAIL_ALL = auto()
    REQUIRE = auto()
    REQUIRE_ANY = auto()
    ONCHANGES = auto()
    ONCHANGES_ANY = auto()
    WATCH = auto()
    WATCH_ANY = auto()
    PREREQ = auto()
    PREREQUIRED = auto()
    LISTEN = auto()


class DependencyGraph:
    """
    Class used to track dependencies (requisites) among salt states.

    This class utilizes a Directed Acyclic Graph to determine the
    ordering of states. The nodes represent the individual states that
    can be depended on and edges represent the types of requisites
    between the states.
    """

    __slots__ = ("dag", "nodes_lookup_map", "sls_to_nodes")

    def __init__(self) -> None:
        self.dag = nx.MultiDiGraph()
        # a mapping to node_id to be able to find nodes with
        # specific state type (module name), names, and/or IDs
        self.nodes_lookup_map: dict[tuple[str, str], set[str]] = {}
        self.sls_to_nodes: dict[str, set[str]] = {}

    def _add_prereq(self, node_tag: str, req_tag: str):
        # the prerequiring chunk is the state declaring the prereq
        # requisite; the prereq/prerequired state is the one that is
        # declared in the requisite prereq statement
        self.dag.nodes[node_tag]["chunk"]["__prerequiring__"] = True
        prereq_chunk = self.dag.nodes[req_tag]["chunk"]
        # set __prereq__ true to run the state in test mode
        prereq_chunk["__prereq__"] = True
        prereq_check_node = self._get_prereq_node_tag(req_tag)
        if not self.dag.nodes.get(prereq_check_node):
            self.dag.add_node(
                prereq_check_node, chunk=prereq_chunk, state=prereq_chunk["state"]
            )
            # all the dependencies of the node for the prerequired
            # chunk also need to be applied to its prereq check node
            for dependency_node, _, req_type, data in self.dag.in_edges(
                req_tag, data=True, keys=True
            ):
                if req_type != RequisiteType.PREREQ:
                    self.dag.add_edge(
                        dependency_node, prereq_check_node, req_type, **data
                    )
        self.dag.add_edge(prereq_check_node, node_tag, RequisiteType.PREREQ)
        self.dag.add_edge(node_tag, req_tag, RequisiteType.REQUIRE)

    def _add_reqs(
        self,
        node_tag: str,
        has_preq_node: bool,
        req_type: RequisiteType,
        req_tags: Iterable[str],
    ) -> None:
        for req_tag in req_tags:
            if req_type == RequisiteType.PREREQ:
                self._add_prereq(node_tag, req_tag)
            else:
                if has_preq_node:
                    # if the low chunk is set to run in test mode for a
                    # prereq check then also add the requisites to the
                    # prereq node.
                    prereq_node_tag = self._get_prereq_node_tag(node_tag)
                    self.dag.add_edge(req_tag, prereq_node_tag, key=req_type)
                self.dag.add_edge(req_tag, node_tag, key=req_type)

    def _copy_edges(self, source: str, dest: str) -> None:
        """Add the edges from source node to dest node"""
        for dependency, _, req_type, data in self.dag.in_edges(
            source, data=True, keys=True
        ):
            self.dag.add_edge(dependency, dest, req_type, **data)
        for _, dependent, req_type, data in self.dag.out_edges(
            source, data=True, keys=True
        ):
            self.dag.add_edge(dest, dependent, req_type, **data)

    def _get_chunk_order(self, cap: int, node: str) -> tuple[int | float, int | float]:
        dag = self.dag
        stack: list[tuple[str, bool, int | float, int | float]] = [
            # node, is_processing_children, child_min, req_order
            (node, False, float("inf"), float("-inf"))
        ]
        order = cap
        while stack:
            node, is_processing_children, child_min, req_order = stack[-1]
            node_data = dag.nodes[node]
            chunk = node_data.get("chunk", {})
            if not is_processing_children:  # initial stage
                order = chunk.get("order")
                if order is None or not isinstance(order, (int, float)):
                    if order == "last":
                        order = cap + 1000000
                    elif order == "first":
                        order = 0
                    else:
                        order = cap
                    chunk["order"] = order
                name_order = chunk.pop("name_order", 0)
                if name_order:
                    order += name_order / 10000.0
                    chunk["order"] = order
                if order < 0:
                    order += cap + 1000000
                    chunk["order"] = order
                stack.pop()
                # update stage
                stack.append((node, True, child_min, req_order))
            else:  # after processing node
                child_min_node = node_data.get("child_min")
                if child_min_node is None:
                    for _, child, req_type in dag.out_edges(node, keys=True):
                        if req_order <= req_type.weight:
                            req_order = req_type.weight
                            child_order = (
                                dag.nodes[child]
                                .get("chunk", {})
                                .get("order", float("inf"))
                            )
                            child_min = min(child_min, child_order)
                    node_data["child_min"] = child_min
                    if order > child_min:
                        order = child_min
                stack.pop()
        return (order, chunk["order"])

    def _get_prereq_node_tag(self, low_tag: str):
        return f"{low_tag}_|-__prereq_test__"

    def _is_fnmatch_pattern(self, value: str) -> bool:
        return any(char in value for char in ("*", "?", "[", "]"))

    def _chunk_str(self, chunk: LowChunk) -> str:
        node_dict = {
            "SLS": chunk["__sls__"],
            "ID": chunk["__id__"],
        }
        if chunk["__id__"] != chunk["name"]:
            node_dict["NAME"] = chunk["name"]
        return str(node_dict)

    def add_chunk(self, low: LowChunk, allow_aggregate: bool) -> None:
        node_id = _gen_tag(low)
        self.dag.add_node(
            node_id, allow_aggregate=allow_aggregate, chunk=low, state=low["state"]
        )
        self.nodes_lookup_map.setdefault((low["state"], low["name"]), set()).add(
            node_id
        )
        self.nodes_lookup_map.setdefault((low["state"], low["__id__"]), set()).add(
            node_id
        )
        self.nodes_lookup_map.setdefault(("id", low["__id__"]), set()).add(node_id)
        self.nodes_lookup_map.setdefault(("id", low["name"]), set()).add(node_id)
        if sls := low.get("__sls__"):
            self.sls_to_nodes.setdefault(sls, set()).add(node_id)
        if sls_included_from := low.get("__sls_included_from__"):
            for sls in sls_included_from:
                self.sls_to_nodes.setdefault(sls, set()).add(node_id)

    def add_dependency(
        self, low: LowChunk, req_type: RequisiteType, req_key: str, req_val: str
    ) -> bool:
        found = False
        has_prereq_node = low.get("__prereq__", False)
        if req_key == "sls":
            # Allow requisite tracking of entire sls files
            if self._is_fnmatch_pattern(req_val):
                found = True
                node_tag = _gen_tag(low)
                for sls, req_tags in self.sls_to_nodes.items():
                    if fnmatch.fnmatch(sls, req_val):
                        found = True
                        self._add_reqs(node_tag, has_prereq_node, req_type, req_tags)
            else:
                node_tag = _gen_tag(low)
                if req_tags := self.sls_to_nodes.get(req_val, []):
                    found = True
                    self._add_reqs(node_tag, has_prereq_node, req_type, req_tags)
        elif self._is_fnmatch_pattern(req_val):
            # This iterates over every chunk to check
            # if any match instead of doing a look up since
            # it has to support wildcard matching.
            node_tag = _gen_tag(low)
            for (state_type, name_or_id), req_tags in self.nodes_lookup_map.items():
                if req_key == state_type and (fnmatch.fnmatch(name_or_id, req_val)):
                    found = True
                    self._add_reqs(node_tag, has_prereq_node, req_type, req_tags)
        elif req_tags := self.nodes_lookup_map.get((req_key, req_val)):
            found = True
            node_tag = _gen_tag(low)
            self._add_reqs(node_tag, has_prereq_node, req_type, req_tags)
        return found

    def add_requisites(self, low: LowChunk, disabled_reqs: Sequence[str]) -> str | None:
        """
        Add all the dependency requisites of the low chunk as edges to the DAG
        :return: an error string if there was an error otherwise None
        """
        present = False
        for req_type in RequisiteType:
            if req_type.value in low:
                present = True
                break
        if not present:
            return None
        reqs = {
            rtype: []
            for rtype in (
                RequisiteType.REQUIRE,
                RequisiteType.REQUIRE_ANY,
                RequisiteType.WATCH,
                RequisiteType.WATCH_ANY,
                RequisiteType.PREREQ,
                RequisiteType.ONFAIL,
                RequisiteType.ONFAIL_ANY,
                RequisiteType.ONFAIL_ALL,
                RequisiteType.ONCHANGES,
                RequisiteType.ONCHANGES_ANY,
            )
        }
        for r_type in reqs:
            if low_reqs := low.get(r_type.value):
                if r_type in disabled_reqs:
                    log.warning("The %s requisite has been disabled, Ignoring.", r_type)
                    continue
                for req_ref in low_reqs:
                    if isinstance(req_ref, str):
                        req_ref = {"id": req_ref}
                    req_ref = trim_req(req_ref)
                    # req_key: match state module name
                    # req_val: match state id or name
                    req_key, req_val = next(iter(req_ref.items()))
                    if req_val is None:
                        continue
                    if not isinstance(req_val, str):
                        return (
                            f"Requisite [{r_type}: {req_key}] in state"
                            f" [{low['name']}] in SLS [{low.get('__sls__')}]"
                            " must have a string as the value"
                        )
                    found = self.add_dependency(low, r_type, req_key, req_val)
                    if not found:
                        return (
                            "Referenced state does not exist"
                            f" for requisite [{r_type}: ({req_key}: {req_val})] in state"
                            f" [{low['name']}] in SLS [{low.get('__sls__')}]"
                        )
        return None

    def aggregate_and_order_chunks(self, cap: int) -> list[LowChunk]:
        """
        Aggregate eligible nodes in the dependencies graph.

        Return a list of the chunks in the sorted order in which the
        chunks should be executed.
        Nodes are eligible for aggregation if the state function in the
        chunks match and aggregation is enabled in the configuration for
        the state function.
        :param cap: the maximum order value configured in the states
        :return: the ordered chunks
        """
        dag: nx.MultiDiGraph = self.dag
        # dict for tracking topo order and for mapping each node that
        # was aggregated to the aggregated node that replaces it
        topo_order = {}

        max_group_size = 500
        groups_by_type = defaultdict(list)

        def _get_order(node):
            chunk = dag.nodes[node].get("chunk", {})
            chunk_label = "{0[state]}{0[name]}{0[fun]}".format(chunk) if chunk else ""
            chunk_order = self._get_chunk_order(cap, node)
            return (chunk_order, chunk_label)

        # Iterate over the nodes in topological order to get the correct
        # ordering which takes requisites into account
        for node in nx.lexicographical_topological_sort(dag, key=_get_order):
            topo_order[node] = None
            data = dag.nodes[node]
            if not data.get("allow_aggregate"):
                continue

            node_type = data["state"]
            added = False
            for idx, group in enumerate(groups_by_type[node_type]):
                if len(group) >= max_group_size:
                    continue
                # Check if the node can be reached from any node in the group
                first_node = next(iter(group))
                agg_node = topo_order.get(first_node)
                # Since we are iterating in topological order we know
                # that there is no path from the current node to the
                # node in the group; so we only need to check the path
                # from the group node to the current node
                reachable = nx.has_path(dag, agg_node or first_node, node)
                if not reachable:
                    # If not, add the node to the group
                    if agg_node is None:
                        # there is now more than one node for this
                        # group so aggregate them
                        agg_node = f"__aggregate_{node_type}_{idx}__"
                        dag.add_node(
                            agg_node, state=node_type, aggregated_nodes=group.keys()
                        )
                        # add the edges of the first node in the group to
                        # the aggregate
                        self._copy_edges(first_node, agg_node)
                        dag.nodes[first_node]["aggregate"] = agg_node
                        topo_order[first_node] = agg_node

                    self._copy_edges(node, agg_node)
                    dag.nodes[node]["aggregate"] = agg_node
                    topo_order[node] = agg_node
                    group[node] = None
                    added = True
                    break

            # If the node was not added to any set, create a new set
            if not added:
                # use a dict instead of set to retain insertion ordering
                groups_by_type[node_type].append({node: None})

        ordered_chunks = [dag.nodes[node].get("chunk", {}) for node in topo_order]
        return ordered_chunks

    def find_cycle_edges(self) -> list[tuple[LowChunk, RequisiteType, LowChunk]]:
        """
        Find the cycles if the graph is not a Directed Acyclic Graph
        """
        dag = self.dag
        try:
            cycle_edges = []
            for dependency, dependent, req_type in nx.find_cycle(dag):
                dependency_chunk = self.dag.nodes[dependency]["chunk"]
                dependent_chunk = self.dag.nodes[dependent]["chunk"]
                if (
                    req_type not in dependent_chunk
                    and req_type == RequisiteType.REQUIRE
                ):
                    # show the original prereq requisite for the require edges
                    # added for the prereq
                    req_type = RequisiteType.PREREQ
                cycle_edges.append((dependent_chunk, req_type, dependency_chunk))
            return cycle_edges
        except nx.NetworkXNoCycle:
            # If the graph is a DAG, return an empty list
            return []

    def get_aggregate_chunks(self, low: LowChunk) -> list[LowChunk]:
        """
        Get the chunks that were set to be valid for aggregation with
        this low chunk.
        """
        low_tag = _gen_tag(low)
        if aggregate_node := self.dag.nodes[low_tag].get("aggregate"):
            return [
                self.dag.nodes[node]["chunk"]
                for node in self.dag.nodes[aggregate_node]["aggregated_nodes"]
            ]
        return []

    def get_cycles_str(self) -> str:
        cycle_edges = [
            f"({self._chunk_str(dependency)}, '{req_type.value}', {self._chunk_str(dependent)})"
            for dependency, req_type, dependent in self.find_cycle_edges()
        ]
        return ", ".join(cycle_edges)

    def get_dependencies(
        self, low: LowChunk
    ) -> Generator[tuple[RequisiteType, LowChunk], None, None]:
        """Get the requisite type and low chunk for each dependency of low"""
        low_tag = _gen_tag(low)
        if low.get("__prereq__"):
            # if the low chunk is set to run in test mode for a
            # prereq check then return the reqs for prereq test node.
            low_tag = self._get_prereq_node_tag(low_tag)
        for req_id, _, req_type in self.dag.in_edges(low_tag, keys=True):
            if chunk := self.dag.nodes[req_id].get("chunk"):
                yield req_type, chunk
            else:
                for node in self.dag.nodes[req_id]["aggregated_nodes"]:
                    yield req_type, self.dag.nodes[node].get("chunk")
