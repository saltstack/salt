import re

import pytest

import salt.modules.selinux as selinux
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, call, mock_open, patch

pytestmark = [pytest.mark.skip_unless_on_linux]


@pytest.fixture
def configure_loader_modules():
    return {selinux: {}}


def _semanage_list(stdout, retcode=0, stderr=""):
    header = "SELinux fcontext                                   type               Context\n\n"
    return MagicMock(
        return_value={"retcode": retcode, "stdout": header + stdout, "stderr": stderr}
    )


def test_fcontext_get_policy_parsing():
    """
    Test to verify that the parsing of the semanage output into fields is
    correct. Added with #45784.
    """
    cases = [
        {
            "semanage_out": (
                "/var/www(/.*)?     all files         "
                " system_u:object_r:httpd_sys_content_t:s0 "
            ),
            "name": "/var/www(/.*)?",
            "filetype": "all files",
            "sel_user": "system_u",
            "sel_role": "object_r",
            "sel_type": "httpd_sys_content_t",
            "sel_level": "s0",
        },
        {
            "semanage_out": (
                "/var/www(/.*)? all files         "
                " system_u:object_r:httpd_sys_content_t:s0  "
            ),
            "name": "/var/www(/.*)?",
            "filetype": "all files",
            "sel_user": "system_u",
            "sel_role": "object_r",
            "sel_type": "httpd_sys_content_t",
            "sel_level": "s0",
        },
        {
            "semanage_out": (
                "/var/lib/dhcp3?                                    directory      "
                "    system_u:object_r:dhcp_state_t:s0	"
            ),
            "name": "/var/lib/dhcp3?",
            "filetype": "directory",
            "sel_user": "system_u",
            "sel_role": "object_r",
            "sel_type": "dhcp_state_t",
            "sel_level": "s0",
        },
        {
            "semanage_out": (
                "/var/lib/dhcp3?  directory         "
                " system_u:object_r:dhcp_state_t:s0"
            ),
            "name": "/var/lib/dhcp3?",
            "filetype": "directory",
            "sel_user": "system_u",
            "sel_role": "object_r",
            "sel_type": "dhcp_state_t",
            "sel_level": "s0",
        },
        {
            "semanage_out": (
                "/var/lib/dhcp3? directory         "
                " system_u:object_r:dhcp_state_t:s0"
            ),
            "name": "/var/lib/dhcp3?",
            "filetype": "directory",
            "sel_user": "system_u",
            "sel_role": "object_r",
            "sel_type": "dhcp_state_t",
            "sel_level": "s0",
        },
    ]

    for case in cases:
        with patch.dict(
            selinux.__salt__,
            {"cmd.run_all": _semanage_list(case["semanage_out"])},
        ):
            ret = selinux.fcontext_get_policy(case["name"])
            assert ret["filespec"] == case["name"]
            assert ret["filetype"] == case["filetype"]
            assert ret["sel_user"] == case["sel_user"]
            assert ret["sel_role"] == case["sel_role"]
            assert ret["sel_type"] == case["sel_type"]
            assert ret["sel_level"] == case["sel_level"]


@pytest.mark.parametrize(
    "name, protocol, port, expected",
    (
        ("tcp/80", None, None, ("tcp", "80")),
        ("udp/53", None, None, ("udp", "53")),
        ("tcp_test_dns", "tcp", "53", ("tcp", "53")),
        ("udp_test/dns", "udp", "53", ("udp", "53")),
    ),
)
def test_parse_protocol_port_positive(name, protocol, port, expected):
    """
    Test to verify positive parsing name, protocol and port combinations
    """
    ret = selinux._parse_protocol_port(name, protocol, port)
    assert ret == expected


@pytest.mark.parametrize(
    "name, protocol, port",
    (
        ("invalid_name_no_args", None, None),
        ("invalid_proto/80", "nottcp", "80"),
        ("invalid_port", "tcp", "notaport"),
        ("missing_proto", None, "80"),
        ("missing_port", "udp", None),
    ),
)
def test_parse_protocol_port_negative(name, protocol, port):
    """
    Test to verify negative parsing of name, protocol and port combinations
    """
    pytest.raises(
        SaltInvocationError,
        selinux._parse_protocol_port,
        name,
        protocol,
        port,
    )


def test_port_get_policy_parsing():
    """
    Test to verify that the parsing of the semanage port output into fields is correct.
    """
    cases = [
        {
            "semanage_out": "cma_port_t                     tcp      1050",
            "name": "tcp/1050",
            "expected": {
                "sel_type": "cma_port_t",
                "protocol": "tcp",
                "port": "1050",
            },
        },
        {
            "semanage_out": (
                "cluster_port_t                 tcp      5149, 40040, 50006-50008"
            ),
            "name": "tcp/40040",
            "expected": {
                "sel_type": "cluster_port_t",
                "protocol": "tcp",
                "port": "5149, 40040, 50006-50008",
            },
        },
        {
            "semanage_out": (
                "http_port_t                    tcp      9008, 8010, 9002-9003, 80,"
                " 81, 443, 488, 8008, 8009, 8443, 9000"
            ),
            "name": "tcp/9000",
            "expected": {
                "sel_type": "http_port_t",
                "protocol": "tcp",
                "port": (
                    "9008, 8010, 9002-9003, 80, 81, 443, 488, 8008, 8009, 8443," " 9000"
                ),
            },
        },
        {
            "semanage_out": (
                "vnc_port_t                     tcp      5985-5999, 5900-5983"
            ),
            "name": "tcp/5985-5999",
            "expected": {
                "sel_type": "vnc_port_t",
                "protocol": "tcp",
                "port": "5985-5999, 5900-5983",
            },
        },
        {
            "semanage_out": (
                "zebra_port_t                   tcp      2606, 2608-2609, 2600-2604"
            ),
            "name": "tcp/2608-2609",
            "expected": {
                "sel_type": "zebra_port_t",
                "protocol": "tcp",
                "port": "2606, 2608-2609, 2600-2604",
            },
        },
        {
            "semanage_out": (
                "radius_port_t                  udp      1645, 1812, 18120-18121"
            ),
            "name": "tcp/18120-18121",
            "expected": {
                "sel_type": "radius_port_t",
                "protocol": "udp",
                "port": "1645, 1812, 18120-18121",
            },
        },
    ]

    for case in cases:
        with patch.dict(
            selinux.__salt__,
            {"cmd.shell": MagicMock(return_value=case["semanage_out"])},
        ):
            ret = selinux.port_get_policy(case["name"])
            assert ret == case["expected"]


def test_port_get_policy_unparseable_raises_command_execution_error_64583():
    """
    Regression test for #64583.

    On Fedora 38+, `semanage port -l` output can change format so that the
    grep pipeline in ``port_get_policy`` returns a non-empty line that does
    not match the parsing regex. Previously ``re.match`` returned ``None``
    and the code raised ``AttributeError: 'NoneType' object has no
    attribute 'group'``. It should raise ``CommandExecutionError`` instead.
    """
    unparseable_output = "   \n"
    with patch.dict(
        selinux.__salt__,
        {"cmd.shell": MagicMock(return_value=unparseable_output)},
    ):
        with pytest.raises(CommandExecutionError):
            selinux.port_get_policy("tcp/22")


def test_fcontext_policy_parsing_new():
    """
    Test parsing the stdout response of restorecon used in fcontext_policy_applied, new style.
    """
    restorecon_ret = (
        "Would relabel /foo/bar from some_u:some_r:some_t:s0 to"
        " other_u:other_r:other_t:s0"
    )
    with patch.object(
        selinux, "fcontext_policy_is_applied", return_value=restorecon_ret
    ), patch.dict(
        selinux.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert selinux.fcontext_apply_policy("/foo/bar") == {
            "changes": {
                "/foo/bar": {
                    "old": {
                        "sel_role": "some_r",
                        "sel_type": "some_t",
                        "sel_user": "some_u",
                    },
                    "new": {
                        "sel_role": "other_r",
                        "sel_type": "other_t",
                        "sel_user": "other_u",
                    },
                },
            },
            "retcode": 0,
        }


def test_fcontext_policy_parsing_old():
    """
    Test parsing the stdout response of restorecon used in fcontext_policy_applied, old style.
    """
    restorecon_ret = (
        "restorecon reset /foo/bar context"
        " some_u:some_r:some_t:s0->other_u:other_r:other_t:s0"
    )
    with patch.object(
        selinux, "fcontext_policy_is_applied", return_value=restorecon_ret
    ), patch.dict(
        selinux.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert selinux.fcontext_apply_policy("/foo/bar") == {
            "changes": {
                "/foo/bar": {
                    "old": {
                        "sel_role": "some_r",
                        "sel_type": "some_t",
                        "sel_user": "some_u",
                    },
                    "new": {
                        "sel_role": "other_r",
                        "sel_type": "other_t",
                        "sel_user": "other_u",
                    },
                },
            },
            "retcode": 0,
        }


def test_fcontext_policy_parsing_fail():
    """
    Test failure response for invalid restorecon data.
    """
    restorecon_ret = "And now for something completely different."
    with patch.object(
        selinux, "fcontext_policy_is_applied", return_value=restorecon_ret
    ), patch.dict(
        selinux.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert selinux.fcontext_apply_policy("/foo/bar") == {
            "retcode": 1,
            "error": "Unrecognized response from restorecon command.",
        }


def test_selinux_config_enforcing():
    """
    Test values written to /etc/selinux/config are lowercase
    """
    mock_file = """
# This file controls the state of SELinux on the system.
# SELINUX= can take one of these three values:
#     enforcing - SELinux security policy is enforced.
#     permissive - SELinux prints warnings instead of enforcing.
#     disabled - No SELinux policy is loaded.
## SELINUX=disabled
SELINUX=permissive
# SELINUXTYPE= can take one of these three values:
#     targeted - Targeted processes are protected,
#     minimum - Modification of targeted policy. Only selected processes are protected.
#     mls - Multi Level Security protection.
SELINUXTYPE=targeted

"""
    with patch("salt.utils.files.fopen", mock_open(read_data=mock_file)) as m_open:
        selinux.setenforce("Enforcing")
        writes = m_open.write_calls()
        assert writes
        for line in writes:
            if line.startswith("SELINUX="):
                assert line == "SELINUX=enforcing"


def test_selinux_config_permissive():
    """
    Test values written to /etc/selinux/config are lowercase
    """
    mock_file = """
# This file controls the state of SELinux on the system.
# SELINUX= can take one of these three values:
#     enforcing - SELinux security policy is enforced.
#     permissive - SELinux prints warnings instead of enforcing.
#     disabled - No SELinux policy is loaded.
SELINUX=disabled
# SELINUXTYPE= can take one of these three values:
#     targeted - Targeted processes are protected,
#     minimum - Modification of targeted policy. Only selected processes are protected.
#     mls - Multi Level Security protection.
SELINUXTYPE=targeted

"""
    with patch("salt.utils.files.fopen", mock_open(read_data=mock_file)) as m_open:
        selinux.setenforce("Permissive")
        writes = m_open.write_calls()
        assert writes
        for line in writes:
            if line.startswith("SELINUX="):
                assert line == "SELINUX=permissive"


def test_selinux_config_disabled():
    """
    Test values written to /etc/selinux/config are lowercase
    """
    mock_file = """
# This file controls the state of SELinux on the system.
# SELINUX= can take one of these three values:
#     enforcing - SELinux security policy is enforced.
#     permissive - SELinux prints warnings instead of enforcing.
#     disabled - No SELinux policy is loaded.
## SELINUX=disabled
SELINUX=permissive
# SELINUXTYPE= can take one of these three values:
#     targeted - Targeted processes are protected,
#     minimum - Modification of targeted policy. Only selected processes are protected.
#     mls - Multi Level Security protection.
SELINUXTYPE=targeted

"""
    with patch("salt.utils.files.fopen", mock_open(read_data=mock_file)) as m_open:
        selinux.setenforce("Disabled")
        writes = m_open.write_calls()
        assert writes
        for line in writes:
            if line.startswith("SELINUX="):
                assert line == "SELINUX=disabled"


def _semanage_run_all(list_stdout, add_result=None):
    """
    Mock ``cmd.run_all`` so that listing returns ``list_stdout`` and any other
    semanage invocation returns ``add_result``
    """
    add_result = add_result or {"retcode": 0, "stdout": "", "stderr": ""}

    def run_all(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd[:3] == ["semanage", "fcontext", "--list"]:
            return {"retcode": 0, "stdout": list_stdout, "stderr": ""}
        return add_result

    return MagicMock(side_effect=run_all)


@pytest.mark.parametrize(
    "name,sel_type",
    (
        ("/srv/ssl/ldap/.*[.]key", "slapd_cert_t"),
        ("/srv/ssl/ldap(/.*[.](pem|crt))?", "cert_t"),
    ),
)
def test_selinux_add_policy_regex(name, sel_type):
    """
    Test adding policy with regex components modifies an existing entry with
    the exact same filespec
    """
    mock_cmd_run_all = _semanage_run_all(
        f"{name}    all files    system_u:object_r:var_t:s0\n"
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        selinux.fcontext_add_policy(name, sel_type=sel_type)

    expected_cmd = f"semanage fcontext --modify --type {sel_type} {re.escape(name)}"
    assert mock_cmd_run_all.call_args_list[-1] == call(expected_cmd)


@pytest.mark.parametrize(
    "name,sel_type",
    (
        ("/usr/share/munin/plugins/mysql_queries", "services_munin_plugin_exec_t"),
        ("/usr/share/munin/plugins/mysql_", "unconfined_munin_plugin_exec_t"),
    ),
)
def test_selinux_add_policy_shorter_path(name, sel_type):
    """
    Test adding policy with a shorter path than an existing entry uses
    ``--add``, not ``--modify``
    """
    mock_cmd_run_all = _semanage_run_all(
        "/usr/share/munin/plugins/mysql_queries_extra    all files"
        "    system_u:object_r:var_t:s0\n"
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        selinux.fcontext_add_policy(name, sel_type=sel_type)

    expected_cmd = f"semanage fcontext --add --type {sel_type} {re.escape(name)}"
    assert mock_cmd_run_all.call_args_list[-1] == call(expected_cmd)


def test_selinux_add_policy_hyphenated_path_ignores_grep_warning():
    """
    Regression test for #66854.

    A filespec containing a hyphen must not be treated as an existing entry
    because of a warning on stderr (grep 3.8+ warns about the escaped hyphen).
    """
    name = "/etc/usbguard/usbguard-daemon.conf"
    mock_cmd_run_all = _semanage_run_all("")

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        selinux.fcontext_add_policy(name, sel_type="usbguard_conf_t")

    assert mock_cmd_run_all.call_args_list[0] == call(
        ["semanage", "fcontext", "--list"], python_shell=False
    )
    expected_cmd = f"semanage fcontext --add --type usbguard_conf_t {re.escape(name)}"
    assert mock_cmd_run_all.call_args_list[-1] == call(expected_cmd)


def test_selinux_add_policy_modify_only_for_matching_filetype():
    """
    An entry for another filetype does not make ``--modify`` valid
    """
    name = "/srv/data"
    mock_cmd_run_all = _semanage_run_all(
        f"{name}    all files    system_u:object_r:var_t:s0\n"
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        selinux.fcontext_add_policy(name, filetype="d", sel_type="var_t")

    expected_cmd = f"semanage fcontext --add --ftype d --type var_t {re.escape(name)}"
    assert mock_cmd_run_all.call_args_list[-1] == call(expected_cmd)


def test_fcontext_get_policy_hyphenated_path():
    """
    Regression test for #66854
    """
    name = "/vol/apache/dummy/bla-bla(/.*)?"
    mock_cmd_run_all = _semanage_run_all(
        f"{name}    all files    system_u:object_r:httpd_sys_content_t:s0\n"
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        ret = selinux.fcontext_get_policy(name)

    assert ret["filespec"] == name
    assert ret["sel_type"] == "httpd_sys_content_t"


def test_fcontext_get_policy_no_match_returns_none():
    mock_cmd_run_all = _semanage_run_all(
        "/var/www(/.*)?    all files    system_u:object_r:httpd_sys_content_t:s0\n"
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        assert selinux.fcontext_get_policy("/var/www") is None
        assert selinux.fcontext_get_policy("/var/www(/.*)?", sel_type="other_t") is None


def test_fcontext_list_policy_raises_when_semanage_fails():
    mock_cmd_run_all = MagicMock(
        return_value={"retcode": 1, "stdout": "", "stderr": "semanage: not found"}
    )

    with patch.dict(selinux.__salt__, {"cmd.run_all": mock_cmd_run_all}):
        with pytest.raises(CommandExecutionError, match="semanage: not found"):
            selinux.fcontext_get_policy("/var/www")
