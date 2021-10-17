"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.supervisord as supervisord
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {supervisord: {}}


def test_running():
    """
    Test to ensure the named service is running.
    """
    name = "wsgi_server"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    comt = "Supervisord module not activated. Do you need to install supervisord?"
    ret.update({"comment": comt, "result": False})
    assert supervisord.running(name) == ret

    mock = MagicMock(return_value={name: {"state": "running"}})
    with patch.dict(supervisord.__salt__, {"supervisord.status": mock}):
        with patch.dict(supervisord.__opts__, {"test": True}):
            comt = "Service wsgi_server is already running"
            ret.update({"comment": comt, "result": True})
            assert supervisord.running(name) == ret

        with patch.dict(supervisord.__opts__, {"test": False}):
            comt = "Not starting already running service: wsgi_server"
            ret.update({"comment": comt})
            assert supervisord.running(name) == ret


def test_dead():
    """
    Test to ensure the named service is dead (not running).
    """
    name = "wsgi_server"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(supervisord.__opts__, {"test": True}):
        comt = "Service {} is set to be stopped".format(name)
        ret.update({"comment": comt})
        assert supervisord.dead(name) == ret


def test_mod_watch():
    """
    Test to always restart on watch.
    """
    name = "wsgi_server"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    comt = "Supervisord module not activated. Do you need to install supervisord?"
    ret.update({"comment": comt, "result": False})
    assert supervisord.mod_watch(name) == ret
