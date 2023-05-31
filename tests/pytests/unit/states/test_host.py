"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import logging

import pytest

import salt.states.host as host
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)


hostname = "salt"
localhost_ip = "127.0.0.1"
ip_list = ["203.0.113.113", "203.0.113.14"]
default_hosts = {
    ip_list[0]: {"aliases": [hostname]},
    ip_list[1]: {"aliases": [hostname]},
}


@pytest.fixture
def configure_loader_modules():
    return {
        host: {"__opts__": {"test": False}},
    }


def test_present():
    """
    Test to ensures that the named host is present with the given ip
    """
    add_host = MagicMock(return_value=True)
    rm_host = MagicMock(return_value=True)
    hostname = "salt"
    ip_str = "127.0.0.1"
    ip_list = ["10.1.2.3", "10.4.5.6"]

    # Case 1: No match for hostname. Single IP address passed to the state.
    list_hosts = MagicMock(return_value={"127.0.0.1": {"aliases": ["localhost"]}})
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_str)
        assert ret["result"] is True
        assert ret["comment"] == "Added host {} ({})".format(hostname, ip_str), ret[
            "comment"
        ]
        assert ret["changes"] == {"added": {ip_str: [hostname]}}, ret["changes"]
        expected = [call(ip_str, hostname)]
        assert add_host.mock_calls == expected, add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 2: No match for hostname. Multiple IP addresses passed to the
    # state.
    list_hosts = MagicMock(return_value={"127.0.0.1": {"aliases": ["localhost"]}})
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[0]) in ret["comment"]
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert ret["changes"] == {
            "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]}
        }, ret["changes"]
        expected = sorted(call(x, hostname) for x in ip_list)
        assert sorted(add_host.mock_calls) == expected, add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 3: Match for hostname, but no matching IP. Single IP address
    # passed to the state.
    list_hosts = MagicMock(
        return_value={
            "127.0.0.1": {"aliases": ["localhost"]},
            ip_list[0]: {"aliases": [hostname]},
        }
    )
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_str)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_str) in ret["comment"]
        assert (
            "Host {} present for IP address {}".format(hostname, ip_list[0])
            in ret["warnings"][0]
        )
        assert ret["changes"] == {"added": {ip_str: [hostname]}}, ret["changes"]
        expected = [call(ip_str, hostname)]
        assert add_host.mock_calls == expected, add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 3a: Repeat the above with clean=True
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_str, clean=True)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_str) in ret["comment"]
        assert "Removed host {} ({})".format(hostname, ip_list[0]) in ret["comment"]
        assert ret["changes"] == {
            "added": {ip_str: [hostname]},
            "removed": {ip_list[0]: [hostname]},
        }, ret["changes"]
        expected = [call(ip_str, hostname)]
        assert add_host.mock_calls == expected, add_host.mock_calls
        expected = [call(ip_list[0], hostname)]
        assert rm_host.mock_calls == expected, rm_host.mock_calls

    # Case 4: Match for hostname, but no matching IP. Multiple IP addresses
    # passed to the state.
    cur_ip = "1.2.3.4"
    list_hosts = MagicMock(
        return_value={
            "127.0.0.1": {"aliases": ["localhost"]},
            cur_ip: {"aliases": [hostname]},
        }
    )
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[0]) in ret["comment"]
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert ret["changes"] == {
            "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]},
        }, ret["changes"]
        expected = sorted(call(x, hostname) for x in ip_list)
        assert sorted(add_host.mock_calls) == expected, add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 4a: Repeat the above with clean=True
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list, clean=True)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[0]) in ret["comment"]
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert "Removed host {} ({})".format(hostname, cur_ip) in ret["comment"]
        assert ret["changes"] == {
            "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]},
            "removed": {cur_ip: [hostname]},
        }, ret["changes"]
        expected = sorted(call(x, hostname) for x in ip_list)
        assert sorted(add_host.mock_calls) == expected, add_host.mock_calls
        expected = [call(cur_ip, hostname)]
        assert rm_host.mock_calls == expected, rm_host.mock_calls

    # Case 5: Multiple IP addresses passed to the state. One of them
    # matches, the other does not. There is also a non-matching IP that
    # must be removed.
    cur_ip = "1.2.3.4"
    list_hosts = MagicMock(
        return_value={
            "127.0.0.1": {"aliases": ["localhost"]},
            cur_ip: {"aliases": [hostname]},
            ip_list[0]: {"aliases": [hostname]},
        }
    )
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert ret["changes"] == {"added": {ip_list[1]: [hostname]}}, ret["changes"]
        expected = [call(ip_list[1], hostname)]
        assert add_host.mock_calls == expected, add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 5a: Repeat the above with clean=True
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list, clean=True)
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert "Removed host {} ({})".format(hostname, cur_ip) in ret["comment"]
        assert ret["changes"] == {
            "added": {ip_list[1]: [hostname]},
            "removed": {cur_ip: [hostname]},
        }, ret["changes"]
        expected = [call(ip_list[1], hostname)]
        assert add_host.mock_calls == expected, add_host.mock_calls
        expected = [call(cur_ip, hostname)]
        assert rm_host.mock_calls == expected, rm_host.mock_calls

    # Case 6: Single IP address passed to the state, which matches the
    # current configuration for that hostname. No changes should be made.
    list_hosts = MagicMock(return_value={ip_str: {"aliases": [hostname]}})
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_str)
        assert ret["result"] is True
        assert (
            ret["comment"]
            == "Host {} ({}) already present".format(hostname, ip_str)
            in ret["comment"]
        )
        assert ret["changes"] == {}, ret["changes"]
        assert add_host.mock_calls == [], add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 7: Multiple IP addresses passed to the state, which both match
    # the current configuration for that hostname. No changes should be
    # made.
    list_hosts = MagicMock(
        return_value={
            ip_list[0]: {"aliases": [hostname]},
            ip_list[1]: {"aliases": [hostname]},
        }
    )
    add_host.reset_mock()
    rm_host.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host,
            "hosts.rm_host": rm_host,
        },
    ):
        ret = host.present(hostname, ip_list)
        assert ret["result"] is True
        assert (
            "Host {} ({}) already present".format(hostname, ip_list[0])
            in ret["comment"]
        )
        assert (
            "Host {} ({}) already present".format(hostname, ip_list[1])
            in ret["comment"]
        )
        assert ret["changes"] == {}, ret["changes"]
        assert add_host.mock_calls == [], add_host.mock_calls
        assert rm_host.mock_calls == [], rm_host.mock_calls

    # Case 8: Passing a comment to host.present with multiple IPs
    list_hosts = MagicMock(return_value={"127.0.0.1": {"aliases": ["localhost"]}})
    add_host_mock = MagicMock(return_value=True)
    rm_host_mock = MagicMock(return_value=True)
    set_comment_mock = MagicMock(return_value=True)
    add_host_mock.reset_mock()
    rm_host_mock.reset_mock()
    set_comment_mock.reset_mock()
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host_mock,
            "hosts.rm_host": rm_host_mock,
            "hosts.set_comment": set_comment_mock,
        },
    ):
        ret = host.present(hostname, ip_list, comment="A comment")
        assert ret["result"] is True
        assert "Added host {} ({})".format(hostname, ip_list[0]) in ret["comment"]
        assert "Added host {} ({})".format(hostname, ip_list[1]) in ret["comment"]
        assert (
            "Set comment for host {} (A comment)".format(ip_list[0]) in ret["comment"]
        )
        assert (
            "Set comment for host {} (A comment)".format(ip_list[1]) in ret["comment"]
        )
        assert ret["changes"] == {
            "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]},
            "comment_added": {ip_list[0]: ["A comment"], ip_list[1]: ["A comment"]},
        }, ret["changes"]
        expected = sorted(call(x, hostname) for x in ip_list)
        assert sorted(add_host_mock.mock_calls) == expected, add_host_mock.mock_calls

        expected = sorted(call(x, "A comment") for x in ip_list)
        assert (
            sorted(set_comment_mock.mock_calls) == expected
        ), set_comment_mock.mock_calls

        assert rm_host_mock.mock_calls == [], rm_host_mock.mock_calls


def test_host_present_should_return_True_if_test_and_no_changes():
    add_host_mock = MagicMock(return_value=True)
    rm_host_mock = MagicMock(return_value=True)
    expected = {
        "comment": "Host {} ({}) already present".format(
            hostname,
            ip_list[0],
        ),
        "changes": {},
        "name": hostname,
        "result": True,
    }
    list_hosts = MagicMock(
        return_value={ip_list[0]: {"aliases": [hostname]}},
    )
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host_mock,
            "hosts.rm_host": rm_host_mock,
        },
    ):
        with patch.dict(host.__opts__, {"test": True}):
            ret = host.present(hostname, ip_list[:1])

            assert ret == expected


def test_host_present_should_return_None_if_test_and_adding():
    add_host_mock = MagicMock(return_value=True)
    rm_host_mock = MagicMock(return_value=True)
    expected = {
        "comment": "\n".join(
            ["Host {} ({}) already present", "Host {} ({}) would be added"]
        ).format(
            hostname,
            ip_list[0],
            hostname,
            ip_list[1],
        ),
        "changes": {"added": {ip_list[1]: [hostname]}},
        "name": hostname,
        "result": None,
    }
    list_hosts = MagicMock(
        return_value={ip_list[0]: {"aliases": [hostname]}},
    )
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts,
            "hosts.add_host": add_host_mock,
            "hosts.rm_host": rm_host_mock,
        },
    ):
        with patch.dict(host.__opts__, {"test": True}):
            ret = host.present(hostname, ip_list)
            assert ret == expected


def test_host_present_should_return_None_if_test_and_removing():
    add_host_mock = MagicMock(return_value=True)
    rm_host_mock = MagicMock(return_value=True)
    list_hosts_mock = MagicMock(return_value=default_hosts)
    expected = {
        "comment": "\n".join(
            ["Host {} ({}) already present", "Host {} ({}) would be removed"]
        ).format(
            hostname,
            ip_list[0],
            hostname,
            ip_list[1],
        ),
        "changes": {"removed": {ip_list[1]: [hostname]}},
        "name": hostname,
        "result": None,
    }
    with patch.dict(
        host.__salt__,
        {
            "hosts.list_hosts": list_hosts_mock,
            "hosts.add_host": add_host_mock,
            "hosts.rm_host": rm_host_mock,
        },
    ):
        with patch.dict(host.__opts__, {"test": True}):
            ret = host.present(hostname, ip_list[:1], clean=True)
            assert ret == expected


def test_absent():
    """
    Test to ensure that the named host is absent
    """
    ret = {
        "changes": {},
        "comment": "Host salt (127.0.0.1) already absent",
        "name": "salt",
        "result": True,
    }

    mock = MagicMock(return_value=False)
    with patch.dict(host.__salt__, {"hosts.has_pair": mock}):
        assert host.absent("salt", "127.0.0.1") == ret


def test_only_already():
    """
    Test only() when the state hasn't changed
    """
    expected = {
        "name": "127.0.1.1",
        "changes": {},
        "result": True,
        "comment": 'IP address 127.0.1.1 already set to "foo.bar"',
    }
    mock1 = MagicMock(return_value=["foo.bar"])
    with patch.dict(host.__salt__, {"hosts.get_alias": mock1}):
        mock2 = MagicMock(return_value=True)
        with patch.dict(host.__salt__, {"hosts.set_host": mock2}):
            with patch.dict(host.__opts__, {"test": False}):
                assert expected == host.only("127.0.1.1", "foo.bar")


def test_only_dryrun():
    """
    Test only() when state would change, but it's a dry run
    """
    expected = {
        "name": "127.0.1.1",
        "changes": {},
        "result": None,
        "comment": 'Would change 127.0.1.1 from "foo.bar" to "foo.bar foo"',
    }
    mock1 = MagicMock(return_value=["foo.bar"])
    with patch.dict(host.__salt__, {"hosts.get_alias": mock1}):
        mock2 = MagicMock(return_value=True)
        with patch.dict(host.__salt__, {"hosts.set_host": mock2}):
            with patch.dict(host.__opts__, {"test": True}):
                assert expected == host.only("127.0.1.1", ["foo.bar", "foo"])


def test_only_fail():
    """
    Test only() when state change fails
    """
    expected = {
        "name": "127.0.1.1",
        "changes": {},
        "result": False,
        "comment": "hosts.set_host failed to change 127.0.1.1"
        + ' from "foo.bar" to "foo.bar foo"',
    }
    mock = MagicMock(return_value=["foo.bar"])
    with patch.dict(host.__salt__, {"hosts.get_alias": mock}):
        mock = MagicMock(return_value=False)
        with patch.dict(host.__salt__, {"hosts.set_host": mock}):
            with patch.dict(host.__opts__, {"test": False}):
                assert expected == host.only("127.0.1.1", ["foo.bar", "foo"])


def test_only_success():
    """
    Test only() when state successfully changes
    """
    expected = {
        "name": "127.0.1.1",
        "changes": {"127.0.1.1": {"old": "foo.bar", "new": "foo.bar foo"}},
        "result": True,
        "comment": "successfully changed 127.0.1.1"
        + ' from "foo.bar" to "foo.bar foo"',
    }
    mock = MagicMock(return_value=["foo.bar"])
    with patch.dict(host.__salt__, {"hosts.get_alias": mock}):
        mock = MagicMock(return_value=True)
        with patch.dict(host.__salt__, {"hosts.set_host": mock}):
            with patch.dict(host.__opts__, {"test": False}):
                assert expected == host.only("127.0.1.1", ["foo.bar", "foo"])
