"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Jason Woods <devel@jasonwoods.me.uk>
"""

import copy

import pytest

import salt.states.selinux as selinux
from tests.support.mock import MagicMock, patch

pytestmark = [pytest.mark.skip_unless_on_linux]
_SEBOOL_ON_VALUES = [True, "true", "on", "1", 1]
_SEBOOL_OFF_VALUES = [False, "false", "off", "0", 0]


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


def test_boolean_not_available():
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_en = MagicMock(return_value=[])
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_en}):
        comt = f"Boolean {name} is not available"
        ret.update({"comment": comt})
        assert selinux.boolean(name, True) == ret


def test_boolean_on_on():
    """
    Test setting an SELinux boolean with existing state on and default on.
    """
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = {"State": "on", "Default": "on"}
    mock_bools = MagicMock(return_value={name: old})
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"None is not a valid value for the boolean {name}"
        ret.update({"comment": comt})
        assert selinux.boolean(name, None) == ret

        comt = f"The following booleans were in the correct state: {name}"
        ret.update({"comment": comt, "result": True})
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value) == ret
            assert selinux.boolean(name, value, persist=True) == ret

        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {"comment": comt, "changes": {name: {"old": old["State"], "new": "off"}}}
        )
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value) == ret
        ret.update(
            {
                "changes": {
                    name: {"old": (old["State"], old["Default"]), "new": ("off", "off")}
                }
            }
        )
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = f"The following booleans would be changed: {name}"
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {name: {"old": old["State"], "new": "off"}},
                }
            )
            for value in _SEBOOL_OFF_VALUES:
                assert selinux.boolean(name, value) == ret
            ret.update(
                {
                    "changes": {
                        name: {
                            "old": (old["State"], old["Default"]),
                            "new": ("off", "off"),
                        }
                    }
                }
            )
            for value in _SEBOOL_OFF_VALUES:
                assert selinux.boolean(name, value, persist=True) == ret


def test_boolean_on_off():
    """
    Test setting an SELinux boolean with existing state on and default off.
    """
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    old = {"State": "on", "Default": "off"}
    mock_bools = MagicMock(return_value={name: old})
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {
                "comment": comt,
                "changes": {
                    name: {"old": (old["State"], old["Default"]), "new": ("on", "on")}
                },
            }
        )
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        comt = f"The following booleans were in the correct state: {name}"
        ret.update({"comment": comt, "changes": {}})
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value) == ret

        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {"comment": comt, "changes": {name: {"old": old["State"], "new": "off"}}}
        )
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value) == ret

        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {
                "comment": comt,
                "changes": {
                    name: {"old": (old["State"], old["Default"]), "new": ("off", "off")}
                },
            }
        )
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = f"The following booleans would be changed: {name}"
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {name: {"old": old["State"], "new": "off"}},
                }
            )
            for value in _SEBOOL_OFF_VALUES:
                assert selinux.boolean(name, value) == ret

            ret.update(
                {
                    "changes": {
                        name: {
                            "old": (old["State"], old["Default"]),
                            "new": ("off", "off"),
                        }
                    }
                }
            )
            for value in _SEBOOL_OFF_VALUES:
                assert selinux.boolean(name, value, persist=True) == ret


def test_boolean_off_off():
    """
    Test setting an SELinux boolean with existing state off and default off.
    """
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    old = {"State": "off", "Default": "off"}
    mock_bools = MagicMock(return_value={name: {"State": "off", "Default": "off"}})
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {"comment": comt, "changes": {name: {"old": old["State"], "new": "on"}}}
        )
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value) == ret

        ret.update({"changes": {name: {"old": ("off", "off"), "new": ("on", "on")}}})
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        comt = f"The following booleans were in the correct state: {name}"
        ret.update({"comment": comt, "changes": {}})
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value) == ret
            assert selinux.boolean(name, value, persist=True) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = f"The following booleans would be changed: {name}"
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {name: {"old": old["State"], "new": "on"}},
                }
            )
            for value in _SEBOOL_ON_VALUES:
                assert selinux.boolean(name, value) == ret

            ret.update(
                {"changes": {name: {"old": ("off", "off"), "new": ("on", "on")}}}
            )
            for value in _SEBOOL_ON_VALUES:
                assert selinux.boolean(name, value, persist=True) == ret

            comt = f"The following booleans were in the correct state: {name}"
            ret.update({"comment": comt, "result": True, "changes": {}})
            for value in _SEBOOL_OFF_VALUES:
                assert selinux.boolean(name, value) == ret
                assert selinux.boolean(name, value, persist=True) == ret


def test_boolean_off_on():
    """
    Test setting an SELinux boolean with existing state off and default on.
    """
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    old = {"State": "off", "Default": "on"}
    mock_bools = MagicMock(return_value={name: old})
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {name: {"old": old["State"], "new": "on"}},
            }
        )
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value) == ret

        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {
                "comment": comt,
                "changes": {
                    name: {"old": (old["State"], old["Default"]), "new": ("on", "on")}
                },
            }
        )
        for value in _SEBOOL_ON_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        comt = f"The following booleans were in the correct state: {name}"
        ret.update({"comment": comt, "changes": {}})
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value) == ret

        comt = f"The following booleans have been changed: {name}"
        ret.update(
            {
                "comment": comt,
                "changes": {
                    name: {"old": (old["State"], old["Default"]), "new": ("off", "off")}
                },
            }
        )
        for value in _SEBOOL_OFF_VALUES:
            assert selinux.boolean(name, value, persist=True) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = f"The following booleans would be changed: {name}"
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {name: {"old": old["State"], "new": "on"}},
                }
            )
            for value in _SEBOOL_ON_VALUES:
                assert selinux.boolean(name, value) == ret

            ret.update(
                {
                    "changes": {
                        name: {
                            "old": (old["State"], old["Default"]),
                            "new": ("on", "on"),
                        }
                    }
                }
            )
            for value in _SEBOOL_ON_VALUES:
                assert selinux.boolean(name, value, persist=True) == ret


def test_boolean_failure():
    """
    Test setting an SELinux boolean with failure.
    """
    name = "samba_create_home_dirs"
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    old = {"State": "off", "Default": "off"}
    mock_bools = MagicMock(return_value={name: old})
    mock = MagicMock(return_value=False)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        ret.update({"result": False, "changes": {}})
        for value in _SEBOOL_ON_VALUES:
            comt = f"Failed to set the following booleans: { {name: value} }"
            ret.update({"comment": comt})
            assert selinux.boolean(name, value) == ret
            assert selinux.boolean(name, value, persist=True) == ret

    old = {"State": "on", "Default": "on"}
    mock_bools = MagicMock(return_value={name: old})
    mock = MagicMock(return_value=False)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        ret.update({"result": False, "changes": {}})
        for value in _SEBOOL_OFF_VALUES:
            comt = f"Failed to set the following booleans: { {name: value} }"
            ret.update({"comment": comt})
            assert selinux.boolean(name, value) == ret
            assert selinux.boolean(name, value, persist=True) == ret


def test_boolean_booleans():
    """
    Test to set up multiple SELinux booleans with a single state.
    """
    name = "mybooleans"
    se_bool_names = [
        "abrt_anon_write",
        "abrt_handle_event",
        "domain_can_ptrace",
        "ftpd_anon_write",
        "ftpd_home_dir",
        "ftpd_use_cifs",
        "nis_enabled",
        "samba_create_home_dirs",
        "tftp_anon_write",
        "tftp_home_dir",
    ]
    on_values_dict = {
        "abrt_anon_write": True,
        "abrt_handle_event": True,
        "domain_can_ptrace": "True",
        "ftpd_anon_write": "true",
        "ftpd_home_dir": "on",
        "ftpd_use_cifs": "1",
        "nis_enabled": "1",
        "samba_create_home_dirs": 1,
        "tftp_home_dir": 1,
        "tftp_anon_write": 1,
    }
    on_values_list_of_dict = [
        {"abrt_anon_write": True},
        {"abrt_handle_event": True},
        {"domain_can_ptrace": "True"},
        {"ftpd_anon_write": "true"},
        {"ftpd_home_dir": "on"},
        {"ftpd_use_cifs": "1"},
        {"nis_enabled": "1"},
        {"samba_create_home_dirs": 1},
        {"tftp_home_dir": 1},
        {"tftp_anon_write": 1},
    ]
    on_values_list_of_str_and_dict = [
        "abrt_anon_write",
        {"abrt_handle_event": True},
        {"domain_can_ptrace": "true"},
        {"ftpd_anon_write": "on"},
        "ftpd_home_dir",
        {"ftpd_use_cifs": "1"},
        {"nis_enabled": 1},
        "samba_create_home_dirs",
        "tftp_home_dir",
        "tftp_anon_write",
    ]
    off_values_dict = {
        "abrt_anon_write": False,
        "abrt_handle_event": False,
        "domain_can_ptrace": "False",
        "ftpd_anon_write": "false",
        "ftpd_home_dir": "off",
        "ftpd_use_cifs": "0",
        "nis_enabled": "0",
        "samba_create_home_dirs": 0,
        "tftp_home_dir": 0,
        "tftp_anon_write": 0,
    }
    off_values_list_of_dict = [
        {"abrt_anon_write": False},
        {"abrt_handle_event": False},
        {"domain_can_ptrace": "False"},
        {"ftpd_anon_write": "false"},
        {"ftpd_home_dir": "off"},
        {"ftpd_use_cifs": "0"},
        {"nis_enabled": "0"},
        {"samba_create_home_dirs": 0},
        {"tftp_home_dir": 0},
        {"tftp_anon_write": 0},
    ]
    off_values_list_of_str_and_dict = [
        "abrt_anon_write",
        {"abrt_handle_event": False},
        {"domain_can_ptrace": "false"},
        {"ftpd_anon_write": "off"},
        "ftpd_home_dir",
        {"ftpd_use_cifs": "0"},
        {"nis_enabled": 0},
        "samba_create_home_dirs",
        "tftp_home_dir",
        "tftp_anon_write",
    ]
    on_values_for_mixed = {
        "abrt_anon_write": True,
        "abrt_handle_event": "true",
        "domain_can_ptrace": "on",
        "ftpd_anon_write": "1",
        "ftpd_home_dir": 1,
    }
    off_values_for_mixed = {
        "ftpd_use_cifs": False,
        "nis_enabled": "false",
        "samba_create_home_dirs": "off",
        "tftp_anon_write": "0",
        "tftp_home_dir": 0,
    }
    mixed_values_dict = on_values_for_mixed | off_values_for_mixed
    mixed_values_list = [{key: value} for key, value in mixed_values_dict.items()]
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_en = MagicMock(return_value=[])
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_en}):
        comt = f"Boolean {se_bool_names[0]} is not available"
        ret.update({"comment": comt})
        assert selinux.boolean(name, True, booleans=se_bool_names) == ret

    old = {"State": "on", "Default": "on"}
    mock_bools = MagicMock(
        return_value={se_bool_name: old for se_bool_name in se_bool_names}
    )
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        # value not set; booleans as a list of str
        comt = "None is not a valid value for the boolean abrt_anon_write"
        ret.update({"comment": comt, "result": False, "changes": {}})
        assert selinux.boolean(name, booleans=se_bool_names) == ret
        assert selinux.boolean(name, None, booleans=se_bool_names) == ret
        # value not set; booleans as a list of mixed str and dict
        assert selinux.boolean(name, booleans=on_values_list_of_str_and_dict) == ret

        comt = f"The following booleans were in the correct state: {', '.join(se_bool_names)}"
        ret.update({"comment": comt, "result": True})
        # value set; booleans as a list of str
        assert selinux.boolean(name, True, booleans=se_bool_names) == ret
        # value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(name, True, booleans=on_values_list_of_str_and_dict) == ret
        )
        # value not set; booleans as a list of dict
        assert selinux.boolean(name, booleans=on_values_list_of_dict) == ret
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=on_values_dict) == ret
        # value set differently than booleans as a dict
        assert selinux.boolean(name, False, booleans=on_values_dict) == ret
        # persist; value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(
                name, True, booleans=on_values_list_of_str_and_dict, persist=True
            )
            == ret
        )
        # persist; value not set; booleans as dict
        assert selinux.boolean(name, booleans=on_values_dict, persist=True) == ret

        comt = f"The following booleans have been changed: {', '.join(se_bool_names)}"
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "off"}
                    for se_bool_name in se_bool_names
                },
            }
        )
        # value set; booleans as a list of str
        assert selinux.boolean(name, False, booleans=se_bool_names) == ret
        # value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(name, False, booleans=off_values_list_of_str_and_dict)
            == ret
        )
        # value not set; booleans as a list of dict
        assert selinux.boolean(name, booleans=off_values_list_of_dict) == ret
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=off_values_dict) == ret
        # value set differently than booleans as a dict
        assert selinux.boolean(name, True, booleans=off_values_dict) == ret

        # persist; value set; booleans as a list of mixed str and dict
        ret.update(
            {
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("off", "off"),
                    }
                    for se_bool_name in se_bool_names
                }
            }
        )
        assert (
            selinux.boolean(
                name, False, booleans=off_values_list_of_str_and_dict, persist=True
            )
            == ret
        )
        # persist; value not set; booleans as dict
        assert selinux.boolean(name, persist=True, booleans=off_values_dict) == ret

        comt = (
            f"The following booleans were in the correct state: {', '.join(on_values_for_mixed)}\n"
            + f"The following booleans have been changed: {', '.join(off_values_for_mixed)}"
        )
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "off"}
                    for se_bool_name in off_values_for_mixed
                },
            }
        )

        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict) == ret
        # value set on with dict of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_dict) == ret
        # value set off with dict of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_dict) == ret
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list) == ret
        # value set on with list of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_list) == ret
        # value set off with list of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_list) == ret

        ret.update(
            {
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("off", "off"),
                    }
                    for se_bool_name in off_values_for_mixed
                }
            }
        )
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict, persist=True) == ret
        # value set on with dict of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_dict, persist=True) == ret
        )
        # value set off with dict of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_dict, persist=True)
            == ret
        )
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list, persist=True) == ret
        # value set on with list of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_list, persist=True) == ret
        )
        # value set off with list of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_list, persist=True)
            == ret
        )

    old = {"State": "off", "Default": "on"}
    mock_bools = MagicMock(
        return_value={se_bool_name: old for se_bool_name in se_bool_names}
    )
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"The following booleans have been changed: {', '.join(se_bool_names)}"
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "on"}
                    for se_bool_name in se_bool_names
                },
            }
        )
        # value set; booleans as a list of str
        assert selinux.boolean(name, True, booleans=se_bool_names) == ret
        # value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(name, True, booleans=on_values_list_of_str_and_dict) == ret
        )
        # value not set; booleans as a list of dict
        assert selinux.boolean(name, booleans=on_values_list_of_dict) == ret
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=on_values_dict) == ret
        # value set differently than booleans as a dict
        assert selinux.boolean(name, False, booleans=on_values_dict) == ret

        # persist; value set; booleans as a list of mixed str and dict
        ret.update(
            {
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("on", "on"),
                    }
                    for se_bool_name in se_bool_names
                }
            }
        )
        assert (
            selinux.boolean(
                name, True, booleans=on_values_list_of_str_and_dict, persist=True
            )
            == ret
        )
        # persist; value not set; booleans as dict
        assert selinux.boolean(name, persist=True, booleans=on_values_dict) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = (
                f"The following booleans would be changed: {', '.join(se_bool_names)}"
            )
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {
                        se_bool_name: {"old": old["State"], "new": "on"}
                        for se_bool_name in se_bool_names
                    },
                }
            )

            assert selinux.boolean(name, True, booleans=se_bool_names) == ret
            # value set; booleans as a list of mixed str and dict
            assert (
                selinux.boolean(name, True, booleans=on_values_list_of_str_and_dict)
                == ret
            )
            # value not set; booleans as a list of dict
            assert selinux.boolean(name, booleans=on_values_list_of_dict) == ret
            # value not set; booleans as a dict
            assert selinux.boolean(name, booleans=on_values_dict) == ret
            # value set differently than booleans as a dict
            assert selinux.boolean(name, False, booleans=on_values_dict) == ret

            # persist; value set; booleans as a list of mixed str and dict
            ret.update(
                {
                    "changes": {
                        se_bool_name: {
                            "old": (old["State"], old["Default"]),
                            "new": ("on", "on"),
                        }
                        for se_bool_name in se_bool_names
                    }
                }
            )
            assert (
                selinux.boolean(
                    name,
                    True,
                    persist=True,
                    booleans=on_values_list_of_str_and_dict,
                )
                == ret
            )
            # persist; value not set; booleans as dict
            assert selinux.boolean(name, persist=True, booleans=on_values_dict) == ret

        comt = (
            f"The following booleans were in the correct state: {', '.join(off_values_for_mixed)}\n"
            + f"The following booleans have been changed: {', '.join(on_values_for_mixed)}"
        )
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "on"}
                    for se_bool_name in on_values_for_mixed
                },
            }
        )

        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict) == ret
        # value set on with dict of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_dict) == ret
        # value set off with dict of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_dict) == ret
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list) == ret
        # value set on with list of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_list) == ret
        # value set off with list of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_list) == ret

        comt = (
            f"The following booleans have been changed: {', '.join(mixed_values_dict)}"
        )
        ret.update(
            {
                "comment": comt,
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("off", "off"),
                    }
                    for se_bool_name in off_values_for_mixed
                }
                | {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("on", "on"),
                    }
                    for se_bool_name in on_values_for_mixed
                },
            }
        )
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict, persist=True) == ret
        # value set on with dict of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_dict, persist=True) == ret
        )
        # value set off with dict of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_dict, persist=True)
            == ret
        )
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list, persist=True) == ret
        # value set on with list of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_list, persist=True) == ret
        )
        # value set off with list of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_list, persist=True)
            == ret
        )

    old = {"State": "off", "Default": "off"}
    mock_bools = MagicMock(
        return_value={se_bool_name: old for se_bool_name in se_bool_names}
    )
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        # value not set; booleans as a list of str
        comt = "None is not a valid value for the boolean abrt_anon_write"
        ret.update({"comment": comt, "result": False, "changes": {}})
        assert selinux.boolean(name, booleans=se_bool_names) == ret
        assert selinux.boolean(name, None, booleans=se_bool_names) == ret
        # value not set; booleans as a list of mixed str and dict
        assert selinux.boolean(name, booleans=on_values_list_of_str_and_dict) == ret

        comt = f"The following booleans were in the correct state: {', '.join(se_bool_names)}"
        ret.update({"comment": comt, "result": True})
        # value set; booleans as a list of str
        assert selinux.boolean(name, False, booleans=se_bool_names) == ret
        # value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(name, False, booleans=off_values_list_of_str_and_dict)
            == ret
        )
        # value not set; booleans as a list of dict
        assert selinux.boolean(name, booleans=off_values_list_of_dict) == ret
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=off_values_dict) == ret
        # value set differently than booleans as a dict
        assert selinux.boolean(name, True, booleans=off_values_dict) == ret

        # persist; value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(
                name,
                False,
                persist=True,
                booleans=off_values_list_of_str_and_dict,
            )
            == ret
        )
        # persist; value not set; booleans as dict
        assert selinux.boolean(name, persist=True, booleans=off_values_dict) == ret

        comt = (
            f"The following booleans were in the correct state: {', '.join(off_values_for_mixed)}\n"
            + f"The following booleans have been changed: {', '.join(on_values_for_mixed)}"
        )
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "on"}
                    for se_bool_name in on_values_for_mixed
                },
            }
        )
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict) == ret
        # value set on with dict of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_dict) == ret
        # value set off with dict of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_dict) == ret
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list) == ret
        # value set on with list of mixed values
        assert selinux.boolean(name, True, booleans=mixed_values_list) == ret
        # value set off with list of mixed values
        assert selinux.boolean(name, False, booleans=mixed_values_list) == ret

        ret.update(
            {
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("on", "on"),
                    }
                    for se_bool_name in on_values_for_mixed
                }
            }
        )
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=mixed_values_dict, persist=True) == ret
        # value set on with dict of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_dict, persist=True) == ret
        )
        # value set off with dict of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_dict, persist=True)
            == ret
        )
        # value not set; booleans as a list of mixed values
        assert selinux.boolean(name, booleans=mixed_values_list, persist=True) == ret
        # value set on with list of mixed values
        assert (
            selinux.boolean(name, True, booleans=mixed_values_list, persist=True) == ret
        )
        # value set off with list of mixed values
        assert (
            selinux.boolean(name, False, booleans=mixed_values_list, persist=True)
            == ret
        )

    old = {"State": "off", "Default": "on"}
    mock_bools = MagicMock(
        return_value={se_bool_name: old for se_bool_name in se_bool_names}
    )
    mock = MagicMock(return_value=True)
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebools": mock},
    ):
        comt = f"The following booleans have been changed: {', '.join(se_bool_names)}"
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    se_bool_name: {"old": old["State"], "new": "on"}
                    for se_bool_name in se_bool_names
                },
            }
        )
        # value set; booleans as a list of str
        assert selinux.boolean(name, True, booleans=se_bool_names) == ret
        # value set; booleans as a list of mixed str and dict
        assert (
            selinux.boolean(name, True, booleans=on_values_list_of_str_and_dict) == ret
        )
        # value not set; booleans as a list
        assert selinux.boolean(name, booleans=on_values_list_of_dict) == ret
        # value not set; booleans as a dict
        assert selinux.boolean(name, booleans=on_values_dict) == ret
        # value set differently than booleans as a dict
        assert selinux.boolean(name, False, booleans=on_values_dict) == ret

        # persist; value set; booleans as a list of mixed str and dict
        ret.update(
            {
                "changes": {
                    se_bool_name: {
                        "old": (old["State"], old["Default"]),
                        "new": ("on", "on"),
                    }
                    for se_bool_name in se_bool_names
                }
            }
        )
        assert (
            selinux.boolean(
                name,
                True,
                persist=True,
                booleans=on_values_list_of_str_and_dict,
            )
            == ret
        )
        # persist; value not set; booleans as dict
        assert selinux.boolean(name, persist=True, booleans=on_values_dict) == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = (
                f"The following booleans would be changed: {', '.join(se_bool_names)}"
            )
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {
                        name: {"old": old["State"], "new": "on"}
                        for name in se_bool_names
                    },
                }
            )

            assert selinux.boolean(name, True, booleans=se_bool_names) == ret
            # value set; booleans as a list of mixed str and dict
            assert (
                selinux.boolean(name, True, booleans=on_values_list_of_str_and_dict)
                == ret
            )
            # value not set; booleans as a list of dict
            assert selinux.boolean(name, booleans=on_values_list_of_dict) == ret
            # value not set; booleans as a dict
            assert selinux.boolean(name, booleans=on_values_dict) == ret
            # value set differently than booleans as a dict
            assert selinux.boolean(name, False, booleans=on_values_dict) == ret

            # persist; value set; booleans as a list of mixed str and dict
            ret.update(
                {
                    "changes": {
                        se_bool_name: {
                            "old": (old["State"], old["Default"]),
                            "new": ("on", "on"),
                        }
                        for se_bool_name in se_bool_names
                    }
                }
            )
            assert (
                selinux.boolean(
                    name,
                    True,
                    booleans=on_values_list_of_str_and_dict,
                    persist=True,
                )
                == ret
            )
            # persist; value not set; booleans as dict
            assert selinux.boolean(name, persist=True, booleans=on_values_dict) == ret


def test_mod_aggregate():
    """
    Test mod_aggregate function
    """
    chunks = [
        {
            "state": "file",
            "name": "/tmp/install-vim",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-vim",
            "order": 10000,
            "fun": "managed",
        },
        {
            "state": "file",
            "name": "/tmp/install-tmux",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-tmux",
            "order": 10001,
            "fun": "managed",
        },
        {
            "state": "selinux",
            "name": "other_bools_list",
            "__sls__": "47628",
            "__env __": "base",
            "__id__": "other_bools_list",
            "booleans": [
                "domain_can_ptrace",
                "ftpd_anon_write",
                {"samba_create_home_dirs": "on"},
            ],
            "value": "off",
            "aggregate": True,
            "order": 10002,
            "fun": "boolean",
        },
        {
            "state": "selinux",
            "name": "other_bools_dict",
            "__sls__": "47628",
            "__env __": "base",
            "__id__": "other_bools_dict",
            "booleans": {
                "ftpd_home_dir": False,
                "ftpd_use_cifs": True,
            },
            "value": "off",
            "aggregate": True,
            "order": 10003,
            "fun": "boolean",
        },
        {
            "state": "selinux",
            # override previous value
            "name": "ftpd_home_dir",
            "value": "on",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "ftpd_home_dir",
            "aggregate": True,
            "order": 10004,
            "fun": "boolean",
        },
        {
            "state": "selinux",
            "name": "ftpd_connect_all_unreserved",
            "value": "False",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "ftpd_connect_all_unreserved",
            "require": ["/tmp/install-vim"],
            "order": 10004,
            "fun": "boolean",
        },
        {
            "state": "selinux",
            "name": "nis_enabled",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "nis_enabled",
            "require": ["/tmp/install-tmux"],
            "value": "on",
            "order": 10005,
            "fun": "boolean",
        },
    ]

    running = {
        "file_|-/tmp/install-vim_| -/tmp/install-vim_|-managed": {
            "changes": {},
            "comment": "File /tmp/install-vim exists with proper permissions. No changes made.",
            "name": "/tmp/install-vim",
            "result": True,
            "__sls__": "47628",
            "__run_num__": 0,
            "start_time": "18:41:20.987275",
            "duration": 5.833,
            "__id__": "/tmp/install-vim",
        },
        "file_|-/tmp/install-tmux_|-/tmp/install-tmux_|-managed": {
            "changes": {},
            "comment": "File /tmp/install-tmux exists with proper permissions. No changes made.",
            "name": "/tmp/install-tmux",
            "result": True,
            "__sls__": "47628",
            "__run_num__": 1,
            "start_time": "18:41:20.993258",
            "duration": 1.263,
            "__id__": "/tmp/install-tmux",
        },
    }

    expected = {
        "__id__": "agg_root_selinux_bool",
        "state": "selinux",
        "name": "abrt_anon_write",
        "value": "on",
        "aggregate": True,
        "fun": "boolean",
        "booleans": {
            "abrt_anon_write": "on",
            "domain_can_ptrace": "off",
            "ftpd_anon_write": "off",
            "samba_create_home_dirs": "on",
            "ftpd_home_dir": "on",
            "ftpd_use_cifs": True,
            "ftpd_connect_all_unreserved": "False",
            "nis_enabled": "on",
        },
    }
    low_single = {
        "__id__": "agg_root_selinux_bool",
        "state": "selinux",
        "name": "abrt_anon_write",
        "value": "on",
        "aggregate": True,
        "fun": "boolean",
    }
    res = selinux.mod_aggregate(low_single, copy.deepcopy(chunks), running)
    assert res == expected

    expected = {
        "__id__": "agg_root_selinux_bool",
        "booleans": {
            "abrt_anon_write": False,
            "abrt_handle_event": False,
            "domain_can_ptrace": "off",
            "ftpd_anon_write": "off",
            "samba_create_home_dirs": "on",
            "ftpd_home_dir": "on",
            "ftpd_use_cifs": True,
            "ftpd_connect_all_unreserved": "False",
            "nis_enabled": "on",
        },
        "name": "agg_root_selinux_bool",
        "value": False,
        "fun": "boolean",
        "aggregate": True,
        "state": "selinux",
    }
    low_bool_list = {
        "__id__": "agg_root_selinux_bool",
        "state": "selinux",
        "name": "agg_root_selinux_bool",
        "value": False,
        "booleans": [
            "abrt_anon_write",
            "abrt_handle_event",
        ],
        "aggregate": True,
        "fun": "boolean",
    }
    res = selinux.mod_aggregate(low_bool_list, copy.deepcopy(chunks), running)
    assert res == expected

    expected = {
        "__id__": "agg_root_selinux_bool",
        "booleans": {
            "abrt_anon_write": True,
            "abrt_handle_event": False,
            "domain_can_ptrace": "off",
            "ftpd_anon_write": "off",
            "samba_create_home_dirs": "on",
            "ftpd_home_dir": "on",
            "ftpd_use_cifs": True,
            "ftpd_connect_all_unreserved": "False",
            "nis_enabled": "on",
        },
        "name": "agg_root_selinux_bool",
        "fun": "boolean",
        "aggregate": True,
        "state": "selinux",
    }
    low_bool_dict = {
        "__id__": "agg_root_selinux_bool",
        "state": "selinux",
        "name": "agg_root_selinux_bool",
        "booleans": {
            "abrt_anon_write": True,
            "abrt_handle_event": False,
        },
        "aggregate": True,
        "fun": "boolean",
    }
    res = selinux.mod_aggregate(low_bool_dict, copy.deepcopy(chunks), running)
    assert res == expected


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
