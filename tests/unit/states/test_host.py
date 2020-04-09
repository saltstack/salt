# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.host as host

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class HostTestCase(TestCase, LoaderModuleMockMixin):
    """
    Validate the host state
    """

    hostname = "salt"
    localhost_ip = "127.0.0.1"
    ip_list = ["203.0.113.113", "203.0.113.14"]
    default_hosts = {
        ip_list[0]: [hostname],
        ip_list[1]: [hostname],
    }

    def setUp(self):
        self.add_host_mock = MagicMock(return_value=True)
        self.rm_host_mock = MagicMock(return_value=True)
        self.list_hosts_mock = MagicMock(return_value=self.default_hosts)

    def setup_loader_modules(self):
        return {
            host: {"__opts__": {"test": False}},
        }

    def test_present(self):
        """
        Test to ensures that the named host is present with the given ip
        """
        add_host = MagicMock(return_value=True)
        rm_host = MagicMock(return_value=True)
        hostname = "salt"
        ip_str = "127.0.0.1"
        ip_list = ["10.1.2.3", "10.4.5.6"]

        # Case 1: No match for hostname. Single IP address passed to the state.
        list_hosts = MagicMock(return_value={"127.0.0.1": ["localhost"]})
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
            assert ret["comment"] == "Added host {0} ({1})".format(
                hostname, ip_str
            ), ret["comment"]
            assert ret["changes"] == {"added": {ip_str: [hostname]}}, ret["changes"]
            expected = [call(ip_str, hostname)]
            assert add_host.mock_calls == expected, add_host.mock_calls
            assert rm_host.mock_calls == [], rm_host.mock_calls

        # Case 2: No match for hostname. Multiple IP addresses passed to the
        # state.
        list_hosts = MagicMock(return_value={"127.0.0.1": ["localhost"]})
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
            assert "Added host {0} ({1})".format(hostname, ip_list[0]) in ret["comment"]
            assert "Added host {0} ({1})".format(hostname, ip_list[1]) in ret["comment"]
            assert ret["changes"] == {
                "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]}
            }, ret["changes"]
            expected = sorted([call(x, hostname) for x in ip_list])
            assert sorted(add_host.mock_calls) == expected, add_host.mock_calls
            assert rm_host.mock_calls == [], rm_host.mock_calls

        # Case 3: Match for hostname, but no matching IP. Single IP address
        # passed to the state.
        list_hosts = MagicMock(
            return_value={"127.0.0.1": ["localhost"], ip_list[0]: [hostname]}
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
            assert "Added host {0} ({1})".format(hostname, ip_str) in ret["comment"]
            assert (
                "Host {0} present for IP address {1}".format(hostname, ip_list[0])
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
            assert "Added host {0} ({1})".format(hostname, ip_str) in ret["comment"]
            assert (
                "Removed host {0} ({1})".format(hostname, ip_list[0]) in ret["comment"]
            )
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
            return_value={"127.0.0.1": ["localhost"], cur_ip: [hostname]}
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
            assert "Added host {0} ({1})".format(hostname, ip_list[0]) in ret["comment"]
            assert "Added host {0} ({1})".format(hostname, ip_list[1]) in ret["comment"]
            assert ret["changes"] == {
                "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]},
            }, ret["changes"]
            expected = sorted([call(x, hostname) for x in ip_list])
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
            assert "Added host {0} ({1})".format(hostname, ip_list[0]) in ret["comment"]
            assert "Added host {0} ({1})".format(hostname, ip_list[1]) in ret["comment"]
            assert "Removed host {0} ({1})".format(hostname, cur_ip) in ret["comment"]
            assert ret["changes"] == {
                "added": {ip_list[0]: [hostname], ip_list[1]: [hostname]},
                "removed": {cur_ip: [hostname]},
            }, ret["changes"]
            expected = sorted([call(x, hostname) for x in ip_list])
            assert sorted(add_host.mock_calls) == expected, add_host.mock_calls
            expected = [call(cur_ip, hostname)]
            assert rm_host.mock_calls == expected, rm_host.mock_calls

        # Case 5: Multiple IP addresses passed to the state. One of them
        # matches, the other does not. There is also a non-matching IP that
        # must be removed.
        cur_ip = "1.2.3.4"
        list_hosts = MagicMock(
            return_value={
                "127.0.0.1": ["localhost"],
                cur_ip: [hostname],
                ip_list[0]: [hostname],
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
            assert "Added host {0} ({1})".format(hostname, ip_list[1]) in ret["comment"]
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
            assert "Added host {0} ({1})".format(hostname, ip_list[1]) in ret["comment"]
            assert "Removed host {0} ({1})".format(hostname, cur_ip) in ret["comment"]
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
        list_hosts = MagicMock(return_value={ip_str: [hostname]})
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
                == "Host {0} ({1}) already present".format(hostname, ip_str)
                in ret["comment"]
            )
            assert ret["changes"] == {}, ret["changes"]
            assert add_host.mock_calls == [], add_host.mock_calls
            assert rm_host.mock_calls == [], rm_host.mock_calls

        # Case 7: Multiple IP addresses passed to the state, which both match
        # the current configuration for that hostname. No changes should be
        # made.
        list_hosts = MagicMock(
            return_value={ip_list[0]: [hostname], ip_list[1]: [hostname]}
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
                "Host {0} ({1}) already present".format(hostname, ip_list[0])
                in ret["comment"]
            )
            assert (
                "Host {0} ({1}) already present".format(hostname, ip_list[1])
                in ret["comment"]
            )
            assert ret["changes"] == {}, ret["changes"]
            assert add_host.mock_calls == [], add_host.mock_calls
            assert rm_host.mock_calls == [], rm_host.mock_calls

    def test_host_present_should_return_True_if_test_and_no_changes(self):
        expected = {
            "comment": "Host {} ({}) already present".format(
                self.hostname, self.ip_list[0],
            ),
            "changes": {},
            "name": self.hostname,
            "result": True,
        }
        list_hosts = MagicMock(return_value={self.ip_list[0]: [self.hostname]},)
        with patch.dict(
            host.__salt__,
            {
                "hosts.list_hosts": list_hosts,
                "hosts.add_host": self.add_host_mock,
                "hosts.rm_host": self.rm_host_mock,
            },
        ):
            with patch.dict(host.__opts__, {"test": True}):
                ret = host.present(self.hostname, self.ip_list[:1])

                self.assertDictEqual(ret, expected)

    def test_host_present_should_return_None_if_test_and_adding(self):
        expected = {
            "comment": "\n".join(
                ["Host {} ({}) already present", "Host {} ({}) would be added"]
            ).format(self.hostname, self.ip_list[0], self.hostname, self.ip_list[1],),
            "changes": {"added": {self.ip_list[1]: [self.hostname]}},
            "name": self.hostname,
            "result": None,
        }
        list_hosts = MagicMock(return_value={self.ip_list[0]: [self.hostname]},)
        with patch.dict(
            host.__salt__,
            {
                "hosts.list_hosts": list_hosts,
                "hosts.add_host": self.add_host_mock,
                "hosts.rm_host": self.rm_host_mock,
            },
        ):
            with patch.dict(host.__opts__, {"test": True}):
                ret = host.present(self.hostname, self.ip_list)
                self.assertDictEqual(ret, expected)

    def test_host_present_should_return_None_if_test_and_removing(self):
        expected = {
            "comment": "\n".join(
                ["Host {} ({}) already present", "Host {} ({}) would be removed"]
            ).format(self.hostname, self.ip_list[0], self.hostname, self.ip_list[1],),
            "changes": {"removed": {self.ip_list[1]: [self.hostname]}},
            "name": self.hostname,
            "result": None,
        }
        with patch.dict(
            host.__salt__,
            {
                "hosts.list_hosts": self.list_hosts_mock,
                "hosts.add_host": self.add_host_mock,
                "hosts.rm_host": self.rm_host_mock,
            },
        ):
            with patch.dict(host.__opts__, {"test": True}):
                ret = host.present(self.hostname, self.ip_list[:1], clean=True)
                self.assertDictEqual(ret, expected)

    def test_absent(self):
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
            self.assertDictEqual(host.absent("salt", "127.0.0.1"), ret)

    def test_only_already(self):
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
                    self.assertDictEqual(expected, host.only("127.0.1.1", "foo.bar"))

    def test_only_dryrun(self):
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
                    self.assertDictEqual(
                        expected, host.only("127.0.1.1", ["foo.bar", "foo"])
                    )

    def test_only_fail(self):
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
                    self.assertDictEqual(
                        expected, host.only("127.0.1.1", ["foo.bar", "foo"])
                    )

    def test_only_success(self):
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
                    self.assertDictEqual(
                        expected, host.only("127.0.1.1", ["foo.bar", "foo"])
                    )
