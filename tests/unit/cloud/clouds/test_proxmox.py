"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""


from salt.cloud.clouds import proxmox
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, patch
from tests.support.unit import TestCase


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
                    "providers": {"my_proxmox": {}},
                    "profiles": {"my_proxmox": {}},
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

    def test__import_api_version_6(self):
        """
        Test successful import of version 6 api
        """
        with patch("salt.cloud.clouds.proxmox.requests.get") as mock_request:
            url = "proxmox"
            port = "8006"
            verify_ssl = False

            mock_request.return_value.text = """
var pveapi = [
    {
        "testkey": "testvalue"
    }]
;
"""
            proxmox._import_api()

    def test__import_api_version_7(self):
        """
        Test successful import of version 6 api
        """
        with patch("salt.cloud.clouds.proxmox.requests.get") as mock_request:
            url = "proxmox"
            port = "8006"
            verify_ssl = False

            mock_request.return_value.text = """
const apiSchema = [
    {
        "testkey": "testvalue"
    }]
;
"""
            proxmox._import_api()
