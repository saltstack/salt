"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.modjk as modjk
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {modjk: {}}


def test_version():
    """
    Test for return the modjk version
    """
    with patch.object(
        modjk, "_do_http", return_value={"worker.jk_version": "mod_jk/1.2.37"}
    ):
        assert modjk.version() == "1.2.37"


def test_get_running():
    """
    Test for get the current running config (not from disk)
    """
    with patch.object(modjk, "_do_http", return_value={}):
        assert modjk.get_running() == {}


def test_dump_config():
    """
    Test for dump the original configuration that was loaded from disk
    """
    with patch.object(modjk, "_do_http", return_value={}):
        assert modjk.dump_config() == {}


def test_list_configured_members():
    """
    Test for return a list of member workers from the configuration files
    """
    with patch.object(modjk, "_do_http", return_value={}):
        assert modjk.list_configured_members("loadbalancer1") == []

    with patch.object(
        modjk,
        "_do_http",
        return_value={"worker.loadbalancer1.balance_workers": "SALT"},
    ):
        assert modjk.list_configured_members("loadbalancer1") == ["SALT"]


def test_workers():
    """
    Test for return a list of member workers and their status
    """
    with patch.object(modjk, "_do_http", return_value={"worker.list": "Salt1,Salt2"}):
        assert modjk.workers() == {}


def test_recover_all():
    """
    Test for set the all the workers in lbn to recover and
    activate them if they are not
    """
    with patch.object(modjk, "_do_http", return_value={}):
        assert modjk.recover_all("loadbalancer1") == {}

    with patch.object(
        modjk,
        "_do_http",
        return_value={"worker.loadbalancer1.balance_workers": "SALT"},
    ):
        with patch.object(
            modjk,
            "worker_status",
            return_value={"activation": "ACT", "state": "OK"},
        ):
            assert modjk.recover_all("loadbalancer1") == {
                "SALT": {"activation": "ACT", "state": "OK"}
            }


def test_reset_stats():
    """
    Test for reset all runtime statistics for the load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.reset_stats("loadbalancer1")


def test_lb_edit():
    """
    Test for edit the loadbalancer settings
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.lb_edit("loadbalancer1", {"vlr": 1, "vlt": 60})


def test_bulk_stop():
    """
    Test for stop all the given workers in the specific load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.bulk_stop(["node1", "node2", "node3"], "loadbalancer1")


def test_bulk_activate():
    """
    Test for activate all the given workers in the specific load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.bulk_activate(["node1", "node2", "node3"], "loadbalancer1")


def test_bulk_disable():
    """
    Test for disable all the given workers in the specific load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.bulk_disable(["node1", "node2", "node3"], "loadbalancer1")


def test_bulk_recover():
    """
    Test for recover all the given workers in the specific load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.bulk_recover(["node1", "node2", "node3"], "loadbalancer1")


def test_worker_status():
    """
    Test for return the state of the worker
    """
    with patch.object(
        modjk,
        "_do_http",
        return_value={"worker.node1.activation": "ACT", "worker.node1.state": "OK"},
    ):
        assert modjk.worker_status("node1") == {"activation": "ACT", "state": "OK"}

    with patch.object(modjk, "_do_http", return_value={}):
        assert not modjk.worker_status("node1")


def test_worker_recover():
    """
    Test for set the worker to recover this module will fail
    if it is in OK state
    """
    with patch.object(modjk, "_do_http", return_value={}):
        assert modjk.worker_recover("node1", "loadbalancer1") == {}


def test_worker_disable():
    """
    Test for set the worker to disable state in the lbn load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.worker_disable("node1", "loadbalancer1")


def test_worker_activate():
    """
    Test for set the worker to activate state in the lbn load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.worker_activate("node1", "loadbalancer1")


def test_worker_stop():
    """
    Test for set the worker to stopped state in the lbn load balancer
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.worker_stop("node1", "loadbalancer1")


def test_worker_edit():
    """
    Test for edit the worker settings
    """
    with patch.object(modjk, "_do_http", return_value={"worker.result.type": "OK"}):
        assert modjk.worker_edit("node1", "loadbalancer1", {"vwf": 500, "vwd": 60})
