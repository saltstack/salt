# -*- coding: utf-8 -*-
"""
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.gce_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import collections

# Import Salt Libs
from salt.cloud.clouds import gce
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import LooseVersion

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.mock import __version__ as mock_version
from tests.support.mock import patch
from tests.support.unit import TestCase

try:
    import libcloud.security

    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


VM_NAME = "kings_landing"
DUMMY_TOKEN = {
    "refresh_token": None,
    "client_id": "dany123",
    "client_secret": "lalalalalalala",
    "grant_type": "refresh_token",
}

# Use certifi if installed
try:
    if HAS_LIBCLOUD:
        # This work-around for Issue #32743 is no longer needed for libcloud >=
        # 1.4.0. However, older versions of libcloud must still be supported
        # with this work-around. This work-around can be removed when the
        # required minimum version of libcloud is 2.0.0 (See PR #40837 - which
        # is implemented in Salt 2018.3.0).
        if LooseVersion(libcloud.__version__) < LooseVersion("1.4.0"):
            import certifi

            libcloud.security.CA_CERTS_PATH.append(certifi.where())
except ImportError:
    pass


class DummyGCEConn(object):
    def __init__(self):
        self.create_node = MagicMock()

    def __getattr__(self, attr):
        if attr != "create_node":
            # Return back the first thing passed in (i.e. don't call out to get
            # the override value).
            return lambda *args, **kwargs: args[0]


class GCETestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for salt.cloud.clouds.gce module.
    """

    def setup_loader_modules(self):
        return {
            gce: {
                "__active_provider_name__": "",
                "__utils__": {
                    "cloud.fire_event": MagicMock(),
                    "cloud.filter_event": MagicMock(),
                },
                "__opts__": {
                    "sock_dir": True,
                    "transport": True,
                    "providers": {
                        "my-google-cloud": {
                            "gce": {
                                "project": "daenerys-cloud",
                                "service_account_email_address": "dany@targaryen.westeros.cloud",
                                "service_account_private_key": "/home/dany/PRIVKEY.pem",
                                "driver": "gce",
                                "ssh_interface": "public_ips",
                            }
                        }
                    },
                },
            }
        }

    def setUp(self):
        self.location = collections.namedtuple("Location", "name")("chicago")
        self.vm_ = {
            "name": "new",
            "driver": "gce",
            "profile": None,
            "size": 1234,
            "image": "myimage",
            "location": self.location,
            "ex_network": "mynetwork",
            "ex_subnetwork": "mysubnetwork",
            "ex_tags": "mytags",
            "ex_metadata": "metadata",
        }
        self.conn = DummyGCEConn()

    def tearDown(self):
        del self.vm_
        del self.conn

    def test_destroy_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        """
        self.assertRaises(
            SaltCloudSystemExit, gce.destroy, vm_name=VM_NAME, call="function"
        )

    def test_fail_virtual_missing_deps(self):
        # Missing deps
        with patch("salt.config.check_driver_dependencies", return_value=False):
            v = gce.__virtual__()
            self.assertEqual(v, False)

    def test_fail_virtual_deps_missing_config(self):
        with patch("salt.config.check_driver_dependencies", return_value=True):
            with patch("salt.config.is_provider_configured", return_value=False):
                v = gce.__virtual__()
                self.assertEqual(v, False)

    def test_import(self):
        """
        Test that the module picks up installed deps
        """
        with patch("salt.config.check_driver_dependencies", return_value=True) as p:
            get_deps = gce.get_dependencies()
            self.assertEqual(get_deps, True)
            if LooseVersion(mock_version) >= LooseVersion("2.0.0"):
                self.assert_called_once(p)

    def test_provider_matches(self):
        """
        Test that the first configured instance of a gce driver is matched
        """
        p = gce.get_configured_provider()
        self.assertNotEqual(p, None)

    def test_request_instance_with_accelerator(self):
        """
        Test requesting an instance with GCE accelerators
        """

        self.vm_.update({"ex_accelerator_type": "foo", "ex_accelerator_count": 42})
        call_kwargs = {
            "ex_disk_type": "pd-standard",
            "ex_metadata": {"items": [{"value": None, "key": "salt-cloud-profile"}]},
            "ex_accelerator_count": 42,
            "name": "new",
            "ex_service_accounts": None,
            "external_ip": "ephemeral",
            "ex_accelerator_type": "foo",
            "ex_tags": None,
            "ex_disk_auto_delete": True,
            "ex_network": "default",
            "ex_disks_gce_struct": None,
            "ex_preemptible": False,
            "ex_can_ip_forward": False,
            "ex_on_host_maintenance": "TERMINATE",
            "location": self.location,
            "ex_subnetwork": None,
            "image": "myimage",
            "size": 1234,
        }

        with patch(
            "salt.cloud.clouds.gce.get_conn", MagicMock(return_value=self.conn)
        ), patch("salt.cloud.clouds.gce.show_instance", MagicMock()), patch(
            "salt.cloud.clouds.gce.LIBCLOUD_VERSION_INFO", (2, 3, 0)
        ):
            gce.request_instance(self.vm_)
            self.conn.create_node.assert_called_once_with(**call_kwargs)
