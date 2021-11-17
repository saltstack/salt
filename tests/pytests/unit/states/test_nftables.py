"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import salt.states.nftables as nftables
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {nftables: {}}


def test_chain_present():
    """
    Test to verify the chain is exist.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(
        side_effect=[
            {"result": True, "comment": ""},
            {"result": False, "comment": ""},
            {"result": False, "comment": ""},
        ]
    )
    with patch.dict(nftables.__salt__, {"nftables.check_chain": mock}):
        ret.update(
            {"comment": "nftables salt chain is already exist in filter table for ipv4"}
        )
        assert nftables.chain_present("salt") == ret

        mock = MagicMock(
            side_effect=[
                {"result": True, "comment": ""},
                {"result": False, "comment": ""},
            ]
        )
        with patch.dict(nftables.__salt__, {"nftables.new_chain": mock}):
            with patch.dict(nftables.__opts__, {"test": False}):
                ret.update(
                    {
                        "changes": {"locale": "salt"},
                        "comment": (
                            "nftables salt chain in filter table create success for"
                            " ipv4"
                        ),
                    }
                )
                assert nftables.chain_present("salt") == ret

                ret.update(
                    {
                        "changes": {},
                        "comment": (
                            "Failed to create salt chain in filter table:  for ipv4"
                        ),
                        "result": False,
                    }
                )
                assert nftables.chain_present("salt") == ret


def test_chain_absent():
    """
    Test to verify the chain is absent.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[False, True])
    with patch.dict(nftables.__salt__, {"nftables.check_chain": mock}):
        ret.update(
            {
                "comment": (
                    "nftables salt chain is already absent in filter table for ipv4"
                )
            }
        )
        assert nftables.chain_absent("salt") == ret

        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"nftables.flush": mock}):
            ret.update(
                {
                    "result": False,
                    "comment": "Failed to flush salt chain in filter table:  for ipv4",
                }
            )
            assert nftables.chain_absent("salt") == ret


def test_append():
    """
    Test to append a rule to a chain
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(return_value=[])
    with patch.object(nftables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value={"result": True, "comment": "", "rule": "a"})
        with patch.dict(nftables.__salt__, {"nftables.build_rule": mock}):
            mock = MagicMock(
                side_effect=[
                    {"result": True, "comment": ""},
                    {"result": False, "comment": ""},
                    {"result": False, "comment": ""},
                    {"result": False, "comment": ""},
                ]
            )
            with patch.dict(nftables.__salt__, {"nftables.check": mock}):
                ret.update(
                    {"comment": "nftables rule for salt already set (a) for ipv4"}
                )
                assert nftables.append("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "nftables rule for salt needs to be set (a) for ipv4"
                            ),
                        }
                    )
                    assert nftables.append("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": False}):
                    mock = MagicMock(
                        side_effect=[
                            {"result": True, "comment": ""},
                            {"result": False, "comment": ""},
                        ]
                    )
                    with patch.dict(nftables.__salt__, {"nftables.append": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "comment": "Set nftables rule for salt to: a for ipv4",
                                "result": True,
                            }
                        )
                        assert nftables.append("salt", table="", chain="") == ret

                        ret.update(
                            {
                                "changes": {},
                                "comment": (
                                    "Failed to set nftables rule for"
                                    " salt.\nAttempted rule was a for ipv4.\n"
                                ),
                                "result": False,
                            }
                        )
                        assert nftables.append("salt", table="", chain="") == ret


def test_insert():
    """
    Test to insert a rule into a chain
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(return_value=[])
    with patch.object(nftables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value={"result": True, "comment": "", "rule": "a"})
        with patch.dict(nftables.__salt__, {"nftables.build_rule": mock}):
            mock = MagicMock(
                side_effect=[
                    {"result": True, "comment": ""},
                    {"result": False, "comment": ""},
                    {"result": False, "comment": ""},
                    {"result": False, "comment": ""},
                ]
            )
            with patch.dict(nftables.__salt__, {"nftables.check": mock}):
                ret.update(
                    {"comment": "nftables rule for salt already set for ipv4 (a)"}
                )
                assert nftables.insert("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "nftables rule for salt needs to be set for ipv4 (a)"
                            ),
                        }
                    )
                    assert nftables.insert("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": False}):
                    mock = MagicMock(
                        side_effect=[
                            {"result": True, "comment": ""},
                            {"result": False, "comment": ""},
                        ]
                    )
                    with patch.dict(nftables.__salt__, {"nftables.insert": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "comment": "Set nftables rule for salt to: a for ipv4",
                                "result": True,
                            }
                        )
                        assert (
                            nftables.insert("salt", table="", chain="", position="")
                            == ret
                        )

                        ret.update(
                            {
                                "changes": {},
                                "comment": (
                                    "Failed to set nftables rule for"
                                    " salt.\nAttempted rule was a"
                                ),
                                "result": False,
                            }
                        )
                        assert (
                            nftables.insert("salt", table="", chain="", position="")
                            == ret
                        )


def test_delete():
    """
    Test to delete a rule to a chain
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

    mock = MagicMock(return_value=[])
    with patch.object(nftables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value={"result": True, "comment": "", "rule": "a"})
        with patch.dict(nftables.__salt__, {"nftables.build_rule": mock}):
            mock = MagicMock(
                side_effect=[
                    {"result": False, "comment": ""},
                    {"result": True, "comment": ""},
                    {"result": True, "comment": ""},
                    {"result": True, "comment": ""},
                ]
            )
            with patch.dict(nftables.__salt__, {"nftables.check": mock}):
                ret.update(
                    {
                        "comment": "nftables rule for salt already absent for ipv4 (a)",
                        "result": True,
                    }
                )
                assert nftables.delete("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "result": None,
                            "comment": (
                                "nftables rule for salt needs to be deleted for"
                                " ipv4 (a)"
                            ),
                        }
                    )
                    assert nftables.delete("salt", table="", chain="") == ret

                with patch.dict(nftables.__opts__, {"test": False}):
                    mock = MagicMock(
                        side_effect=[
                            {"result": True, "comment": ""},
                            {"result": False, "comment": ""},
                        ]
                    )
                    with patch.dict(nftables.__salt__, {"nftables.delete": mock}):
                        ret.update(
                            {
                                "result": True,
                                "changes": {"locale": "salt"},
                                "comment": "Delete nftables rule for salt a",
                            }
                        )
                        assert (
                            nftables.delete("salt", table="", chain="", position="")
                            == ret
                        )

                        ret.update(
                            {
                                "result": False,
                                "changes": {},
                                "comment": (
                                    "Failed to delete nftables rule for"
                                    " salt.\nAttempted rule was a"
                                ),
                            }
                        )
                        assert (
                            nftables.delete("salt", table="", chain="", position="")
                            == ret
                        )


def test_flush():
    """
    Test to flush current nftables state
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}
    mock = MagicMock(return_value=[])
    with patch.object(nftables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(
            side_effect=[
                {"result": False, "comment": ""},
                {"result": True, "comment": ""},
                {"result": True, "comment": ""},
                {"result": True, "comment": ""},
            ]
        )
        with patch.dict(nftables.__salt__, {"nftables.check_table": mock}):
            with patch.dict(nftables.__opts__, {"test": False}):
                ret.update(
                    {
                        "comment": (
                            "Failed to flush table  in family ipv4, table does not"
                            " exist."
                        ),
                        "result": False,
                    }
                )
                assert (
                    nftables.flush("salt", table="", chain="", ignore_absence=False)
                    == ret
                )

                mock = MagicMock(
                    side_effect=[
                        {"result": False, "comment": ""},
                        {"result": True, "comment": ""},
                        {"result": True, "comment": ""},
                    ]
                )
                with patch.dict(nftables.__salt__, {"nftables.check_chain": mock}):
                    ret.update(
                        {
                            "comment": (
                                "Failed to flush chain  in table  in family ipv4, chain"
                                " does not exist."
                            )
                        }
                    )
                    assert (
                        nftables.flush("salt", table="", chain="", ignore_absence=False)
                        == ret
                    )

                    mock = MagicMock(
                        side_effect=[
                            {"result": True, "comment": ""},
                            {"result": False, "comment": ""},
                        ]
                    )
                    with patch.dict(nftables.__salt__, {"nftables.flush": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "comment": (
                                    "Flush nftables rules in  table  chain ipv4 family"
                                ),
                                "result": True,
                            }
                        )
                        assert nftables.flush("salt", table="", chain="") == ret

                        ret.update(
                            {
                                "changes": {},
                                "comment": "Failed to flush nftables rules",
                                "result": False,
                            }
                        )
                        assert nftables.flush("salt", table="", chain="") == ret


def test_set_policy():
    """
    Test to sets the default policy for nftables firewall tables
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(return_value=[])
    with patch.object(nftables, "_STATE_INTERNAL_KEYWORDS", mock):
        mock = MagicMock(return_value="stack")
        with patch.dict(nftables.__salt__, {"nftables.get_policy": mock}):
            ret.update(
                {
                    "comment": (
                        "nftables default policy for chain"
                        "  on table  for ipv4 already set to stack"
                    )
                }
            )
            assert (
                nftables.set_policy("salt", table="", chain="", policy="stack") == ret
            )

            with patch.dict(nftables.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": (
                            "nftables default policy for chain  on table  for "
                            "ipv4 needs to be set to sal"
                        ),
                        "result": None,
                    }
                )
                assert (
                    nftables.set_policy("salt", table="", chain="", policy="sal") == ret
                )

            with patch.dict(nftables.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, False])
                with patch.dict(nftables.__salt__, {"nftables.set_policy": mock}):
                    ret.update(
                        {
                            "changes": {"locale": "salt"},
                            "comment": "Set default policy for  to sal family ipv4",
                            "result": True,
                        }
                    )
                    assert (
                        nftables.set_policy("salt", table="", chain="", policy="sal")
                        == ret
                    )

                    ret.update(
                        {
                            "comment": "Failed to set nftables default policy",
                            "result": False,
                            "changes": {},
                        }
                    )
                    assert (
                        nftables.set_policy("salt", table="", chain="", policy="sal")
                        == ret
                    )


def test_table_present():
    """
    Test to verify a table exists.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(
        side_effect=[
            {"result": True},
            {"result": False},
            {"result": False},
            {"result": False},
        ]
    )
    with patch.dict(nftables.__salt__, {"nftables.check_table": mock}):
        ret.update({"comment": "nftables table salt already exists in family ipv4"})
        assert nftables.table_present("salt") == ret

        with patch.dict(nftables.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": "nftables table salt would be created in family ipv4",
                    "result": None,
                }
            )
            assert nftables.table_present("salt") == ret

        with patch.dict(nftables.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[{"result": True}, {"result": False}])
            with patch.dict(nftables.__salt__, {"nftables.new_table": mock}):
                ret.update(
                    {
                        "result": True,
                        "comment": (
                            "nftables table salt successfully created in family ipv4"
                        ),
                        "changes": {"locale": "salt"},
                    }
                )
                assert nftables.table_present("salt") == ret

                ret.update(
                    {
                        "changes": {},
                        "result": False,
                        "comment": "Failed to create table salt for family ipv4",
                    }
                )
                assert nftables.table_present("salt") == ret


def test_table_absent():
    """
    Test to verify a table is absent.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(
        side_effect=[
            {"result": False},
            {"result": True},
            {"result": True},
            {"result": True},
        ]
    )
    with patch.dict(nftables.__salt__, {"nftables.check_table": mock}):
        ret.update(
            {"comment": "nftables table salt is already absent from family ipv4"}
        )
        assert nftables.table_absent("salt") == ret

        with patch.dict(nftables.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": "nftables table salt would be deleted from family ipv4",
                    "result": None,
                }
            )
            assert nftables.table_absent("salt") == ret

        with patch.dict(nftables.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[False, "a"])
            with patch.dict(nftables.__salt__, {"nftables.flush": mock}):
                mock = MagicMock(side_effect=[{"result": True}, {"result": False}])
                with patch.dict(nftables.__salt__, {"nftables.delete_table": mock}):
                    ret.update(
                        {
                            "changes": {"locale": "salt"},
                            "comment": (
                                "nftables table salt successfully deleted from family"
                                " ipv4"
                            ),
                            "result": True,
                        }
                    )
                    assert nftables.table_absent("salt") == ret

                    ret.update(
                        {
                            "changes": {},
                            "result": False,
                            "comment": "Failed to delete table salt from family ipv4",
                        }
                    )
                    assert nftables.table_absent("salt") == ret
