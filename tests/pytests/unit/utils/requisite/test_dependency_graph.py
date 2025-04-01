"""
Test functions in state.py that are not a part of a class
"""

import pytest

import salt.utils.requisite

pytestmark = [
    pytest.mark.core_test,
]


def test_ordering():
    """
    Testing that ordering chunks results in the expected order honoring
    requistes and order
    """
    sls = "test"
    env = "base"
    chunks = [
        {
            "__id__": "success-6",
            "name": "success-6",
            "state": "test",
            "fun": "succeed_with_changes",
        },
        {
            "__id__": "fail-0",
            "name": "fail-0",
            "state": "test",
            "fun": "fail_without_changes",
        },
        {
            "__id__": "fail-1",
            "name": "fail-1",
            "state": "test",
            "fun": "fail_without_changes",
        },
        {
            "__id__": "req-fails",
            "name": "req-fails",
            "state": "test",
            "fun": "succeed_with_changes",
            "require": ["fail-0", "fail-1"],
        },
        {
            "__id__": "success-4",
            "name": "success-4",
            "state": "test",
            "fun": "succeed_with_changes",
            "order": 4,
        },
        {
            "__id__": "success-1",
            "name": "success-1",
            "state": "test",
            "fun": "succeed_without_changes",
            "order": 1,
        },
        {
            "__id__": "success-2",
            "name": "success-2",
            "state": "test",
            "fun": "succeed_without_changes",
            "order": 2,
        },
        {
            "__id__": "success-d",
            "name": "success-d",
            "state": "test",
            "fun": "succeed_without_changes",
        },
        {
            "__id__": "success-c",
            "name": "success-c",
            "state": "test",
            "fun": "succeed_without_changes",
        },
        {
            "__id__": "success-b",
            "name": "success-b",
            "state": "test",
            "fun": "succeed_without_changes",
        },
        {
            "__id__": "success-a",
            "name": "success-a",
            "state": "test",
            "fun": "succeed_without_changes",
        },
        {
            "__id__": "success-3",
            "name": "success-3",
            "state": "test",
            "fun": "succeed_without_changes",
            "order": 3,
            "require": [{"test": "success-a"}],
            "watch": [{"test": "success-c"}],
            "onchanges": [{"test": "success-b"}],
            "listen": [{"test": "success-d"}],
        },
        {
            "__id__": "success-5",
            "name": "success-5",
            "state": "test",
            "fun": "succeed_without_changes",
            "listen": [{"test": "success-6"}],
        },
    ]
    depend_graph = salt.utils.requisite.DependencyGraph()
    for low in chunks:
        low.update(
            {
                "__env__": env,
                "__sls__": sls,
            }
        )
        depend_graph.add_chunk(low, allow_aggregate=False)
    for low in chunks:
        depend_graph.add_requisites(low, [])
    ordered_chunk_ids = [
        chunk["__id__"] for chunk in depend_graph.aggregate_and_order_chunks(100)
    ]
    expected_order = [
        "success-1",
        "success-2",
        "success-a",
        "success-b",
        "success-c",
        "success-3",
        "success-4",
        "fail-0",
        "fail-1",
        "req-fails",
        "success-5",
        "success-6",
        "success-d",
    ]
    assert expected_order == ordered_chunk_ids


def test_find_cycle_edges():
    sls = "test"
    env = "base"
    chunks = [
        {
            "__id__": "state-1",
            "name": "state-1",
            "state": "test",
            "fun": "succeed_with_changes",
            "require": [{"test": "state-2"}],
        },
        {
            "__id__": "state-2",
            "name": "state-2",
            "state": "test",
            "fun": "succeed_with_changes",
            "require": [{"test": "state-3"}],
        },
        {
            "__id__": "state-3",
            "name": "state-3",
            "state": "test",
            "fun": "succeed_with_changes",
            "require": [{"test": "state-1"}],
        },
    ]
    depend_graph = salt.utils.requisite.DependencyGraph()
    for low in chunks:
        low.update(
            {
                "__env__": env,
                "__sls__": sls,
            }
        )
        depend_graph.add_chunk(low, allow_aggregate=False)
    for low in chunks:
        depend_graph.add_requisites(low, [])
    expected_cycle_edges = [
        (
            {
                "__env__": "base",
                "__id__": "state-3",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-3",
                "require": [{"test": "state-1"}],
                "state": "test",
            },
            "require",
            {
                "__env__": "base",
                "__id__": "state-1",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-1",
                "require": [{"test": "state-2"}],
                "state": "test",
            },
        ),
        (
            {
                "__env__": "base",
                "__id__": "state-2",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-2",
                "require": [{"test": "state-3"}],
                "state": "test",
            },
            "require",
            {
                "__env__": "base",
                "__id__": "state-3",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-3",
                "require": [{"test": "state-1"}],
                "state": "test",
            },
        ),
        (
            {
                "__env__": "base",
                "__id__": "state-1",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-1",
                "require": [{"test": "state-2"}],
                "state": "test",
            },
            "require",
            {
                "__env__": "base",
                "__id__": "state-2",
                "__sls__": "test",
                "fun": "succeed_with_changes",
                "name": "state-2",
                "require": [{"test": "state-3"}],
                "state": "test",
            },
        ),
    ]
    cycle_edges = depend_graph.find_cycle_edges()
    assert expected_cycle_edges == cycle_edges


def test_get_aggregate_chunks():
    sls = "test"
    env = "base"
    chunks = [
        {
            "__id__": "packages-1",
            "name": "packages-1",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["hello"],
        },
        {
            "__id__": "packages-2",
            "name": "packages-2",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay", "fortune-mod"],
            "require": ["requirement"],
        },
        {
            "__id__": "packages-3",
            "name": "packages-3",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["figlet"],
            "require": ["requirement"],
        },
        {
            "__id__": "requirement",
            "name": "requirement",
            "state": "test",
            "fun": "nop",
        },
        {
            "__id__": "packages-4",
            "name": "packages-4",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay"],
        },
        {
            "__id__": "packages-5",
            "name": "packages-5",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["sl"],
            "require": ["packages-4"],
        },
    ]
    depend_graph = salt.utils.requisite.DependencyGraph()
    for low in chunks:
        low.update(
            {
                "__env__": env,
                "__sls__": sls,
            }
        )
        depend_graph.add_chunk(low, allow_aggregate=True)
    for low in chunks:
        depend_graph.add_requisites(low, [])
    depend_graph.aggregate_and_order_chunks(100)
    expected_aggregates = [
        (chunks[0], ["packages-1", "packages-4", "packages-2", "packages-3"]),
        (chunks[1], ["packages-1", "packages-4", "packages-2", "packages-3"]),
        (chunks[2], ["packages-1", "packages-4", "packages-2", "packages-3"]),
        (chunks[3], []),
        (chunks[4], ["packages-1", "packages-4", "packages-2", "packages-3"]),
        (chunks[5], []),
    ]
    for low, expected_aggregate_ids in expected_aggregates:
        aggregated_ids = [
            chunk["__id__"] for chunk in depend_graph.get_aggregate_chunks(low)
        ]
        assert expected_aggregate_ids == aggregated_ids


def test_get_dependencies():
    sls = "test"
    env = "base"
    chunks = [
        {
            "__id__": "packages-1",
            "name": "packages-1",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["hello"],
        },
        {
            "__id__": "packages-2",
            "name": "packages-2",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay", "fortune-mod"],
            "require": ["requirement"],
        },
        {
            "__id__": "packages-3",
            "name": "packages-3",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["figlet"],
            "require": ["requirement"],
        },
        {
            "__id__": "requirement",
            "name": "requirement",
            "state": "test",
            "fun": "nop",
        },
        {
            "__id__": "packages-4",
            "name": "packages-4",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay"],
        },
        {
            "__id__": "packages-5",
            "name": "packages-5",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["sl"],
            "require": ["packages-4"],
        },
    ]
    depend_graph = salt.utils.requisite.DependencyGraph()
    for low in chunks:
        low.update(
            {
                "__env__": env,
                "__sls__": sls,
            }
        )
        depend_graph.add_chunk(low, allow_aggregate=False)
    for low in chunks:
        depend_graph.add_requisites(low, [])
    depend_graph.aggregate_and_order_chunks(100)
    expected_aggregates = [
        (chunks[0], []),
        (chunks[1], [(salt.utils.requisite.RequisiteType.REQUIRE, "requirement")]),
        (chunks[2], [(salt.utils.requisite.RequisiteType.REQUIRE, "requirement")]),
        (chunks[3], []),
        (chunks[4], []),
        (chunks[5], [(salt.utils.requisite.RequisiteType.REQUIRE, "packages-4")]),
    ]
    for low, expected_dependency_tuples in expected_aggregates:
        depend_tuples = [
            (req_type, chunk["__id__"])
            for (req_type, chunk) in depend_graph.get_dependencies(low)
        ]
        assert expected_dependency_tuples == depend_tuples


def test_get_dependencies_when_aggregated():
    sls = "test"
    env = "base"
    chunks = [
        {
            "__id__": "packages-1",
            "name": "packages-1",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["hello"],
        },
        {
            "__id__": "packages-2",
            "name": "packages-2",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay", "fortune-mod"],
            "require": ["requirement"],
        },
        {
            "__id__": "packages-3",
            "name": "packages-3",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["figlet"],
            "require": ["requirement"],
        },
        {
            "__id__": "requirement",
            "name": "requirement",
            "state": "test",
            "fun": "nop",
        },
        {
            "__id__": "packages-4",
            "name": "packages-4",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["cowsay"],
        },
        {
            "__id__": "packages-5",
            "name": "packages-5",
            "state": "pkg",
            "fun": "installed",
            "pkgs": ["sl"],
            "require": ["packages-4"],
        },
    ]
    depend_graph = salt.utils.requisite.DependencyGraph()
    for low in chunks:
        low.update(
            {
                "__env__": env,
                "__sls__": sls,
            }
        )
        depend_graph.add_chunk(low, allow_aggregate=True)
    for low in chunks:
        depend_graph.add_requisites(low, [])
    depend_graph.aggregate_and_order_chunks(100)
    expected_aggregates = [
        (chunks[0], []),
        (chunks[1], [(salt.utils.requisite.RequisiteType.REQUIRE, "requirement")]),
        (chunks[2], [(salt.utils.requisite.RequisiteType.REQUIRE, "requirement")]),
        (chunks[3], []),
        (chunks[4], []),
        (
            chunks[5],
            [
                (salt.utils.requisite.RequisiteType.REQUIRE, "packages-4"),
                (salt.utils.requisite.RequisiteType.REQUIRE, "packages-1"),
                (salt.utils.requisite.RequisiteType.REQUIRE, "packages-4"),
                (salt.utils.requisite.RequisiteType.REQUIRE, "packages-2"),
                (salt.utils.requisite.RequisiteType.REQUIRE, "packages-3"),
            ],
        ),
    ]
    for low, expected_dependency_tuples in expected_aggregates:
        depend_tuples = [
            (req_type, chunk["__id__"])
            for (req_type, chunk) in depend_graph.get_dependencies(low)
        ]
        assert expected_dependency_tuples == depend_tuples
