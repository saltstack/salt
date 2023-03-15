"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.modjk_worker as modjk_worker
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {modjk_worker: {}}


def test_stop():
    """
    Test to stop the named worker from the lbn load balancers
     at the targeted minions.
    """
    name = "{{ grains['id'] }}"
    lbn = "application"
    target = "roles:balancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "no servers answered the published command modjk.worker_status"
    mock = MagicMock(return_value=False)
    with patch.dict(modjk_worker.__salt__, {"publish.publish": mock}):
        ret.update({"comment": comt})
        assert modjk_worker.stop(name, lbn, target) == ret


def test_activate():
    """
    Test to activate the named worker from the lbn load balancers
     at the targeted minions.
    """
    name = "{{ grains['id'] }}"
    lbn = "application"
    target = "roles:balancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "no servers answered the published command modjk.worker_status"
    mock = MagicMock(return_value=False)
    with patch.dict(modjk_worker.__salt__, {"publish.publish": mock}):
        ret.update({"comment": comt})
        assert modjk_worker.activate(name, lbn, target) == ret


def test_disable():
    """
    Test to disable the named worker from the lbn load balancers
     at the targeted minions.
    """
    name = "{{ grains['id'] }}"
    lbn = "application"
    target = "roles:balancer"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "no servers answered the published command modjk.worker_status"
    mock = MagicMock(return_value=False)
    with patch.dict(modjk_worker.__salt__, {"publish.publish": mock}):
        ret.update({"comment": comt})
        assert modjk_worker.disable(name, lbn, target) == ret
