# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.iptables as iptables

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class IptablesTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the iptables state
    """

    def setup_loader_modules(self):
        return {iptables: {}}

    def test_chain_present(self):
        """
            Test to verify the chain is exist.
        """
        ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.dict(iptables.__salt__, {"iptables.check_chain": mock}):
            ret.update(
                {
                    "comment": "iptables salt chain is already"
                    " exist in filter table for ipv4"
                }
            )
            self.assertDictEqual(iptables.chain_present("salt"), ret)

            with patch.dict(iptables.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "iptables salt chain in filter"
                        " table needs to be set for ipv4",
                        "result": None,
                    }
                )
                self.assertDictEqual(iptables.chain_present("salt"), ret)

            with patch.dict(iptables.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, ""])
                with patch.dict(iptables.__salt__, {"iptables.new_chain": mock}):
                    ret.update(
                        {
                            "result": True,
                            "comment": "iptables salt chain in filter"
                            " table create success for ipv4",
                            "changes": {"locale": "salt"},
                        }
                    )
                    self.assertDictEqual(iptables.chain_present("salt"), ret)

                    ret.update(
                        {
                            "changes": {},
                            "result": False,
                            "comment": "Failed to create salt chain"
                            " in filter table:  for ipv4",
                        }
                    )
                    self.assertDictEqual(iptables.chain_present("salt"), ret)

    def test_chain_absent(self):
        """
            Test to verify the chain is absent.
        """
        ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

        mock = MagicMock(side_effect=[False, True, True, True])
        with patch.dict(iptables.__salt__, {"iptables.check_chain": mock}):
            ret.update(
                {
                    "comment": "iptables salt chain is already"
                    " absent in filter table for ipv4"
                }
            )
            self.assertDictEqual(iptables.chain_absent("salt"), ret)

            with patch.dict(iptables.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "iptables salt chain in filter"
                        " table needs to be removed ipv4",
                        "result": None,
                    }
                )
                self.assertDictEqual(iptables.chain_absent("salt"), ret)

            with patch.dict(iptables.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[False, "a"])
                with patch.dict(iptables.__salt__, {"iptables.flush": mock}):
                    mock = MagicMock(return_value=True)
                    with patch.dict(iptables.__salt__, {"iptables.delete_chain": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "comment": "iptables salt chain in filter"
                                " table delete success for ipv4",
                                "result": True,
                            }
                        )
                        self.assertDictEqual(iptables.chain_absent("salt"), ret)

                    ret.update(
                        {
                            "changes": {},
                            "result": False,
                            "comment": "Failed to flush salt chain"
                            " in filter table: a for ipv4",
                        }
                    )
                    self.assertDictEqual(iptables.chain_absent("salt"), ret)

    def test_append(self):
        """
            Test to append a rule to a chain
        """
        ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

        self.assertDictEqual(iptables.append("salt", rules=[]), ret)

        mock = MagicMock(return_value=[])
        with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
            mock = MagicMock(return_value="a")
            with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
                mock = MagicMock(side_effect=[True, False, False, False])
                with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                    ret.update(
                        {
                            "comment": "iptables rule for salt"
                            " already set (a) for ipv4",
                            "result": True,
                        }
                    )
                    self.assertDictEqual(
                        iptables.append("salt", table="", chain=""), ret
                    )

                    with patch.dict(iptables.__opts__, {"test": True}):
                        ret.update(
                            {
                                "result": None,
                                "comment": "iptables rule for salt"
                                " needs to be set (a) for ipv4",
                            }
                        )
                        self.assertDictEqual(
                            iptables.append("salt", table="", chain=""), ret
                        )

                    with patch.dict(iptables.__opts__, {"test": False}):
                        mock = MagicMock(side_effect=[True, False])
                        with patch.dict(iptables.__salt__, {"iptables.append": mock}):
                            ret.update(
                                {
                                    "changes": {"locale": "salt"},
                                    "result": True,
                                    "comment": "Set iptables rule"
                                    " for salt to: a for ipv4",
                                }
                            )
                            self.assertDictEqual(
                                iptables.append("salt", table="", chain=""), ret
                            )

                            ret.update(
                                {
                                    "changes": {},
                                    "result": False,
                                    "comment": "Failed to set iptables"
                                    " rule for salt.\nAttempted rule was"
                                    " a for ipv4",
                                }
                            )
                            self.assertDictEqual(
                                iptables.append("salt", table="", chain=""), ret
                            )

    def test_insert(self):
        """
            Test to insert a rule into a chain
        """
        ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

        self.assertDictEqual(iptables.insert("salt", rules=[]), ret)

        mock = MagicMock(return_value=[])
        with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
            mock = MagicMock(return_value="a")
            with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
                mock = MagicMock(side_effect=[True, False, False, False])
                with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                    ret.update(
                        {
                            "comment": "iptables rule for salt"
                            " already set for ipv4 (a)",
                            "result": True,
                        }
                    )
                    self.assertDictEqual(
                        iptables.insert("salt", table="", chain=""), ret
                    )

                    with patch.dict(iptables.__opts__, {"test": True}):
                        ret.update(
                            {
                                "result": None,
                                "comment": "iptables rule for salt"
                                " needs to be set for ipv4 (a)",
                            }
                        )
                        self.assertDictEqual(
                            iptables.insert("salt", table="", chain=""), ret
                        )

                    with patch.dict(iptables.__opts__, {"test": False}):
                        mock = MagicMock(side_effect=[False, True])
                        with patch.dict(iptables.__salt__, {"iptables.insert": mock}):
                            ret.update(
                                {
                                    "changes": {"locale": "salt"},
                                    "result": True,
                                    "comment": "Set iptables rule"
                                    " for salt to: a for ipv4",
                                }
                            )
                            self.assertDictEqual(
                                iptables.insert(
                                    "salt", table="", chain="", position=""
                                ),
                                ret,
                            )

                            ret.update(
                                {
                                    "changes": {},
                                    "result": False,
                                    "comment": "Failed to set iptables"
                                    " rule for salt.\nAttempted rule was a",
                                }
                            )
                            self.assertDictEqual(
                                iptables.insert(
                                    "salt", table="", chain="", position=""
                                ),
                                ret,
                            )

    def test_delete(self):
        """
            Test to delete a rule to a chain
        """
        ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

        self.assertDictEqual(iptables.delete("salt", rules=[]), ret)

        mock = MagicMock(return_value=[])
        with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
            mock = MagicMock(return_value="a")
            with patch.dict(iptables.__salt__, {"iptables.build_rule": mock}):
                mock = MagicMock(side_effect=[False, True, True, True])
                with patch.dict(iptables.__salt__, {"iptables.check": mock}):
                    ret.update(
                        {
                            "comment": "iptables rule for salt"
                            " already absent for ipv4 (a)",
                            "result": True,
                        }
                    )
                    self.assertDictEqual(
                        iptables.delete("salt", table="", chain=""), ret
                    )

                    with patch.dict(iptables.__opts__, {"test": True}):
                        ret.update(
                            {
                                "result": None,
                                "comment": "iptables rule for salt needs"
                                " to be deleted for ipv4 (a)",
                            }
                        )
                        self.assertDictEqual(
                            iptables.delete("salt", table="", chain=""), ret
                        )

                    with patch.dict(iptables.__opts__, {"test": False}):
                        mock = MagicMock(side_effect=[False, True])
                        with patch.dict(iptables.__salt__, {"iptables.delete": mock}):
                            ret.update(
                                {
                                    "result": True,
                                    "changes": {"locale": "salt"},
                                    "comment": "Delete iptables rule" " for salt a",
                                }
                            )
                            self.assertDictEqual(
                                iptables.delete(
                                    "salt", table="", chain="", position=""
                                ),
                                ret,
                            )

                            ret.update(
                                {
                                    "result": False,
                                    "changes": {},
                                    "comment": "Failed to delete iptables"
                                    " rule for salt.\nAttempted rule was a",
                                }
                            )
                            self.assertDictEqual(
                                iptables.delete(
                                    "salt", table="", chain="", position=""
                                ),
                                ret,
                            )

    def test_set_policy(self):
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
                        "comment": "iptables default policy for chain"
                        "  on table  for ipv4 already set to stack"
                    }
                )
                self.assertDictEqual(
                    iptables.set_policy("salt", table="", chain="", policy="stack"), ret
                )

                with patch.dict(iptables.__opts__, {"test": True}):
                    ret.update(
                        {
                            "comment": "iptables default policy for chain"
                            "  on table  for ipv4 needs to be set"
                            " to sal",
                            "result": None,
                        }
                    )
                    self.assertDictEqual(
                        iptables.set_policy("salt", table="", chain="", policy="sal"),
                        ret,
                    )

                with patch.dict(iptables.__opts__, {"test": False}):
                    mock = MagicMock(side_effect=[False, True])
                    with patch.dict(iptables.__salt__, {"iptables.set_policy": mock}):
                        ret.update(
                            {
                                "changes": {"locale": "salt"},
                                "comment": "Set default policy for"
                                "  to sal family ipv4",
                                "result": True,
                            }
                        )
                        self.assertDictEqual(
                            iptables.set_policy(
                                "salt", table="", chain="", policy="sal"
                            ),
                            ret,
                        )

                        ret.update(
                            {
                                "comment": "Failed to set iptables" " default policy",
                                "result": False,
                                "changes": {},
                            }
                        )
                        self.assertDictEqual(
                            iptables.set_policy(
                                "salt", table="", chain="", policy="sal"
                            ),
                            ret,
                        )

    def test_flush(self):
        """
            Test to flush current iptables state
        """
        ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}

        mock = MagicMock(return_value=[])
        with patch.object(iptables, "_STATE_INTERNAL_KEYWORDS", mock):
            with patch.dict(iptables.__opts__, {"test": True}):
                ret.update(
                    {
                        "comment": "iptables rules in salt table filter"
                        " chain ipv4 family needs to be flushed"
                    }
                )
                self.assertDictEqual(iptables.flush("salt"), ret)

            with patch.dict(iptables.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[False, True])
                with patch.dict(iptables.__salt__, {"iptables.flush": mock}):
                    ret.update(
                        {
                            "changes": {"locale": "salt"},
                            "comment": "Flush iptables rules in  "
                            "table  chain ipv4 family",
                            "result": True,
                        }
                    )
                    self.assertDictEqual(
                        iptables.flush("salt", table="", chain=""), ret
                    )

                    ret.update(
                        {
                            "changes": {},
                            "comment": "Failed to flush iptables rules",
                            "result": False,
                        }
                    )
                    self.assertDictEqual(
                        iptables.flush("salt", table="", chain=""), ret
                    )

    def test_mod_aggregate(self):
        """
            Test to mod_aggregate function
        """
        self.assertDictEqual(
            iptables.mod_aggregate({"fun": "salt"}, [], []), {"fun": "salt"}
        )

        self.assertDictEqual(
            iptables.mod_aggregate({"fun": "append"}, [], []), {"fun": "append"}
        )
