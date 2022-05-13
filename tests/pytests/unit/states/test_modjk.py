"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.modjk as modjk


@pytest.fixture
def list_not_str():
    return "workers should be a list not a <class 'str'>"


def test_worker_stopped(list_not_str):
    """
    Test to stop all the workers in the modjk load balancer
    """
    name = "loadbalancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    ret.update({"comment": list_not_str})
    assert modjk.worker_stopped(name, "app1") == ret


def test_worker_activated(list_not_str):
    """
    Test to activate all the workers in the modjk load balancer
    """
    name = "loadbalancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    ret.update({"comment": list_not_str})
    assert modjk.worker_activated(name, "app1") == ret


def test_worker_disabled(list_not_str):
    """
    Test to disable all the workers in the modjk load balancer
    """
    name = "loadbalancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    ret.update({"comment": list_not_str})
    assert modjk.worker_disabled(name, "app1") == ret


def test_worker_recover(list_not_str):
    """
    Test to recover all the workers in the modjk load balancer
    """
    name = "loadbalancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    ret.update({"comment": list_not_str})
    assert modjk.worker_recover(name, "app1") == ret
