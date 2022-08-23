"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

import io
import textwrap

import requests

from salt import config
from salt.cloud.clouds import proxmox
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, patch
from tests.support.unit import TestCase

PROFILE = {
    "my_proxmox": {
        "provider": "my_proxmox",
        "image": "local:some_image.tgz",
    }
}
PROVIDER_CONFIG = {
    "my_proxmox": {
        "proxmox": {
            "driver": "proxmox",
            "url": "pve@domain.com",
            "user": "cloud@pve",
            "password": "verybadpass",
            "profiles": PROFILE,
        }
    }
}


class ProxmoxTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            proxmox: {
                "__utils__": {
                    "cloud.fire_event": MagicMock(),
                    "cloud.filter_event": MagicMock(),
                    "cloud.bootstrap": MagicMock(),
                },
                "__opts__": {
                    "sock_dir": True,
                    "transport": True,
                    "providers": PROVIDER_CONFIG,
                    "profiles": PROFILE,
                },
                "__active_provider_name__": "my_proxmox:proxmox",
            }
        }

    def setUp(self):
        self.vm_ = {
            "profile": "my_proxmox",
            "name": "vm4",
            "driver": "proxmox",
            "technology": "qemu",
            "host": "127.0.0.1",
            "clone": True,
            "ide0": "data",
            "sata0": "data",
            "scsi0": "data",
            "net0": "a=b,c=d",
        }

    def tearDown(self):
        del self.vm_

    def test__stringlist_to_dictionary(self):
        result = proxmox._stringlist_to_dictionary("")
        self.assertEqual(result, {})

        result = proxmox._stringlist_to_dictionary(
            "foo=bar, ignored_space=bar,internal space=bar"
        )
        self.assertEqual(
            result, {"foo": "bar", "ignored_space": "bar", "internal space": "bar"}
        )

        # Negative cases
        self.assertRaises(ValueError, proxmox._stringlist_to_dictionary, "foo=bar,foo")
        self.assertRaises(
            ValueError,
            proxmox._stringlist_to_dictionary,
            "foo=bar,totally=invalid=assignment",
        )

    def test__dictionary_to_stringlist(self):
        result = proxmox._dictionary_to_stringlist({})
        self.assertEqual(result, "")

        result = proxmox._dictionary_to_stringlist({"a": "a"})
        self.assertEqual(result, "a=a")

        result = proxmox._dictionary_to_stringlist({"a": "a", "b": "b"})
        self.assertEqual(result, "a=a,b=b")

    def test__reconfigure_clone(self):
        # The return_value is for the net reconfigure assertions, it is irrelevant for the rest
        with patch.object(
            proxmox, "query", return_value={"net0": "c=overwritten,g=h"}
        ) as query:
            # Test a vm that lacks the required attributes
            proxmox._reconfigure_clone({}, 0)
            query.assert_not_called()

            # Test a fully mocked vm
            proxmox._reconfigure_clone(self.vm_, 0)

            # net reconfigure
            query.assert_any_call("get", "nodes/127.0.0.1/qemu/0/config")
            query.assert_any_call(
                "post", "nodes/127.0.0.1/qemu/0/config", {"net0": "a=b,c=d,g=h"}
            )

            # hdd reconfigure
            query.assert_any_call(
                "post", "nodes/127.0.0.1/qemu/0/config", {"ide0": "data"}
            )
            query.assert_any_call(
                "post", "nodes/127.0.0.1/qemu/0/config", {"sata0": "data"}
            )
            query.assert_any_call(
                "post", "nodes/127.0.0.1/qemu/0/config", {"scsi0": "data"}
            )

    def test_clone(self):
        """
        Test that an integer value for clone_from
        """
        mock_query = MagicMock(return_value="")
        with patch(
            "salt.cloud.clouds.proxmox._get_properties", MagicMock(return_value=[])
        ), patch("salt.cloud.clouds.proxmox.query", mock_query):
            vm_ = {
                "technology": "qemu",
                "name": "new2",
                "host": "myhost",
                "clone": True,
                "clone_from": 123,
            }

            # CASE 1: Numeric ID
            result = proxmox.create_node(vm_, ANY)
            mock_query.assert_called_once_with(
                "post",
                "nodes/myhost/qemu/123/clone",
                {"newid": ANY},
            )
            assert result == {}

            # CASE 2: host:ID notation
            mock_query.reset_mock()
            vm_["clone_from"] = "otherhost:123"
            result = proxmox.create_node(vm_, ANY)
            mock_query.assert_called_once_with(
                "post",
                "nodes/otherhost/qemu/123/clone",
                {"newid": ANY},
            )
            assert result == {}

    def test_clone_pool(self):
        """
        Test that cloning a VM passes the pool parameter if present
        """
        mock_query = MagicMock(return_value="")
        with patch(
            "salt.cloud.clouds.proxmox._get_properties", MagicMock(return_value=[])
        ), patch("salt.cloud.clouds.proxmox.query", mock_query):
            vm_ = {
                "technology": "qemu",
                "name": "new2",
                "host": "myhost",
                "clone": True,
                "clone_from": 123,
                "pool": "mypool",
            }

            result = proxmox.create_node(vm_, ANY)
            mock_query.assert_called_once_with(
                "post",
                "nodes/myhost/qemu/123/clone",
                {"newid": ANY, "pool": "mypool"},
            )
            assert result == {}

    def test_find_agent_ips(self):
        """
        Test find_agent_ip will return an IP
        """

        with patch(
            "salt.cloud.clouds.proxmox.query",
            return_value={
                "result": [
                    {
                        "name": "eth0",
                        "ip-addresses": [
                            {"ip-address": "1.2.3.4", "ip-address-type": "ipv4"},
                            {"ip-address": "2001::1:2", "ip-address-type": "ipv6"},
                        ],
                    },
                    {
                        "name": "eth1",
                        "ip-addresses": [
                            {"ip-address": "2.3.4.5", "ip-address-type": "ipv4"},
                        ],
                    },
                    {
                        "name": "dummy",
                    },
                ]
            },
        ) as mock_query:
            vm_ = {
                "technology": "qemu",
                "host": "myhost",
                "driver": "proxmox",
                "ignore_cidr": "1.0.0.0/8",
            }

            # CASE 1: Test ipv4 and ignore_cidr
            result = proxmox._find_agent_ip(vm_, ANY)
            mock_query.assert_any_call(
                "get", "nodes/myhost/qemu/{}/agent/network-get-interfaces".format(ANY)
            )

            assert result == "2.3.4.5"

            # CASE 2: Test ipv6

            vm_["protocol"] = "ipv6"
            result = proxmox._find_agent_ip(vm_, ANY)
            mock_query.assert_any_call(
                "get", "nodes/myhost/qemu/{}/agent/network-get-interfaces".format(ANY)
            )

            assert result == "2001::1:2"

    def test__authenticate_with_custom_port(self):
        """
        Test the use of a custom port for Proxmox connection
        """
        get_cloud_config_mock = [
            "proxmox.connection.url",
            "9999",
            "fakeuser",
            "secretpassword",
            True,
        ]
        requests_post_mock = MagicMock()
        with patch(
            "salt.config.get_cloud_config_value",
            autospec=True,
            side_effect=get_cloud_config_mock,
        ), patch("requests.post", requests_post_mock):
            proxmox._authenticate()
            requests_post_mock.assert_called_with(
                "https://proxmox.connection.url:9999/api2/json/access/ticket",
                verify=True,
                data={"username": ("fakeuser",), "password": "secretpassword"},
            )

    def test__import_api_v6(self):
        """
        Test _import_api handling of a Proxmox VE 6 response.
        """
        response = textwrap.dedent(
            """\
            var pveapi = [
               {
                  "info" : {
                  }
               }
            ]
            ;
            """
        )
        self._test__import_api(response)

    def test__import_api_v7(self):
        """
        Test _import_api handling of a Proxmox VE 7 response.
        """
        response = textwrap.dedent(
            """\
            const apiSchema = [
               {
                  "info" : {
                  }
               }
            ]
            ;
            """
        )
        self._test__import_api(response)

    def _test__import_api(self, response):
        """
        Test _import_api recognition of varying Proxmox VE responses.
        """
        requests_get_mock = MagicMock()
        requests_get_mock.return_value.status_code = 200
        requests_get_mock.return_value.text = response
        with patch("requests.get", requests_get_mock):
            proxmox._import_api()
        self.assertEqual(proxmox.api, [{"info": {}}])
        return

    def test__authenticate_success(self):
        response = requests.Response()
        response.status_code = 200
        response.reason = "OK"
        response.raw = io.BytesIO(
            b"""{"data":{"CSRFPreventionToken":"01234567:dG9rZW4=","ticket":"PVE:cloud@pve:01234567::dGlja2V0"}}"""
        )
        with patch("requests.post", return_value=response):
            proxmox._authenticate()
        assert proxmox.csrf and proxmox.ticket
        return

    def test__authenticate_failure(self):
        """
        Confirm that authentication failure raises an exception.
        """
        response = requests.Response()
        response.status_code = 401
        response.reason = "authentication failure"
        response.raw = io.BytesIO(b"""{"data":null}""")
        with patch("requests.post", return_value=response):
            self.assertRaises(requests.exceptions.HTTPError, proxmox._authenticate)
        return

    def test_creation_failure_logging(self):
        """
        Test detailed logging on HTTP errors during VM creation.
        """
        vm_ = {
            "profile": "my_proxmox",
            "name": "vm4",
            "technology": "lxc",
            "host": "127.0.0.1",
            "image": "local:some_image.tgz",
            "onboot": True,
        }
        self.assertEqual(
            config.is_profile_configured(
                proxmox.__opts__, "my_proxmox:proxmox", "my_proxmox", vm_=vm_
            ),
            True,
        )

        response = requests.Response()
        response.status_code = 400
        response.reason = "Parameter verification failed."
        response.raw = io.BytesIO(
            b"""{"data":null,"errors":{"onboot":"type check ('boolean') failed - got 'True'"}}"""
        )

        def mock_query_response(conn_type, option, post_data=None):
            if conn_type == "get" and option == "cluster/nextid":
                return 104
            if conn_type == "post" and option == "nodes/127.0.0.1/lxc":
                response.raise_for_status()
                return response
            return None

        with patch.object(
            proxmox, "query", side_effect=mock_query_response
        ), patch.object(
            proxmox, "_get_properties", return_value=set()
        ), TstSuiteLoggingHandler() as log_handler:
            self.assertEqual(proxmox.create(vm_), False)

            # Search for these messages in a multi-line log entry.
            missing = {
                "{} Client Error: {} for url:".format(
                    response.status_code, response.reason
                ),
                response.text,
            }
            for required in list(missing):
                for message in log_handler.messages:
                    if required in message:
                        missing.remove(required)
                        break
            if missing:
                raise AssertionError(
                    "Did not find error messages: {}".format(sorted(list(missing)))
                )
        return
