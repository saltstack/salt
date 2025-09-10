"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import textwrap
import uuid

import pytest

import salt.modules.iptables as iptables
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {iptables: {}}


# 'version' function tests: 1


def test_version():
    """
    Test if it return version from iptables --version
    """
    mock = MagicMock(return_value="iptables v1.4.21")
    with patch.dict(iptables.__salt__, {"cmd.run_stdout": mock}):
        assert iptables.version() == "v1.4.21"


# 'build_rule' function tests: 1


def test_build_rule():
    """
    Test if it build a well-formatted iptables rule based on kwargs.
    """
    with patch.object(iptables, "_has_option", MagicMock(return_value=True)):
        assert iptables.build_rule() == ""

        assert (
            iptables.build_rule(name="ignored", state="ignored") == ""
        ), "build_rule should ignore name and state"

        # Should properly negate bang-prefixed values
        assert iptables.build_rule(**{"if": "!eth0"}) == "! -i eth0"

        # Should properly negate "not"-prefixed values
        assert iptables.build_rule(**{"if": "not eth0"}) == "! -i eth0"

        assert (
            iptables.build_rule(**{"protocol": "tcp", "syn": "!"}) == "-p tcp ! --syn"
        )

        assert (
            iptables.build_rule(dports=[80, 443], protocol="tcp")
            == "-p tcp -m multiport --dports 80,443"
        )

        assert (
            iptables.build_rule(dports="80,443", protocol="tcp")
            == "-p tcp -m multiport --dports 80,443"
        )

        # Should it really behave this way?
        assert (
            iptables.build_rule(dports=["!80", 443], protocol="tcp")
            == "-p tcp -m multiport ! --dports 80,443"
        )

        assert (
            iptables.build_rule(dports="!80,443", protocol="tcp")
            == "-p tcp -m multiport ! --dports 80,443"
        )

        assert (
            iptables.build_rule(sports=[80, 443], protocol="tcp")
            == "-p tcp -m multiport --sports 80,443"
        )

        assert (
            iptables.build_rule(sports="80,443", protocol="tcp")
            == "-p tcp -m multiport --sports 80,443"
        )

        assert (
            iptables.build_rule(
                "filter",
                "INPUT",
                command="I",
                position="3",
                full=True,
                dports="protocol",
                jump="ACCEPT",
            )
            == "Error: protocol must be specified"
        )

        assert (
            iptables.build_rule(
                "filter",
                "INPUT",
                command="I",
                position="3",
                full=True,
                sports="protocol",
                jump="ACCEPT",
            )
            == "Error: protocol must be specified"
        )

        assert (
            iptables.build_rule(
                "",
                "INPUT",
                command="I",
                position="3",
                full="True",
                match="state",
                jump="ACCEPT",
            )
            == "Error: Table needs to be specified"
        )

        assert (
            iptables.build_rule(
                "filter",
                "",
                command="I",
                position="3",
                full="True",
                match="state",
                jump="ACCEPT",
            )
            == "Error: Chain needs to be specified"
        )

        assert (
            iptables.build_rule(
                "filter",
                "INPUT",
                command="",
                position="3",
                full="True",
                match="state",
                jump="ACCEPT",
            )
            == "Error: Command needs to be specified"
        )

        # Test arguments that should appear after the --jump
        assert (
            iptables.build_rule(jump="REDIRECT", **{"to-port": 8080})
            == "--jump REDIRECT --to-port 8080"
        )

        # Should quote arguments with spaces, like log-prefix often has
        assert (
            iptables.build_rule(jump="LOG", **{"log-prefix": "long prefix"})
            == '--jump LOG --log-prefix "long prefix"'
        )

        # Should quote arguments with leading or trailing spaces
        assert (
            iptables.build_rule(jump="LOG", **{"log-prefix": "spam: "})
            == '--jump LOG --log-prefix "spam: "'
        )

        # Should allow no-arg jump options
        assert (
            iptables.build_rule(jump="CLUSTERIP", **{"new": ""})
            == "--jump CLUSTERIP --new"
        )

        # Should allow no-arg jump options as None
        assert (
            iptables.build_rule(jump="CT", **{"notrack": None}) == "--jump CT --notrack"
        )

        # should build match-sets with single string
        assert (
            iptables.build_rule(**{"match-set": "src flag1,flag2"})
            == "-m set --match-set src flag1,flag2"
        )

        # should build match-sets as list
        match_sets = [
            "src1 flag1",
            "src2 flag2,flag3",
        ]
        assert (
            iptables.build_rule(**{"match-set": match_sets})
            == "-m set --match-set src1 flag1 -m set --match-set src2 flag2,flag3"
        )

        # should handle negations for string match-sets
        assert (
            iptables.build_rule(**{"match-set": "!src flag"})
            == "-m set ! --match-set src flag"
        )

        # should handle negations for list match-sets
        match_sets = ["src1 flag", "not src2 flag2"]
        assert (
            iptables.build_rule(**{"match-set": match_sets})
            == "-m set --match-set src1 flag -m set ! --match-set src2 flag2"
        )

        # should allow escaped name
        assert (
            iptables.build_rule(**{"match": "recent", "name_": "SSH"})
            == "-m recent --name SSH"
        )

        # should allow empty arguments
        assert (
            iptables.build_rule(**{"match": "recent", "update": None})
            == "-m recent --update"
        )

        # Should allow the --save jump option to CONNSECMARK
        # assert (
        #    iptables.build_rule(jump='CONNSECMARK', **{'save': ''})
        #    == '--jump CONNSECMARK --save '
        # )

        ret = "/sbin/iptables --wait -t salt -I INPUT 3 -m state --jump ACCEPT"
        with patch.object(
            iptables, "_iptables_cmd", MagicMock(return_value="/sbin/iptables")
        ):
            assert (
                iptables.build_rule(
                    "salt",
                    "INPUT",
                    command="I",
                    position="3",
                    full="True",
                    match="state",
                    jump="ACCEPT",
                )
                == ret
            )


# 'get_saved_rules' function tests: 2


def test_get_saved_rules():
    """
    Test if it return a data structure of the rules in the conf file
    """
    mock = MagicMock(return_value=False)
    with patch.object(iptables, "_parse_conf", mock):
        assert not iptables.get_saved_rules()
        mock.assert_called_with(conf_file=None, family="ipv4")


def test_get_saved_rules_nilinuxrt():
    """
    Test get rules on NILinuxRT system
    """
    data = {
        "/etc/natinst/share/iptables.conf": textwrap.dedent(
            """\
            # Generated by iptables-save v1.6.2 on Thu Oct  8 12:13:44 2020
            *filter
            :INPUT ACCEPT [2958:584773]
            :FORWARD ACCEPT [0:0]
            :OUTPUT ACCEPT [92:23648]
            -A INPUT -p tcp -m tcp --dport 80 -j ACCEPT
            COMMIT
            # Completed on Thu Oct  8 12:13:44 2020
            """
        )
    }
    expected_input_rules = [
        {
            "protocol": ["tcp"],
            "jump": ["ACCEPT"],
            "match": ["tcp"],
            "destination_port": ["80"],
        }
    ]
    file_mock = mock_open(read_data=data)
    with patch.dict(iptables.__grains__, {"os_family": "NILinuxRT", "os": "NILinuxRT"}):
        with patch.object(iptables.salt.utils.files, "fopen", file_mock):
            rules = iptables.get_saved_rules()
            assert expected_input_rules == rules["filter"]["INPUT"]["rules"]


# 'get_rules' function tests: 1


def test_get_rules():
    """
    Test if it return a data structure of the current, in-memory rules
    """
    mock = MagicMock(return_value=False)
    with patch.object(iptables, "_parse_conf", mock):
        assert not iptables.get_rules()
        mock.assert_called_with(in_mem=True, family="ipv4")


# 'get_saved_policy' function tests: 1


def test_get_saved_policy():
    """
    Test if it return the current policy for the specified table/chain
    """
    assert (
        iptables.get_saved_policy(
            table="filter", chain=None, conf_file=None, family="ipv4"
        )
        == "Error: Chain needs to be specified"
    )

    with patch.object(
        iptables,
        "_parse_conf",
        MagicMock(return_value={"filter": {"INPUT": {"policy": True}}}),
    ):
        assert iptables.get_saved_policy(
            table="filter", chain="INPUT", conf_file=None, family="ipv4"
        )

    with patch.object(
        iptables,
        "_parse_conf",
        MagicMock(return_value={"filter": {"INPUT": {"policy1": True}}}),
    ):
        assert (
            iptables.get_saved_policy(
                table="filter", chain="INPUT", conf_file=None, family="ipv4"
            )
            is None
        )


# 'get_policy' function tests: 1


def test_get_policy():
    """
    Test if it return the current policy for the specified table/chain
    """
    assert (
        iptables.get_policy(table="filter", chain=None, family="ipv4")
        == "Error: Chain needs to be specified"
    )

    with patch.object(
        iptables,
        "_parse_conf",
        MagicMock(return_value={"filter": {"INPUT": {"policy": True}}}),
    ):
        assert iptables.get_policy(table="filter", chain="INPUT", family="ipv4")

    with patch.object(
        iptables,
        "_parse_conf",
        MagicMock(return_value={"filter": {"INPUT": {"policy1": True}}}),
    ):
        assert iptables.get_policy(table="filter", chain="INPUT", family="ipv4") is None


# 'set_policy' function tests: 1


def test_set_policy():
    """
    Test if it set the current policy for the specified table/chain
    """
    with patch.object(iptables, "_has_option", MagicMock(return_value=True)):
        assert (
            iptables.set_policy(table="filter", chain=None, policy=None, family="ipv4")
            == "Error: Chain needs to be specified"
        )

        assert (
            iptables.set_policy(
                table="filter", chain="INPUT", policy=None, family="ipv4"
            )
            == "Error: Policy needs to be specified"
        )

        mock = MagicMock(return_value=True)
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock}):
            assert iptables.set_policy(
                table="filter", chain="INPUT", policy="ACCEPT", family="ipv4"
            )


# 'save' function tests: 1


def test_save():
    """
    Test if it save the current in-memory rules to disk
    """
    with patch("salt.modules.iptables._conf", MagicMock(return_value=False)), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(
            iptables.__salt__,
            {
                "cmd.run_stdout": mock,
                "file.write": mock,
                "config.option": MagicMock(return_value=[]),
            },
        ):
            assert iptables.save(filename="/xyz", family="ipv4")


# 'check' function tests: 1


def test_check():
    """
    Test if it check for the existence of a rule in the table and chain
    """
    assert (
        iptables.check(table="filter", chain=None, rule=None, family="ipv4")
        == "Error: Chain needs to be specified"
    )

    assert (
        iptables.check(table="filter", chain="INPUT", rule=None, family="ipv4")
        == "Error: Rule needs to be specified"
    )

    mock_rule = "m state --state RELATED,ESTABLISHED -j ACCEPT"
    mock_chain = "INPUT"
    mock_uuid = 31337
    mock_cmd_rule = MagicMock(return_value=f"-A {mock_chain}\n-A {hex(mock_uuid)}")
    mock_cmd_nooutput = MagicMock(return_value="")
    mock_has = MagicMock(return_value=True)
    mock_not = MagicMock(return_value=False)

    with patch.object(iptables, "_has_option", mock_not):
        with patch.object(uuid, "getnode", MagicMock(return_value=mock_uuid)):
            with patch.dict(
                iptables.__salt__,
                {"cmd.run_stdout": mock_cmd_rule, "cmd.run": mock_cmd_nooutput},
            ):
                assert iptables.check(
                    table="filter",
                    chain=mock_chain,
                    rule=mock_rule,
                    family="ipv4",
                )

    mock_cmd = MagicMock(return_value="")

    with patch.object(iptables, "_has_option", mock_not):
        with patch.object(uuid, "getnode", MagicMock(return_value=mock_uuid)):
            with patch.dict(
                iptables.__salt__,
                {
                    "cmd.run_stdout": mock_cmd_nooutput,
                    "cmd.run": mock_cmd_nooutput,
                },
            ):
                assert not iptables.check(
                    table="filter",
                    chain=mock_chain,
                    rule=mock_rule,
                    family="ipv4",
                )

    with patch.object(iptables, "_has_option", mock_has):
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock_cmd}):
            with patch.dict(iptables.__context__, {"retcode": 1}):
                assert not iptables.check(
                    table="filter", chain="INPUT", rule=mock_rule, family="ipv4"
                )

    mock_cmd = MagicMock(return_value="-A 0x4d2")
    mock_uuid = MagicMock(return_value=1234)

    with patch.object(iptables, "_has_option", mock_has):
        with patch.object(uuid, "getnode", mock_uuid):
            with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock_cmd}):
                with patch.dict(iptables.__context__, {"retcode": 0}):
                    assert iptables.check(
                        table="filter", chain="0x4d2", rule=mock_rule, family="ipv4"
                    )


# 'check_chain' function tests: 1


def test_check_chain():
    """
    Test if it check for the existence of a chain in the table
    """
    assert (
        iptables.check_chain(table="filter", chain=None, family="ipv4")
        == "Error: Chain needs to be specified"
    )

    mock_cmd = MagicMock(return_value="")
    with patch.dict(iptables.__salt__, {"cmd.run_stdout": mock_cmd}):
        assert not iptables.check_chain(table="filter", chain="INPUT", family="ipv4")


# 'new_chain' function tests: 1


def test_new_chain():
    """
    Test if it create new custom chain to the specified table.
    """
    assert (
        iptables.new_chain(table="filter", chain=None, family="ipv4")
        == "Error: Chain needs to be specified"
    )

    mock_cmd = MagicMock(return_value="")
    with patch.dict(
        iptables.__salt__,
        {
            "cmd.run_stdout": mock_cmd,  # called by iptables._has_option
            "cmd.run_stderr": mock_cmd,
        },
    ):
        assert iptables.new_chain(table="filter", chain="INPUT", family="ipv4")


# 'delete_chain' function tests: 1


def test_delete_chain():
    """
    Test if it delete custom chain to the specified table.
    """
    assert (
        iptables.delete_chain(table="filter", chain=None, family="ipv4")
        == "Error: Chain needs to be specified"
    )

    mock_cmd = MagicMock(return_value="")
    with patch.dict(
        iptables.__salt__,
        {
            "cmd.run_stdout": mock_cmd,  # called by iptables._has_option
            "cmd.run_stderr": mock_cmd,
        },
    ):
        assert iptables.delete_chain(table="filter", chain="INPUT", family="ipv4")


# 'append' function tests: 1


def test_append():
    """
    Test if it append a rule to the specified table/chain.
    """
    with patch.object(
        iptables, "_has_option", MagicMock(return_value=True)
    ), patch.object(iptables, "check", MagicMock(return_value=False)):
        assert (
            iptables.append(table="filter", chain=None, rule=None, family="ipv4")
            == "Error: Chain needs to be specified"
        )

        assert (
            iptables.append(table="filter", chain="INPUT", rule=None, family="ipv4")
            == "Error: Rule needs to be specified"
        )

        _rule = "m state --state RELATED,ESTABLISHED -j ACCEPT"
        mock = MagicMock(side_effect=["", "SALT"])
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock}):
            assert iptables.append(
                table="filter", chain="INPUT", rule=_rule, family="ipv4"
            )

            assert not iptables.append(
                table="filter", chain="INPUT", rule=_rule, family="ipv4"
            )


# 'insert' function tests: 1


def test_insert():
    """
    Test if it insert a rule into the specified table/chain,
    at the specified position.
    """
    with patch.object(
        iptables, "_has_option", MagicMock(return_value=True)
    ), patch.object(iptables, "check", MagicMock(return_value=False)):
        assert (
            iptables.insert(
                table="filter", chain=None, position=None, rule=None, family="ipv4"
            )
            == "Error: Chain needs to be specified"
        )

        pos_err = "Error: Position needs to be specified or use append (-A)"
        assert (
            iptables.insert(
                table="filter",
                chain="INPUT",
                position=None,
                rule=None,
                family="ipv4",
            )
            == pos_err
        )

        assert (
            iptables.insert(
                table="filter", chain="INPUT", position=3, rule=None, family="ipv4"
            )
            == "Error: Rule needs to be specified"
        )

        _rule = "m state --state RELATED,ESTABLISHED -j ACCEPT"
        mock = MagicMock(return_value=True)
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock}):
            assert iptables.insert(
                table="filter",
                chain="INPUT",
                position=3,
                rule=_rule,
                family="ipv4",
            )


# 'delete' function tests: 1


def test_delete():
    """
    Test if it delete a rule from the specified table/chain
    """
    with patch.object(iptables, "_has_option", MagicMock(return_value=True)):
        _rule = "m state --state RELATED,ESTABLISHED -j ACCEPT"
        assert (
            iptables.delete(
                table="filter", chain=None, position=3, rule=_rule, family="ipv4"
            )
            == "Error: Only specify a position or a rule, not both"
        )

        mock = MagicMock(return_value=True)
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock}):
            assert iptables.delete(
                table="filter",
                chain="INPUT",
                position=3,
                rule="",
                family="ipv4",
            )


# 'flush' function tests: 1


def test_flush():
    """
    Test if it flush the chain in the specified table,
    flush all chains in the specified table if not specified chain.
    """
    with patch.object(iptables, "_has_option", MagicMock(return_value=True)):
        mock_cmd = MagicMock(return_value=True)
        with patch.dict(iptables.__salt__, {"cmd.run_stderr": mock_cmd}):
            assert iptables.flush(table="filter", chain="INPUT", family="ipv4")
