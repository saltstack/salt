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


def test_zone_absent_zone_exists():
    """
    zone_absent removes a zone that currently exists.
    """
    firewalld_get_zones = MagicMock(return_value=["public", "myzone"])
    firewalld_delete_zone = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.delete_zone": firewalld_delete_zone,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.zone_absent("myzone")
        assert ret == {
            "name": "myzone",
            "result": True,
            "changes": {},
            "comment": "'myzone' has been deleted.",
        }
        firewalld_delete_zone.assert_called_once_with("myzone", True)


def test_zone_absent_zone_does_not_exist():
    """
    zone_absent is a no-op when the zone does not exist.
    """
    firewalld_get_zones = MagicMock(return_value=["public"])

    __salt__ = {
        "firewalld.get_zones": firewalld_get_zones,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.zone_absent("myzone")
        assert ret == {
            "name": "myzone",
            "result": True,
            "changes": {},
            "comment": "'myzone' does not exist.",
        }


def test_zone_absent_test_mode():
    """
    zone_absent in test mode reports the zone would be deleted without acting.
    """
    firewalld_get_zones = MagicMock(return_value=["public", "myzone"])
    firewalld_delete_zone = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.delete_zone": firewalld_delete_zone,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        with patch.dict(firewalld.__opts__, {"test": True}):
            ret = firewalld.zone_absent("myzone")
            assert ret == {
                "name": "myzone",
                "result": None,
                "changes": {},
                "comment": "'myzone' exists, it will be deleted.",
            }
            firewalld_delete_zone.assert_not_called()


def test_service_absent_service_exists():
    """
    service_absent removes a service that currently exists.
    """
    firewalld_get_services = MagicMock(return_value=["http", "mysvc"])
    firewalld_delete_service = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.get_services": firewalld_get_services,
        "firewalld.delete_service": firewalld_delete_service,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.service_absent("mysvc")
        assert ret == {
            "name": "mysvc",
            "result": True,
            "changes": {},
            "comment": "'mysvc' has been deleted.",
        }
        firewalld_delete_service.assert_called_once_with("mysvc", True)


def test_service_absent_service_does_not_exist():
    """
    service_absent is a no-op when the service does not exist.
    """
    firewalld_get_services = MagicMock(return_value=["http"])

    __salt__ = {
        "firewalld.get_services": firewalld_get_services,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.service_absent("mysvc")
        assert ret == {
            "name": "mysvc",
            "result": True,
            "changes": {},
            "comment": "'mysvc' does not exist.",
        }


def test_ipset_absent_ipset_exists():
    """
    ipset_absent deletes an ipset that currently exists.
    """
    firewalld_get_ipsets = MagicMock(return_value=["myipset", "other"])
    firewalld_delete_ipset = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.get_ipsets": firewalld_get_ipsets,
        "firewalld.delete_ipset": firewalld_delete_ipset,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.ipset_absent("myipset")
        assert ret == {
            "name": "myipset",
            "result": True,
            "changes": {},
            "comment": "'myipset' has been deleted.",
        }
        firewalld_delete_ipset.assert_called_once_with(
            "myipset", permanent=True, restart=True
        )


def test_ipset_absent_ipset_does_not_exist():
    """
    ipset_absent is a no-op when the ipset does not exist.
    """
    firewalld_get_ipsets = MagicMock(return_value=[])

    __salt__ = {
        "firewalld.get_ipsets": firewalld_get_ipsets,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.ipset_absent("myipset")
        assert ret == {
            "name": "myipset",
            "result": True,
            "changes": {},
            "comment": "'myipset' does not exist.",
        }


def test_ipset_present_creates_and_adds_entries():
    """
    ipset_present creates a new ipset and adds entries when ipset is absent.
    """
    firewalld_get_ipsets = MagicMock(return_value=[])
    firewalld_new_ipset = MagicMock(return_value="success")
    firewalld_info_ipset = MagicMock(
        return_value={"myipset": {"type": ["hash:net"], "entries": []}}
    )
    firewalld_add_ipset_entry = MagicMock(return_value="success")
    firewalld_reload_rules = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.get_ipsets": firewalld_get_ipsets,
        "firewalld.new_ipset": firewalld_new_ipset,
        "firewalld.info_ipset": firewalld_info_ipset,
        "firewalld.add_ipset_entry": firewalld_add_ipset_entry,
        "firewalld.remove_ipset_entry": MagicMock(return_value="success"),
        "firewalld.reload_rules": firewalld_reload_rules,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.ipset_present(
            "myipset",
            "hash:net",
            entries=["1.1.1.1/32", "8.8.8.8/32"],
        )
        assert ret["result"] is True
        assert ret["name"] == "myipset"
        assert "entries" in ret["changes"]
        assert set(ret["changes"]["entries"]["new"]) == {"1.1.1.1/32", "8.8.8.8/32"}
        firewalld_new_ipset.assert_called_once()
        firewalld_add_ipset_entry.assert_called()


def test_ipset_present_idempotent():
    """
    ipset_present is a no-op when the ipset and entries already match.
    """
    firewalld_get_ipsets = MagicMock(return_value=["myipset"])
    firewalld_info_ipset = MagicMock(
        return_value={
            "myipset": {"type": ["hash:net"], "entries": ["1.1.1.1/32", "8.8.8.8/32"]}
        }
    )

    __salt__ = {
        "firewalld.get_ipsets": firewalld_get_ipsets,
        "firewalld.info_ipset": firewalld_info_ipset,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.ipset_present(
            "myipset",
            "hash:net",
            entries=["1.1.1.1/32", "8.8.8.8/32"],
        )
        assert ret == {
            "name": "myipset",
            "result": True,
            "changes": {},
            "comment": "'myipset' is already in the desired state.",
        }


def test_zone_present_with_target():
    """
    zone_present sets zone target when it differs from current value.
    """
    firewalld_reload_rules = MagicMock(return_value="success")
    firewalld_get_zones = MagicMock(return_value=["public"])
    firewalld_get_target = MagicMock(return_value="default")
    firewalld_set_target = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.reload_rules": firewalld_reload_rules,
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.get_target": firewalld_get_target,
        "firewalld.set_target": firewalld_set_target,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.zone_present("public", target="DROP")
        assert ret["result"] is True
        assert ret["changes"] == {"target": {"old": "default", "new": "DROP"}}
        firewalld_set_target.assert_called_once_with("public", "DROP", permanent=True)


def test_zone_present_target_already_set():
    """
    zone_present does not change target when it already matches.
    """
    firewalld_reload_rules = MagicMock(return_value="success")
    firewalld_get_zones = MagicMock(return_value=["public"])
    firewalld_get_target = MagicMock(return_value="DROP")
    firewalld_set_target = MagicMock(return_value="success")

    __salt__ = {
        "firewalld.reload_rules": firewalld_reload_rules,
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.get_target": firewalld_get_target,
        "firewalld.set_target": firewalld_set_target,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.zone_present("public", target="DROP")
        assert ret == {
            "name": "public",
            "result": True,
            "changes": {},
            "comment": "'public' is already in the desired state.",
        }
        firewalld_set_target.assert_not_called()


@pytest.mark.parametrize(
    "rich_rule",
    [
        (
            [
                'rule family="ipv4" source address="192.168.0.0/16" port port=22 protocol=tcp accept'
            ]
        ),
        (
            [
                'rule family="ipv4" source address="192.168.0.0/16" port port=\'22\' protocol=tcp accept'
            ]
        ),
        (
            [
                "rule family='ipv4' source address='192.168.0.0/16' port port='22' protocol=tcp accept"
            ]
        ),
    ],
)
def test_present_rich_rules_normalized(rich_rule):
    firewalld_reload_rules = MagicMock(return_value={})
    firewalld_rich_rules = [
        'rule family="ipv4" source address="192.168.0.0/16" port port="22" protocol="tcp" accept',
    ]

    firewalld_get_zones = MagicMock(
        return_value=[
            "block",
            "public",
        ]
    )
    firewalld_get_masquerade = MagicMock(return_value=True)
    firewalld_get_rich_rules = MagicMock(return_value=firewalld_rich_rules)

    __salt__ = {
        "firewalld.reload_rules": firewalld_reload_rules,
        "firewalld.get_zones": firewalld_get_zones,
        "firewalld.get_masquerade": firewalld_get_masquerade,
        "firewalld.get_rich_rules": firewalld_get_rich_rules,
    }
    with patch.dict(firewalld.__dict__, {"__salt__": __salt__}):
        ret = firewalld.present("public", rich_rules=rich_rule)
        assert ret == {
            "changes": {},
            "result": True,
            "comment": "'public' is already in the desired state.",
            "name": "public",
        }
