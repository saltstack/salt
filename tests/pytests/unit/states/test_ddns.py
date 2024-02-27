"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.ddns as ddns
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ddns: {}}


def test_present():
    """
    Test to ensures that the named DNS record is present with the given ttl.
    """
    name = "webserver"
    zone = "example.com"
    ttl = "60"
    data = "111.222.333.444"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(ddns.__opts__, {"test": True}):
        comt = f'A record "{name}" will be updated'
        ret.update({"comment": comt})
        assert ddns.present(name, zone, ttl, data) == ret

        with patch.dict(ddns.__opts__, {"test": False}):
            mock = MagicMock(return_value=None)
            with patch.dict(ddns.__salt__, {"ddns.update": mock}):
                comt = f'A record "{name}" already present with ttl of {ttl}'
                ret.update({"comment": comt, "result": True})
                assert ddns.present(name, zone, ttl, data) == ret


def test_absent():
    """
    Test to ensures that the named DNS record is absent.
    """
    name = "webserver"
    zone = "example.com"
    data = "111.222.333.444"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(ddns.__opts__, {"test": True}):
        comt = f'None record "{name}" will be deleted'
        ret.update({"comment": comt})
        assert ddns.absent(name, zone, data) == ret

        with patch.dict(ddns.__opts__, {"test": False}):
            mock = MagicMock(return_value=None)
            with patch.dict(ddns.__salt__, {"ddns.delete": mock}):
                comt = "No matching DNS record(s) present"
                ret.update({"comment": comt, "result": True})
                assert ddns.absent(name, zone, data) == ret
