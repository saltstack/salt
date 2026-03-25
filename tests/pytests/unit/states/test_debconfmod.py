"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.debconfmod as debconfmod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {debconfmod: {}}


def test_set_file():
    """
    Test to set debconf selections from a file or a template
    """
    name = "nullmailer"
    source = "salt://pathto/pkg.selections"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Context must be formed as a dict"
    ret.update({"comment": comt})
    assert debconfmod.set_file(name, source, context="salt") == ret

    comt = "Defaults must be formed as a dict"
    ret.update({"comment": comt})
    assert debconfmod.set_file(name, source, defaults="salt") == ret

    with patch.dict(debconfmod.__opts__, {"test": True}):
        comt = "Debconf selections would have been set."
        ret.update({"comment": comt, "result": None})
        assert debconfmod.set_file(name, source) == ret

        with patch.dict(debconfmod.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(debconfmod.__salt__, {"debconf.set_file": mock}):
                comt = "Debconf selections were set."
                ret.update({"comment": comt, "result": True})
                assert debconfmod.set_file(name, source) == ret


def test_set():
    """
    Test to set debconf selections
    """
    name = "nullmailer"
    data = {
        "shared/mailname": {"type": "string", "value": "server.domain.tld"},
        "nullmailer/relayhost": {"type": "string", "value": "mail.domain.tld"},
    }

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    changes = {
        "nullmailer/relayhost": "New value: mail.domain.tld",
        "shared/mailname": "New value: server.domain.tld",
    }

    mock = MagicMock(return_value=None)
    with patch.dict(debconfmod.__salt__, {"debconf.show": mock}):
        with patch.dict(debconfmod.__opts__, {"test": True}):
            ret.update({"changes": changes})
            assert debconfmod.set(name, data) == ret
