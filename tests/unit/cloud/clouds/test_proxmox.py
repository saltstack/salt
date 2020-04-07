# -*- coding: utf-8 -*-
"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

# Import Salt Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.cloud.clouds import proxmox

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ProxmoxTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            proxmox: {
                "__utils__": {
                    "cloud.fire_event": MagicMock(),
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
