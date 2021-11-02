"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import json

import salt.modules.nftables as nftables
import salt.utils.files
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class NftablesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.nftables
    """

    def setup_loader_modules(self):
        return {nftables: {}}

    # 'version' function tests: 1

    def test_version(self):
        """
        Test if it return version from nftables --version
        """
        mock = MagicMock(return_value="nf_tables 0.3-1")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.version(), "0.3-1")

    # 'build_rule' function tests: 1

    def test_build_rule(self):
        """
        Test if it build a well-formatted nftables rule based on kwargs.
        """
        self.assertEqual(
            nftables.build_rule(full="True"),
            {"result": False, "rule": "", "comment": "Table needs to be specified"},
        )

        self.assertEqual(
            nftables.build_rule(table="filter", full="True"),
            {"result": False, "rule": "", "comment": "Chain needs to be specified"},
        )

        self.assertEqual(
            nftables.build_rule(table="filter", chain="input", full="True"),
            {"result": False, "rule": "", "comment": "Command needs to be specified"},
        )

        self.assertEqual(
            nftables.build_rule(
                table="filter",
                chain="input",
                command="insert",
                position="3",
                full="True",
            ),
            {
                "result": True,
                "rule": "nft insert rule ip filter input position 3 ",
                "comment": "Successfully built rule",
            },
        )

        self.assertEqual(
            nftables.build_rule(
                table="filter", chain="input", command="insert", full="True"
            ),
            {
                "result": True,
                "rule": "nft insert rule ip filter input ",
                "comment": "Successfully built rule",
            },
        )

        self.assertEqual(
            nftables.build_rule(
                table="filter", chain="input", command="halt", full="True"
            ),
            {
                "result": True,
                "rule": "nft halt rule ip filter input ",
                "comment": "Successfully built rule",
            },
        )

        self.assertEqual(
            nftables.build_rule(
                table="filter",
                chain="input",
                command="insert",
                position="3",
                full="True",
                connstate="related,established",
                saddr="10.0.0.1",
                daddr="10.0.0.2",
                jump="accept",
            ),
            {
                "result": True,
                "rule": (
                    "nft insert rule ip filter input position 3 ct state {"
                    " related,established } ip saddr 10.0.0.1 ip daddr 10.0.0.2 accept"
                ),
                "comment": "Successfully built rule",
            },
        )

        self.assertEqual(
            nftables.build_rule(), {"result": True, "rule": "", "comment": ""}
        )

    # 'get_saved_rules' function tests: 1

    def test_get_saved_rules(self):
        """
        Test if it return a data structure of the rules in the conf file
        """
        with patch.dict(nftables.__grains__, {"os_family": "Debian"}):
            with patch.object(salt.utils.files, "fopen", MagicMock(mock_open())):
                self.assertListEqual(nftables.get_saved_rules(), [])

    # 'list_tables' function tests: 1

    def test_list_tables(self):
        """
        Test if it return a data structure of the current, in-memory tables
        """
        list_tables = [{"family": "inet", "name": "filter", "handle": 2}]
        list_tables_mock = MagicMock(return_value=list_tables)

        with patch.object(nftables, "list_tables", list_tables_mock):
            self.assertListEqual(nftables.list_tables(), list_tables)

        list_tables_mock = MagicMock(return_value=[])
        with patch.object(nftables, "list_tables", list_tables_mock):
            self.assertListEqual(nftables.list_tables(), [])

    # 'get_rules' function tests: 1

    def test_get_rules(self):
        """
        Test if it return a data structure of the current, in-memory rules
        """
        list_tables_mock = MagicMock(
            return_value=[{"family": "inet", "name": "filter", "handle": 2}]
        )
        list_rules_return = """table inet filter {
            chain input {
                type filter hook input priority 0; policy accept;
            }

            chain forward {
                type filter hook forward priority 0; policy accept;
            }

            chain output {
                type filter hook output priority 0; policy accept;
            }
        }"""
        list_rules_mock = MagicMock(return_value=list_rules_return)
        expected = [list_rules_return]

        with patch.object(nftables, "list_tables", list_tables_mock):
            with patch.dict(nftables.__salt__, {"cmd.run": list_rules_mock}):
                self.assertListEqual(nftables.get_rules(), expected)

        list_tables_mock = MagicMock(return_value=[])
        with patch.object(nftables, "list_tables", list_tables_mock):
            self.assertListEqual(nftables.get_rules(), [])

    # 'get_rules_json' function tests: 1

    def test_get_rules_json(self):
        """
        Test if it return a data structure of the current, in-memory rules
        """
        list_rules_return = """
        {
          "nftables": [
            {
              "table": {
                "family": "ip",
                "name": "filter",
                "handle": 47
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "input",
                "handle": 1,
                "type": "filter",
                "hook": "input",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "forward",
                "handle": 2,
                "type": "filter",
                "hook": "forward",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "output",
                "handle": 3,
                "type": "filter",
                "hook": "output",
                "prio": 0,
                "policy": "accept"
              }
            }
          ]
        }
        """
        list_rules_mock = MagicMock(return_value=list_rules_return)
        expected = json.loads(list_rules_return)["nftables"]

        with patch.dict(nftables.__salt__, {"cmd.run": list_rules_mock}):
            self.assertListEqual(nftables.get_rules_json(), expected)

        list_rules_mock = MagicMock(return_value=[])
        with patch.dict(nftables.__salt__, {"cmd.run": list_rules_mock}):
            self.assertListEqual(nftables.get_rules_json(), [])

    # 'save' function tests: 1

    def test_save(self):
        """
        Test if it save the current in-memory rules to disk
        """
        with patch.dict(nftables.__grains__, {"os_family": "Debian"}):
            mock = MagicMock(return_value=False)
            with patch.dict(nftables.__salt__, {"file.directory_exists": mock}):
                with patch.dict(nftables.__salt__, {"cmd.run": mock}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        self.assertEqual(nftables.save(), "#! nft -f\n\n")

                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(side_effect=IOError)
                    ):
                        self.assertRaises(CommandExecutionError, nftables.save)

    # 'get_rule_handle' function tests: 1

    def test_get_rule_handle(self):
        """
        Test if it get the handle for a particular rule
        """
        self.assertEqual(
            nftables.get_rule_handle(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        self.assertEqual(
            nftables.get_rule_handle(chain="input"),
            {"result": False, "comment": "Rule needs to be specified"},
        )

        _ru = "input tcp dport 22 log accept"
        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.get_rule_handle(chain="input", rule=_ru), ret)

        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 does not exist",
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.get_rule_handle(chain="input", rule=_ru), ret)

        ret = {
            "result": False,
            "comment": (
                "Rule input tcp dport 22 log accept chain"
                " input in table filter in family ipv4 does not exist"
            ),
        }
        ret1 = {
            "result": False,
            "comment": "Could not find rule input tcp dport 22 log accept",
        }
        with patch.object(
            nftables,
            "check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            with patch.object(
                nftables,
                "check_chain",
                MagicMock(return_value={"result": True, "comment": ""}),
            ):
                _ret1 = {
                    "result": False,
                    "comment": (
                        "Rule input tcp dport 22 log accept"
                        " chain input in table filter in"
                        " family ipv4 does not exist"
                    ),
                }
                _ret2 = {"result": True, "comment": ""}
                with patch.object(
                    nftables, "check", MagicMock(side_effect=[_ret1, _ret2])
                ):
                    self.assertEqual(
                        nftables.get_rule_handle(chain="input", rule=_ru), ret
                    )

                    _ru = "input tcp dport 22 log accept"
                    mock = MagicMock(return_value="")
                    with patch.dict(nftables.__salt__, {"cmd.run": mock}):
                        self.assertEqual(
                            nftables.get_rule_handle(chain="input", rule=_ru), ret1
                        )

    # 'check' function tests: 1

    def test_check(self):
        """
        Test if it check for the existence of a rule in the table and chain
        """
        self.assertEqual(
            nftables.check(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        self.assertEqual(
            nftables.check(chain="input"),
            {"result": False, "comment": "Rule needs to be specified"},
        )

        _ru = "tcp dport 22 log accept"
        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check(chain="input", rule=_ru), ret)

        mock = MagicMock(return_value="table ip filter")
        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 does not exist",
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check(chain="input", rule=_ru), ret)

        mock = MagicMock(return_value="table ip filter chain input {{")
        ret = {
            "result": False,
            "comment": (
                "Rule tcp dport 22 log accept in chain input in table filter in family"
                " ipv4 does not exist"
            ),
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check(chain="input", rule=_ru), ret)

        r_val = "table ip filter chain input {{ input tcp dport 22 log accept #"
        mock = MagicMock(return_value=r_val)
        ret = {
            "result": True,
            "comment": (
                "Rule tcp dport 22 log accept in chain input in table filter in family"
                " ipv4 exists"
            ),
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check(chain="input", rule=_ru), ret)

    # 'check_chain' function tests: 1

    def test_check_chain(self):
        """
        Test if it check for the existence of a chain in the table
        """
        self.assertEqual(
            nftables.check_chain(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        mock = MagicMock(return_value="")
        ret = {
            "comment": "Chain input in table filter in family ipv4 does not exist",
            "result": False,
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check_chain(chain="input"), ret)

        mock = MagicMock(return_value="chain input {{")
        ret = {
            "comment": "Chain input in table filter in family ipv4 exists",
            "result": True,
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check_chain(chain="input"), ret)

    # 'check_table' function tests: 1

    def test_check_table(self):
        """
        Test if it check for the existence of a table
        """
        self.assertEqual(
            nftables.check_table(),
            {"result": False, "comment": "Table needs to be specified"},
        )

        mock = MagicMock(return_value="")
        ret = {"comment": "Table nat in family ipv4 does not exist", "result": False}
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check_table(table="nat"), ret)

        mock = MagicMock(return_value="table ip nat")
        ret = {"comment": "Table nat in family ipv4 exists", "result": True}
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.check_table(table="nat"), ret)

    # 'new_table' function tests: 1

    def test_new_table(self):
        """
        Test if it create new custom table.
        """
        self.assertEqual(
            nftables.new_table(table=None),
            {"result": False, "comment": "Table needs to be specified"},
        )

        mock = MagicMock(return_value="")
        ret = {"comment": "Table nat in family ipv4 created", "result": True}
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.new_table(table="nat"), ret)

        mock = MagicMock(return_value="table ip nat")
        ret = {"comment": "Table nat in family ipv4 exists", "result": True}
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.new_table(table="nat"), ret)

    # 'delete_table' function tests: 1

    def test_delete_table(self):
        """
        Test if it delete custom table.
        """
        self.assertEqual(
            nftables.delete_table(table=None),
            {"result": False, "comment": "Table needs to be specified"},
        )

        mock_ret = {
            "result": False,
            "comment": "Table nat in family ipv4 does not exist",
        }
        with patch(
            "salt.modules.nftables.check_table", MagicMock(return_value=mock_ret)
        ):
            ret = nftables.delete_table(table="nat")
            self.assertEqual(
                ret,
                {"result": False, "comment": "Table nat in family ipv4 does not exist"},
            )

        mock = MagicMock(return_value="table ip nat")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            self.assertEqual(
                nftables.delete_table(table="nat"),
                {
                    "comment": "Table nat in family ipv4 could not be deleted",
                    "result": False,
                },
            )

        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            self.assertEqual(
                nftables.delete_table(table="nat"),
                {"comment": "Table nat in family ipv4 deleted", "result": True},
            )

    # 'new_chain' function tests: 2

    def test_new_chain(self):
        """
        Test if it create new chain to the specified table.
        """
        self.assertEqual(
            nftables.new_chain(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.new_chain(chain="input"), ret)

        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 already exists",
        }
        mock = MagicMock(return_value="table ip filter chain input {{")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.new_chain(chain="input"), ret)

    def test_new_chain_variable(self):
        """
        Test if it create new chain to the specified table.
        """
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": False, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            self.assertEqual(
                nftables.new_chain(chain="input", table_type="filter"),
                {
                    "result": False,
                    "comment": "Table_type, hook, and priority required.",
                },
            )

            self.assertTrue(
                nftables.new_chain(
                    chain="input", table_type="filter", hook="input", priority=0
                )
            )

    # 'delete_chain' function tests: 1

    def test_delete_chain(self):
        """
        Test if it delete the chain from the specified table.
        """
        self.assertEqual(
            nftables.delete_chain(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.delete_chain(chain="input"), ret)

        ret = {
            "result": False,
            "comment": (
                "Chain input in table filter in family ipv4 could not be deleted"
            ),
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            self.assertEqual(nftables.delete_chain(chain="input"), ret)

        ret = {
            "result": True,
            "comment": "Chain input in table filter in family ipv4 deleted",
        }
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            self.assertEqual(nftables.delete_chain(chain="input"), ret)

    def test_delete_chain_variables(self):
        """
        Test if it delete the chain from the specified table.
        """
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            _expected = {
                "comment": "Chain input in table filter in family ipv4 deleted",
                "result": True,
            }
            self.assertEqual(nftables.delete_chain(chain="input"), _expected)

    # 'append' function tests: 2

    def test_append(self):
        """
        Test if it append a rule to the specified table & chain.
        """
        self.assertEqual(
            nftables.append(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        self.assertEqual(
            nftables.append(chain="input"),
            {"result": False, "comment": "Rule needs to be specified"},
        )

        _ru = "input tcp dport 22 log accept"
        ret = {"comment": "Table filter in family ipv4 does not exist", "result": False}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.append(chain="input", rule=_ru), ret)

        ret = {
            "comment": "Chain input in table filter in family ipv4 does not exist",
            "result": False,
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.append(chain="input", rule=_ru), ret)

        r_val = "table ip filter chain input {{ input tcp dport 22 log accept #"
        mock = MagicMock(return_value=r_val)
        _expected = {
            "comment": (
                "Rule input tcp dport 22 log accept chain input in table filter in"
                " family ipv4 already exists"
            ),
            "result": False,
        }
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.append(chain="input", rule=_ru), _expected)

    def test_append_rule(self):
        """
        Test if it append a rule to the specified table & chain.
        """
        _ru = "input tcp dport 22 log accept"
        mock = MagicMock(side_effect=["1", ""])
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check",
            MagicMock(return_value={"result": False, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            _expected = {
                "comment": (
                    'Failed to add rule "{}" chain input in table filter in family'
                    " ipv4.".format(_ru)
                ),
                "result": False,
            }
            self.assertEqual(nftables.append(chain="input", rule=_ru), _expected)
            _expected = {
                "comment": (
                    'Added rule "{}" chain input in table filter in family ipv4.'.format(
                        _ru
                    )
                ),
                "result": True,
            }
            self.assertEqual(nftables.append(chain="input", rule=_ru), _expected)

    # 'insert' function tests: 2

    def test_insert(self):
        """
        Test if it insert a rule into the specified table & chain,
        at the specified position.
        """
        self.assertEqual(
            nftables.insert(),
            {"result": False, "comment": "Chain needs to be specified"},
        )

        self.assertEqual(
            nftables.insert(chain="input"),
            {"result": False, "comment": "Rule needs to be specified"},
        )

        _ru = "input tcp dport 22 log accept"
        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.insert(chain="input", rule=_ru), ret)

        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 does not exist",
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.insert(chain="input", rule=_ru), ret)

        r_val = "table ip filter chain input {{ input tcp dport 22 log accept #"
        mock = MagicMock(return_value=r_val)
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            res = nftables.insert(chain="input", rule=_ru)
            import logging

            log = logging.getLogger(__name__)
            log.debug("=== res %s ===", res)
            self.assertTrue(nftables.insert(chain="input", rule=_ru))

    def test_insert_rule(self):
        """
        Test if it insert a rule into the specified table & chain,
        at the specified position.
        """
        _ru = "input tcp dport 22 log accept"
        mock = MagicMock(side_effect=["1", ""])
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check",
            MagicMock(return_value={"result": False, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            _expected = {
                "result": False,
                "comment": (
                    'Failed to add rule "{}" chain input in table filter in family'
                    " ipv4.".format(_ru)
                ),
            }
            self.assertEqual(nftables.insert(chain="input", rule=_ru), _expected)
            _expected = {
                "result": True,
                "comment": (
                    'Added rule "{}" chain input in table filter in family ipv4.'.format(
                        _ru
                    )
                ),
            }
            self.assertEqual(nftables.insert(chain="input", rule=_ru), _expected)

    # 'delete' function tests: 2

    def test_delete(self):
        """
        Test if it delete a rule from the specified table & chain,
        specifying either the rule in its entirety, or
        the rule's position in the chain.
        """
        _ru = "input tcp dport 22 log accept"
        ret = {
            "result": False,
            "comment": "Only specify a position or a rule, not both",
        }
        self.assertEqual(
            nftables.delete(table="filter", chain="input", position="3", rule=_ru), ret
        )

        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(
                nftables.delete(table="filter", chain="input", rule=_ru), ret
            )

        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 does not exist",
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(
                nftables.delete(table="filter", chain="input", rule=_ru), ret
            )

        mock = MagicMock(return_value="table ip filter chain input {{")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertTrue(nftables.delete(table="filter", chain="input", rule=_ru))

    def test_delete_rule(self):
        """
        Test if it delete a rule from the specified table & chain,
        specifying either the rule in its entirety, or
        the rule's position in the chain.
        """
        mock = MagicMock(side_effect=["1", ""])
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            _expected = {
                "result": False,
                "comment": (
                    'Failed to delete rule "None" in chain input  table filter in'
                    " family ipv4"
                ),
            }
            self.assertEqual(
                nftables.delete(table="filter", chain="input", position="3"), _expected
            )
            _expected = {
                "result": True,
                "comment": (
                    'Deleted rule "None" in chain input in table filter in family ipv4.'
                ),
            }
            self.assertEqual(
                nftables.delete(table="filter", chain="input", position="3"), _expected
            )

    # 'flush' function tests: 2

    def test_flush(self):
        """
        Test if it flush the chain in the specified table, flush all chains
        in the specified table if chain is not specified.
        """
        ret = {"result": False, "comment": "Table filter in family ipv4 does not exist"}
        mock = MagicMock(return_value="")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.flush(table="filter", chain="input"), ret)

        ret = {
            "result": False,
            "comment": "Chain input in table filter in family ipv4 does not exist",
        }
        mock = MagicMock(return_value="table ip filter")
        with patch.dict(nftables.__salt__, {"cmd.run": mock}):
            self.assertEqual(nftables.flush(table="filter", chain="input"), ret)

    def test_flush_chain(self):
        """
        Test if it flush the chain in the specified table, flush all chains
        in the specified table if chain is not specified.
        """
        mock = MagicMock(side_effect=["1", ""])
        with patch.dict(nftables.__salt__, {"cmd.run": mock}), patch(
            "salt.modules.nftables.check_chain",
            MagicMock(return_value={"result": True, "comment": ""}),
        ), patch(
            "salt.modules.nftables.check_table",
            MagicMock(return_value={"result": True, "comment": ""}),
        ):
            _expected = {
                "result": False,
                "comment": (
                    "Failed to flush rules from chain input in table filter in family"
                    " ipv4."
                ),
            }
            self.assertEqual(nftables.flush(table="filter", chain="input"), _expected)
            _expected = {
                "result": True,
                "comment": (
                    "Flushed rules from chain input in table filter in family ipv4."
                ),
            }
            self.assertEqual(nftables.flush(table="filter", chain="input"), _expected)

    # 'get_policy' function tests: 1

    def test_get_policy(self):
        """
        Test the current policy for the specified table/chain
        """
        list_rules_return = """
        {
          "nftables": [
            {
              "table": {
                "family": "ip",
                "name": "filter",
                "handle": 47
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "input",
                "handle": 1,
                "type": "filter",
                "hook": "input",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "forward",
                "handle": 2,
                "type": "filter",
                "hook": "forward",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "output",
                "handle": 3,
                "type": "filter",
                "hook": "output",
                "prio": 0,
                "policy": "accept"
              }
            }
          ]
        }
        """
        expected = json.loads(list_rules_return)

        self.assertEqual(
            nftables.get_policy(table="filter", chain=None, family="ipv4"),
            "Error: Chain needs to be specified",
        )

        with patch.object(nftables, "get_rules_json", MagicMock(return_value=expected)):
            self.assertEqual(
                nftables.get_policy(table="filter", chain="input", family="ipv4"),
                "accept",
            )

        with patch.object(nftables, "get_rules_json", MagicMock(return_value=expected)):
            self.assertIsNone(
                nftables.get_policy(table="filter", chain="missing", family="ipv4")
            )

    # 'set_policy' function tests: 1

    def test_set_policy(self):
        """
        Test set the current policy for the specified table/chain
        """
        list_rules_return = """
        {
          "nftables": [
            {
              "table": {
                "family": "ip",
                "name": "filter",
                "handle": 47
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "input",
                "handle": 1,
                "type": "filter",
                "hook": "input",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "forward",
                "handle": 2,
                "type": "filter",
                "hook": "forward",
                "prio": 0,
                "policy": "accept"
              }
            },
            {
              "chain": {
                "family": "ip",
                "table": "filter",
                "name": "output",
                "handle": 3,
                "type": "filter",
                "hook": "output",
                "prio": 0,
                "policy": "accept"
              }
            }
          ]
        }
        """
        expected = json.loads(list_rules_return)["nftables"]

        self.assertEqual(
            nftables.set_policy(table="filter", chain=None, policy=None, family="ipv4"),
            "Error: Chain needs to be specified",
        )

        self.assertEqual(
            nftables.set_policy(
                table="filter", chain="input", policy=None, family="ipv4"
            ),
            "Error: Policy needs to be specified",
        )

        mock = MagicMock(return_value={"retcode": 0})
        with patch.object(nftables, "get_rules_json", MagicMock(return_value=expected)):
            with patch.dict(nftables.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(
                    nftables.set_policy(
                        table="filter", chain="input", policy="accept", family="ipv4"
                    )
                )
