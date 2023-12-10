"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""


import pytest

import salt.states.iptables as iptables
import salt.utils.state as state_utils
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        iptables: {
            "__utils__": {"state.gen_tag": state_utils.gen_tag},
        }
    }


def test_chain_present():
    """
    Test to verify the chain is exist.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[True, False, False, False])
    with patch.dict(iptables.__salt__, {"iptables.check_chain": mock}):
        ret.update(
            {
                "comment": (
                    "iptables salt chain is already exist in filter table for ipv4"
                )
            }
        )
        assert iptables.chain_present("salt") == ret

        with patch.dict(iptables.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": (
                        "iptables salt chain in filter"
                        " table needs to be set for ipv4"
                    ),
                    "result": None,
                }
            )
            assert iptables.chain_present("salt") == ret

        with patch.dict(iptables.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[True, ""])
            with patch.dict(iptables.__salt__, {"iptables.new_chain": mock}):
                ret.update(
                    {
                        "result": True,
                        "comment": (
                            "iptables salt chain in filter"
                            " table create success for ipv4"
                        ),
                        "changes": {"locale": "salt"},
                    }
                )
                assert iptables.chain_present("salt") == ret

                ret.update(
                    {
                        "changes": {},
                        "result": False,
                        "comment": (
                            "Failed to create salt chain in filter table:  for ipv4"
                        ),
                    }
                )
                assert iptables.chain_present("salt") == ret


def test_chain_absent():
    """
    Test to verify the chain is absent.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[False, True, True, True])
    with patch.dict(iptables.__salt__, {"iptables.check_chain": mock}):
        ret.update(
            {
                "comment": (
                    "iptables salt chain is already absent in filter table for ipv4"
                )
            }
        )
        assert iptables.chain_absent("salt") == ret

        with patch.dict(iptables.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": (
                        "iptables salt chain in filter"
                        " table needs to be removed ipv4"
                    ),
                    "result": None,
                }
            )
            assert iptables.chain_absent("salt") == ret

        with patch.dict(iptables.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[False, "a"])
            with patch.dict(iptables.__salt__, {"iptables.flush": mock}):
                mock = MagicMock(return_value=True)
                with patch.dict(iptables.__salt__, {"iptables.delete_chain": mock}):
                    ret.update(
                        {
                            "changes": {"locale": "salt"},
                            "comment": (
                                "iptables salt chain in filter"
                                " table delete success for ipv4"
                            ),
                            "result": True,
                        }
                    )
                    assert iptables.chain_absent("salt") == ret

                ret.update(
                    {
                        "changes": {},
                        "result": False,
                        "comment": (
                            "Failed to flush salt chain in filter table: a for ipv4"
                        ),
                    }
                )
                assert iptables.chain_absent("salt") == ret


def test_append():
    """
    Test to append a rule to a chain
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

    assert iptables.append("salt", rules=[]) == ret

    mock = MagicMock(return_value=[])
    with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value="a")
        with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
            mock = MagicMock(side_effect=[True, False, False, False, False, True])
            with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                ret.update(
                    {
                        "comment": ("iptables rule for salt already set (a) for ipv4"),
                        "result": True,
                    }
                )
                assert iptables.append("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "iptables rule for salt" " needs to be set (a) for ipv4"
                            ),
                        }
                    )
                    assert iptables.append("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": False}):
                    mock = MagicMock(side_effect=[True, False, True, True])
                    with patch.dict(iptables.__salt__, {"iptables.append": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "result": True,
                                "comment": (
                                    "Set iptables rule for salt to: a for ipv4"
                                ),
                            }
                        )
                        assert iptables.append("salt", table="", chain="") == ret

                        ret.update(
                            {
                                "changes": {},
                                "result": False,
                                "comment": (
                                    "Failed to set iptables"
                                    " rule for salt.\nAttempted rule was"
                                    " a for ipv4"
                                ),
                            }
                        )
                        assert iptables.append("salt", table="", chain="") == ret

                        mock_save = MagicMock(
                            side_effect=['Wrote 1 lines to "/tmp/iptables"', ""]
                        )
                        with patch.dict(
                            iptables.__salt__, {"iptables.save": mock_save}
                        ):
                            mock_get_saved_rules = MagicMock(side_effect=[""])
                            with patch.dict(
                                iptables.__salt__,
                                {"iptables.get_saved_rules": mock_get_saved_rules},
                            ):
                                mock = MagicMock(side_effect=[""])
                                with patch.dict(
                                    iptables.__salt__, {"iptables.get_rules": mock}
                                ):
                                    ret.update(
                                        {
                                            "changes": {"locale": "salt"},
                                            "result": True,
                                            "comment": "Set and saved iptables rule"
                                            ' salt for ipv4\na\nWrote 1 lines to "/tmp/iptables"',
                                        }
                                    )
                                    assert (
                                        iptables.append(
                                            "salt",
                                            table="",
                                            chain="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    ret.update(
                                        {
                                            "changes": {},
                                            "result": True,
                                            "comment": "iptables rule for salt already set (a) for ipv4",
                                        }
                                    )
                                    assert (
                                        iptables.append(
                                            "salt",
                                            table="",
                                            chain="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    assert (
                                        mock_get_saved_rules.mock_calls[0][2][
                                            "conf_file"
                                        ]
                                        == "/tmp/iptables"
                                    )
                                    assert (
                                        mock_save.mock_calls[0][2]["filename"]
                                        == "/tmp/iptables"
                                    )


def test_insert():
    """
    Test to insert a rule into a chain
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

    assert iptables.insert("salt", rules=[]) == ret

    mock = MagicMock(return_value=[])
    with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value="a")
        with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
            mock = MagicMock(side_effect=[True, False, False, False, False, True])
            with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                ret.update(
                    {
                        "comment": ("iptables rule for salt already set for ipv4 (a)"),
                        "result": True,
                    }
                )
                assert iptables.insert("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "iptables rule for salt" " needs to be set for ipv4 (a)"
                            ),
                        }
                    )
                    assert iptables.insert("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": False}):
                    mock = MagicMock(side_effect=[False, True, False, True])
                    with patch.dict(iptables.__salt__, {"iptables.insert": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "result": True,
                                "comment": (
                                    "Set iptables rule for salt to: a for ipv4"
                                ),
                            }
                        )
                        assert (
                            iptables.insert("salt", table="", chain="", position="")
                            == ret
                        )

                        ret.update(
                            {
                                "changes": {},
                                "result": False,
                                "comment": (
                                    "Failed to set iptables"
                                    " rule for salt.\nAttempted rule was a"
                                ),
                            }
                        )
                        assert (
                            iptables.insert("salt", table="", chain="", position="")
                            == ret
                        )

                        mock_save = MagicMock(
                            side_effect=['Wrote 1 lines to "/tmp/iptables"', ""]
                        )
                        with patch.dict(
                            iptables.__salt__, {"iptables.save": mock_save}
                        ):
                            mock_get_saved_rules = MagicMock(side_effect=[""])
                            with patch.dict(
                                iptables.__salt__,
                                {"iptables.get_saved_rules": mock_get_saved_rules},
                            ):
                                mock = MagicMock(side_effect=[""])
                                with patch.dict(
                                    iptables.__salt__, {"iptables.get_rules": mock}
                                ):
                                    ret.update(
                                        {
                                            "changes": {"locale": "salt"},
                                            "result": True,
                                            "comment": "Set and saved iptables rule"
                                            ' salt for ipv4\na\nWrote 1 lines to "/tmp/iptables"',
                                        }
                                    )
                                    assert (
                                        iptables.insert(
                                            "salt",
                                            table="",
                                            chain="",
                                            position="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    ret.update(
                                        {
                                            "changes": {},
                                            "result": True,
                                            "comment": "iptables rule for salt already set for ipv4 (a)",
                                        }
                                    )
                                    assert (
                                        iptables.insert(
                                            "salt",
                                            table="",
                                            chain="",
                                            position="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    assert (
                                        mock_get_saved_rules.mock_calls[0][2][
                                            "conf_file"
                                        ]
                                        == "/tmp/iptables"
                                    )
                                    assert (
                                        mock_save.mock_calls[0][2]["filename"]
                                        == "/tmp/iptables"
                                    )


def test_delete():
    """
    Test to delete a rule to a chain
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

    assert iptables.delete("salt", rules=[]) == ret

    mock = MagicMock(return_value=[])
    with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value="a")
        with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
            mock = MagicMock(side_effect=[False, True, True, True, True, False])
            with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                ret.update(
                    {
                        "comment": (
                            "iptables rule for salt already absent for ipv4 (a)"
                        ),
                        "result": True,
                    }
                )
                assert iptables.delete("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "iptables rule for salt needs"
                                " to be deleted for ipv4 (a)"
                            ),
                        }
                    )
                    assert iptables.delete("salt", table="", chain="") == ret

                with patch.dict(iptables.__opts__, {"test": False}):
                    mock = MagicMock(side_effect=[False, True, False, False])
                    with patch.dict(iptables.__salt__, {"iptables.delete": mock}):
                        ret.update(
                            {
                                "result": True,
                                "changes": {"locale": "salt"},
                                "comment": "Delete iptables rule for salt a",
                            }
                        )
                        assert (
                            iptables.delete("salt", table="", chain="", position="")
                            == ret
                        )

                        ret.update(
                            {
                                "result": False,
                                "changes": {},
                                "comment": (
                                    "Failed to delete iptables"
                                    " rule for salt.\nAttempted rule was a"
                                ),
                            }
                        )
                        assert (
                            iptables.delete("salt", table="", chain="", position="")
                            == ret
                        )

                        mock_save = MagicMock(
                            side_effect=['Wrote 1 lines to "/tmp/iptables"', ""]
                        )
                        with patch.dict(
                            iptables.__salt__, {"iptables.save": mock_save}
                        ):
                            mock = MagicMock(side_effect=[True, False])
                            with patch.dict(
                                iptables.__salt__, {"iptables.check": mock}
                            ):
                                mock = MagicMock(side_effect=[""])
                                with patch.dict(
                                    iptables.__salt__, {"iptables.get_rules": mock}
                                ):
                                    ret.update(
                                        {
                                            "changes": {"locale": "salt"},
                                            "result": True,
                                            "comment": "Deleted and saved iptables rule"
                                            ' salt for ipv4\na\nWrote 1 lines to "/tmp/iptables"',
                                        }
                                    )
                                    assert (
                                        iptables.delete(
                                            "salt",
                                            table="",
                                            chain="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    ret.update(
                                        {
                                            "changes": {},
                                            "result": True,
                                            "comment": "iptables rule for salt already absent for ipv4 (a)",
                                        }
                                    )
                                    assert (
                                        iptables.delete(
                                            "salt",
                                            table="",
                                            chain="",
                                            save="/tmp/iptables",
                                        )
                                        == ret
                                    )
                                    assert (
                                        mock_save.mock_calls[0][2]["filename"]
                                        == "/tmp/iptables"
                                    )


def test_set_policy():
    """
    Test to sets the default policy for iptables firewall tables
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(return_value=[])
    with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value="stack")
        with patch.dict(iptables.__salt__, {"iptables.get_policy": mock}):
            ret.update(
                {
                    "comment": (
                        "iptables default policy for chain"
                        "  on table  for ipv4 already set to stack"
                    )
                }
            )
            assert (
                iptables.set_policy("salt", table="", chain="", policy="stack") == ret
            )

            with patch.dict(iptables.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": (
                            "iptables default policy for chain"
                            "  on table  for ipv4 needs to be set"
                            " to sal"
                        ),
                        "result": None,
                    }
                )
                assert (
                    iptables.set_policy("salt", table="", chain="", policy="sal") == ret
                )

            with patch.dict(iptables.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[False, True])
                with patch.dict(iptables.__salt__, {"iptables.set_policy": mock}):
                    ret.update(
                        {
                            "changes": {"locale": "salt"},
                            "comment": "Set default policy for  to sal family ipv4",
                            "result": True,
                        }
                    )
                    assert (
                        iptables.set_policy("salt", table="", chain="", policy="sal")
                        == ret
                    )

                    ret.update(
                        {
                            "comment": "Failed to set iptables default policy",
                            "result": False,
                            "changes": {},
                        }
                    )
                    assert (
                        iptables.set_policy("salt", table="", chain="", policy="sal")
                        == ret
                    )


def test_flush():
    """
    Test to flush current iptables state
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

    mock = MagicMock(return_value=[])
    with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
        with patch.dict(iptables.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": (
                        "iptables rules in salt table filter"
                        " chain ipv4 family needs to be flushed"
                    )
                }
            )
            assert iptables.flush("salt") == ret

        with patch.dict(iptables.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[False, True])
            with patch.dict(iptables.__salt__, {"iptables.flush": mock}):
                ret.update(
                    {
                        "changes": {"locale": "salt"},
                        "comment": (
                            "Flush iptables rules in  table  chain ipv4 family"
                        ),
                        "result": True,
                    }
                )
                assert iptables.flush("salt", table="", chain="") == ret

                ret.update(
                    {
                        "changes": {},
                        "comment": "Failed to flush iptables rules",
                        "result": False,
                    }
                )
                assert iptables.flush("salt", table="", chain="") == ret


def test_mod_aggregate():
    """
    Test to mod_aggregate function
    """
    low = {
        "state": "iptables",
        "name": "accept_local_interface",
        "__sls__": "iptables",
        "__env__": "base",
        "__id__": "append_accept_local_interface",
        "table": "filter",
        "chain": "INPUT",
        "in-interface": "lo",
        "jump": "ACCEPT",
        "save": True,
        "order": 10000,
        "fun": "append",
    }

    chunks = [
        {
            "state": "iptables",
            "name": "accept_local_interface",
            "__sls__": "iptables",
            "__env__": "base",
            "__id__": "append_accept_local_interface",
            "table": "filter",
            "chain": "INPUT",
            "in-interface": "lo",
            "jump": "ACCEPT",
            "save": True,
            "order": 10000,
            "fun": "append",
        },
        {
            "state": "iptables",
            "name": "append_accept_loopback_output",
            "__sls__": "iptables",
            "__env__": "base",
            "__id__": "append_accept_loopback_output",
            "table": "filter",
            "chain": "OUTPUT",
            "out-interface": "lo",
            "jump": "ACCEPT",
            "save": True,
            "order": 10001,
            "fun": "append",
        },
        {
            "state": "iptables",
            "name": "append_drop_non_loopback",
            "__sls__": "iptables",
            "__env__": "base",
            "__id__": "append_drop_non_loopback",
            "table": "filter",
            "chain": "INPUT",
            "source": "127.0.0.0/8",
            "jump": "DROP",
            "save": True,
            "order": 10002,
            "fun": "append",
        },
    ]

    expected = {
        "state": "iptables",
        "name": "accept_local_interface",
        "__sls__": "iptables",
        "__env__": "base",
        "__id__": "append_accept_local_interface",
        "table": "filter",
        "chain": "INPUT",
        "in-interface": "lo",
        "jump": "ACCEPT",
        "save": True,
        "order": 10000,
        "fun": "append",
        "rules": [
            {
                "state": "iptables",
                "name": "accept_local_interface",
                "__sls__": "iptables",
                "__env__": "base",
                "__id__": "append_accept_local_interface",
                "table": "filter",
                "chain": "INPUT",
                "in-interface": "lo",
                "jump": "ACCEPT",
                "save": True,
                "order": 10000,
                "fun": "append",
            },
            {
                "state": "iptables",
                "name": "append_accept_loopback_output",
                "__sls__": "iptables",
                "__env__": "base",
                "__id__": "append_accept_loopback_output",
                "table": "filter",
                "chain": "OUTPUT",
                "out-interface": "lo",
                "jump": "ACCEPT",
                "save": True,
                "order": 10001,
                "fun": "append",
            },
            {
                "state": "iptables",
                "name": "append_drop_non_loopback",
                "__sls__": "iptables",
                "__env__": "base",
                "__id__": "append_drop_non_loopback",
                "table": "filter",
                "chain": "INPUT",
                "source": "127.0.0.0/8",
                "jump": "DROP",
                "save": True,
                "order": 10002,
                "fun": "append",
            },
        ],
    }

    res = iptables.mod_aggregate(low, chunks, {})
    assert res == expected
