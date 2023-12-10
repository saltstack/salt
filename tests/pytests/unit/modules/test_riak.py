"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.riak
"""

import pytest

import salt.modules.riak as riak
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {riak: {}}


def test_start():
    """
    Test for start Riak
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.start() == {"success": True, "comment": "success"}


def test_stop():
    """
    Test for stop Riak
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.stop() == {"success": True, "comment": "success"}


def test_cluster_join():
    """
    Test for Join a Riak cluster
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.cluster_join("A", "B") == {"success": True, "comment": "success"}


def test_cluster_leave():
    """
    Test for leaving a Riak cluster
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.cluster_leave("A", "B") == {"success": True, "comment": "success"}


def test_cluster_plan():
    """
    Test for Review Cluster Plan
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.cluster_plan()


def test_cluster_commit():
    """
    Test for Commit Cluster Changes
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.cluster_commit() == {"success": True, "comment": "success"}


def test_member_status():
    """
    Test for Get cluster member status
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"stdout": "A:a/B:b\nC:c/D:d"}
    ):
        assert riak.member_status() == {
            "membership": {},
            "summary": {
                "A": "a",
                "C": "c",
                "B": "b",
                "D": "d",
                "Exiting": 0,
                "Down": 0,
                "Valid": 0,
                "Leaving": 0,
                "Joining": 0,
            },
        }


def test_status():
    """
    Test status information
    """
    ret = {"stdout": "vnode_map_update_time_95 : 0\nvnode_map_update_time_99 : 0"}

    with patch.object(riak, "__execute_cmd", return_value=ret):
        assert riak.status() == {
            "vnode_map_update_time_95": "0",
            "vnode_map_update_time_99": "0",
        }


def test_test():
    """
    Test the Riak test
    """
    with patch.object(
        riak, "__execute_cmd", return_value={"retcode": 0, "stdout": "success"}
    ):
        assert riak.test() == {"success": True, "comment": "success"}


def test_services():
    """
    Test Riak Service List
    """
    with patch.object(riak, "__execute_cmd", return_value={"stdout": "[a,b,c]"}):
        assert riak.services() == ["a", "b", "c"]
