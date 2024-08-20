"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Jason Woods <devel@jasonwoods.me.uk>
"""

import pytest

import salt.states.selinux as selinux
from tests.support.mock import MagicMock, patch

pytestmark = [pytest.mark.skip_unless_on_linux]


@pytest.fixture
def configure_loader_modules():
    return {selinux: {}}


def test_mode():
    """
    Test to verifies the mode SELinux is running in,
    can be set to enforcing or permissive.
    """
    ret = {
        "name": "unknown",
        "changes": {},
        "result": False,
        "comment": "unknown is not an accepted mode",
    }
    assert selinux.mode("unknown") == ret

    mock_en = MagicMock(return_value="Enforcing")
    mock_pr = MagicMock(side_effect=["Permissive", "Enforcing"])
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.getenforce": mock_en,
            "selinux.getconfig": mock_en,
            "selinux.setenforce": mock_pr,
        },
    ):
        comt = "SELinux is already in Enforcing mode"
        ret = {"name": "Enforcing", "comment": comt, "result": True, "changes": {}}
        assert selinux.mode("Enforcing") == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = "SELinux mode is set to be changed to Permissive"
            ret = {
                "name": "Permissive",
                "comment": comt,
                "result": None,
                "changes": {"new": "Permissive", "old": "Enforcing"},
            }
            assert selinux.mode("Permissive") == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "SELinux has been set to Permissive mode"
            ret = {
                "name": "Permissive",
                "comment": comt,
                "result": True,
                "changes": {"new": "Permissive", "old": "Enforcing"},
            }
            assert selinux.mode("Permissive") == ret

            comt = "Failed to set SELinux to Permissive mode"
            ret.update(
                {"name": "Permissive", "comment": comt, "result": False, "changes": {}}
            )
            assert selinux.mode("Permissive") == ret


def test_boolean():
    """
    Test to set up an SELinux boolean.
    """
    name = "samba_create_home_dirs"
    value = True
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_en = MagicMock(return_value=[])
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_en}):
        comt = f"Boolean {name} is not available"
        ret.update({"comment": comt})
        assert selinux.boolean(name, value) == ret

    mock_bools = MagicMock(return_value={name: {"State": "on", "Default": "on"}})
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_bools}):
        comt = "None is not a valid value for the boolean"
        ret.update({"comment": comt})
        assert selinux.boolean(name, None) == ret

        comt = "Boolean is in the correct state"
        ret.update({"comment": comt, "result": True})
        assert selinux.boolean(name, value, True) == ret

        comt = "Boolean is in the correct state"
        ret.update({"comment": comt, "result": True})
        assert selinux.boolean(name, value) == ret

    mock_bools = MagicMock(return_value={name: {"State": "off", "Default": "on"}})
    mock = MagicMock(side_effect=[True, False])
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebool": mock},
    ):
        with patch.dict(selinux.__opts__, {"test": True}):
            comt = "Boolean samba_create_home_dirs is set to be changed to on"
            ret.update({"comment": comt, "result": None})
            assert selinux.boolean(name, value) == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "Boolean samba_create_home_dirs has been set to on"
            ret.update({"comment": comt, "result": True})
            ret.update({"changes": {"State": {"old": "off", "new": "on"}}})
            assert selinux.boolean(name, value) == ret

            comt = "Failed to set the boolean samba_create_home_dirs to on"
            ret.update({"comment": comt, "result": False})
            ret.update({"changes": {}})
            assert selinux.boolean(name, value) == ret


def test_port_policy_present():
    """
    Test to set up an SELinux port.
    """
    name = "tcp/8080"
    protocol = "tcp"
    port = "8080"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Test when already present with same sel_type
    mock_add = MagicMock(return_value={"retcode": 0})
    mock_modify = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        return_value={
            "sel_type": "http_cache_port_t",
            "protocol": "tcp",
            "port": "8080",
        }
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_add_policy": mock_add,
            "selinux.port_modify_policy": mock_modify,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            comt = (
                f'SELinux policy for "{name}" already present '
                + 'with specified sel_type "http_cache_port_t", protocol "None" '
                + 'and port "None".'
            )
            ret.update({"comment": comt, "result": True})
            assert selinux.port_policy_present(name, "http_cache_port_t") == ret

            comt = (
                'SELinux policy for "name" already present '
                + f'with specified sel_type "http_cache_port_t", protocol "{protocol}" '
                + f'and port "{port}".'
            )
            ret.update({"comment": comt, "changes": {}, "result": True, "name": "name"})
            assert (
                selinux.port_policy_present("name", "http_cache_port_t", protocol, port)
                == ret
            )
            ret.update({"name": name})

    # Test adding new port policy
    mock_add = MagicMock(return_value={"retcode": 0})
    mock_modify = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        side_effect=[
            None,
            None,
            None,
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8080"},
        ]
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_add_policy": mock_add,
            "selinux.port_modify_policy": mock_modify,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": True}):
            ret.update({"comment": "", "result": None})
            assert selinux.port_policy_present(name, "http_cache_port_t") == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            ret.update(
                {
                    "comment": "",
                    "changes": {
                        "old": None,
                        "new": {
                            "sel_type": "http_cache_port_t",
                            "protocol": "tcp",
                            "port": "8080",
                        },
                    },
                    "result": True,
                }
            )
            assert selinux.port_policy_present(name, "http_cache_port_t") == ret

    # Test modifying policy to a new sel_type
    mock_add = MagicMock(return_value={"retcode": 0})
    mock_modify = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        side_effect=[
            None,
            None,
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8080"},
            {"sel_type": "http_port_t", "protocol": "tcp", "port": "8080"},
        ]
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_add_policy": mock_add,
            "selinux.port_modify_policy": mock_modify,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": True}):
            ret.update({"comment": "", "changes": {}, "result": None})
            assert selinux.port_policy_present(name, "http_port_t") == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            ret.update(
                {
                    "comment": "",
                    "changes": {
                        "old": {
                            "sel_type": "http_cache_port_t",
                            "protocol": "tcp",
                            "port": "8080",
                        },
                        "new": {
                            "sel_type": "http_port_t",
                            "protocol": "tcp",
                            "port": "8080",
                        },
                    },
                    "result": True,
                }
            )
            assert selinux.port_policy_present(name, "http_port_t") == ret

    # Test adding new port policy with custom name and using protocol and port parameters
    mock_add = MagicMock(return_value={"retcode": 0})
    mock_modify = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        side_effect=[
            None,
            None,
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8081"},
        ]
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_add_policy": mock_add,
            "selinux.port_modify_policy": mock_modify,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            ret.update(
                {
                    "name": "required_protocol_port",
                    "comment": "",
                    "changes": {
                        "old": None,
                        "new": {
                            "sel_type": "http_cache_port_t",
                            "protocol": "tcp",
                            "port": "8081",
                        },
                    },
                    "result": True,
                }
            )
            assert (
                selinux.port_policy_present(
                    "required_protocol_port",
                    "http_cache_port_t",
                    protocol="tcp",
                    port="8081",
                )
                == ret
            )

    # Test failure of adding new policy
    mock_add = MagicMock(return_value={"retcode": 1})
    mock_modify = MagicMock(return_value={"retcode": 1})
    mock_get = MagicMock(return_value=None)
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_add_policy": mock_add,
            "selinux.port_modify_policy": mock_modify,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "Error adding new policy: {'retcode': 1}"
            ret.update({"name": name, "comment": comt, "changes": {}, "result": False})
            assert selinux.port_policy_present(name, "http_cache_port_t") == ret


def test_port_policy_absent():
    """
    Test to delete an SELinux port.
    """
    name = "tcp/8080"
    protocol = "tcp"
    port = "8080"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Test policy already removed
    mock_delete = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(return_value=None)
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_delete_policy": mock_delete,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            comt = (
                f'SELinux policy for "{name}" already absent '
                + 'with specified sel_type "http_cache_port_t", protocol "None" '
                + 'and port "None".'
            )
            ret.update({"comment": comt, "changes": {}, "result": True})
            assert selinux.port_policy_absent(name, "http_cache_port_t") == ret

            comt = (
                'SELinux policy for "name" already absent '
                + f'with specified sel_type "http_cache_port_t", protocol "{protocol}" '
                + f'and port "{port}".'
            )
            ret.update({"comment": comt, "changes": {}, "result": True, "name": "name"})
            assert (
                selinux.port_policy_absent("name", "http_cache_port_t", protocol, port)
                == ret
            )
            ret.update({"name": name})

    # Test removing a policy
    mock_delete = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        side_effect=[
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8080"},
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8080"},
            None,
        ]
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_delete_policy": mock_delete,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": True}):
            ret.update({"comment": "", "result": None})
            assert selinux.port_policy_absent(name, "http_cache_port_t") == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            ret.update(
                {
                    "comment": "",
                    "changes": {
                        "old": {
                            "sel_type": "http_cache_port_t",
                            "protocol": "tcp",
                            "port": "8080",
                        },
                        "new": None,
                    },
                    "result": True,
                }
            )
            assert selinux.port_policy_absent(name, "http_cache_port_t") == ret

    # Test removing a policy using custom name and with protocol and port parameters
    mock_delete = MagicMock(return_value={"retcode": 0})
    mock_get = MagicMock(
        side_effect=[
            {"sel_type": "http_cache_port_t", "protocol": "tcp", "port": "8081"},
            None,
        ]
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_delete_policy": mock_delete,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            ret.update(
                {
                    "name": "required_protocol_port",
                    "comment": "",
                    "changes": {
                        "old": {
                            "sel_type": "http_cache_port_t",
                            "protocol": "tcp",
                            "port": "8081",
                        },
                        "new": None,
                    },
                    "result": True,
                }
            )
            assert (
                selinux.port_policy_absent(
                    "required_protocol_port",
                    "http_cache_port_t",
                    protocol="tcp",
                    port="8081",
                )
                == ret
            )

    # Test failure to delete a policy
    mock_delete = MagicMock(return_value={"retcode": 2})
    mock_get = MagicMock(
        return_value={
            "sel_type": "http_cache_port_t",
            "protocol": "tcp",
            "port": "8080",
        }
    )
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.port_get_policy": mock_get,
            "selinux.port_delete_policy": mock_delete,
        },
    ):
        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "Error deleting policy: {'retcode': 2}"
            ret.update({"name": name, "comment": comt, "changes": {}, "result": False})
            assert selinux.port_policy_absent(name, "http_cache_port_t") == ret
