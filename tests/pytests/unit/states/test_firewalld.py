"""
    :codeauthor: Hristo Voyvodov <hristo.voyvodov@redsift.io>
"""

import pytest

import salt.states.firewalld as firewalld
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {firewalld: {"__opts__": {"test": False}}}


def test_masquerade():
    firewalld_reload_rules = MagicMock(return_value={})
    firewalld_get_zones = MagicMock(
        return_value=[
            "block",
            "public",
        ]
    )
    firewalld_get_masquerade = MagicMock(return_value=True)
    firewalld_remove_masquerade = MagicMock(return_value={})

    __salt__ = {
        "firewalld.reload_rules": firewalld_reload_rules,
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.get_masquerade": firewalld_get_masquerade,
        "firewalld.remove_masquerade": firewalld_remove_masquerade,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.present("public")
        assert ret == {
            "changes": {},
            "result": True,
            "comment": "'public' is already in the desired state.",
            "name": "public",
        }

        ret = firewalld.present("public", masquerade=False)
        assert ret == {
            "changes": {
                "masquerade": {
                    "old": True,
                    "new": "Masquerading successfully disabled.",
                }
            },
            "result": True,
            "comment": "'public' was configured.",
            "name": "public",
        }

        ret = firewalld.present("public", masquerade=True)
        assert ret == {
            "changes": {},
            "result": True,
            "comment": "'public' is already in the desired state.",
            "name": "public",
        }
