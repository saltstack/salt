"""
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from salt.cloud.clouds import dimensiondata
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import LooseVersion
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.mock import __version__ as mock_version
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf
from tests.unit.cloud.clouds import _preferred_ip

try:
    import libcloud.security

    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


VM_NAME = "winterfell"

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
except (ImportError, NameError):
    pass


class ExtendedTestCase(TestCase):
    """
    Extended TestCase class containing additional helper methods.
    """

    def assertRaisesWithMessage(self, exc_type, exc_msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except Exception as exc:  # pylint: disable=broad-except
            self.assertEqual(type(exc), exc_type)
            self.assertEqual(exc.message, exc_msg)


class DimensionDataTestCase(ExtendedTestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for salt.cloud.clouds.dimensiondata module.
    """

    def setup_loader_modules(self):
        return {
            dimensiondata: {
                "__active_provider_name__": "",
                "__opts__": {
                    "providers": {
                        "my-dimensiondata-cloud": {
                            "dimensiondata": {
                                "driver": "dimensiondata",
                                "region": "dd-au",
                                "user_id": "jon_snow",
                                "key": "IKnowNothing",
                            }
                        }
                    }
                },
            }
        }

    def test_avail_images_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call avail_images
        with --action or -a.
        """
        self.assertRaises(
            SaltCloudSystemExit, dimensiondata.avail_images, call="action"
        )

    def test_avail_locations_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
        with --action or -a.
        """
        self.assertRaises(
            SaltCloudSystemExit, dimensiondata.avail_locations, call="action"
        )

    def test_avail_sizes_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
        with --action or -a.
        """
        self.assertRaises(SaltCloudSystemExit, dimensiondata.avail_sizes, call="action")

    def test_list_nodes_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
        with --action or -a.
        """
        self.assertRaises(SaltCloudSystemExit, dimensiondata.list_nodes, call="action")

    def test_destroy_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when trying to call destroy
        with --function or -f.
        """
        self.assertRaises(
            SaltCloudSystemExit, dimensiondata.destroy, name=VM_NAME, call="function"
        )

    @skipIf(
        HAS_LIBCLOUD is False, "Install 'libcloud' to be able to run this unit test."
    )
    def test_avail_sizes(self):
        """
        Tests that avail_sizes returns an empty dictionary.
        """
        sizes = dimensiondata.avail_sizes(call="foo")
        self.assertEqual(len(sizes), 1)
        self.assertEqual(sizes["default"]["name"], "default")

    def test_import(self):
        """
        Test that the module picks up installed deps
        """
        with patch("salt.config.check_driver_dependencies", return_value=True) as p:
            get_deps = dimensiondata.get_dependencies()
            self.assertEqual(get_deps, True)
            if LooseVersion(mock_version) >= LooseVersion("2.0.0"):
                self.assertTrue(p.call_count >= 1)

    def test_provider_matches(self):
        """
        Test that the first configured instance of a dimensiondata driver is matched
        """
        p = dimensiondata.get_configured_provider()
        self.assertNotEqual(p, None)

    def test_query_node_data_filter_preferred_ip_addresses(self):
        """
        Test if query node data is filtering out unpreferred IP addresses.
        """
        zero_ip = "0.0.0.0"
        private_ips = [zero_ip, "1.1.1.1", "2.2.2.2"]
        vm = {"name": None}
        data = MagicMock()
        data.public_ips = []
        # pylint: disable=blacklisted-unmocked-patching
        dimensiondata.NodeState = MagicMock()
        # pylint: enable=blacklisted-unmocked-patching
        dimensiondata.NodeState.RUNNING = True

        with patch(
            "salt.cloud.clouds.dimensiondata.show_instance",
            MagicMock(
                return_value={
                    "state": True,
                    "name": "foo",
                    "public_ips": [],
                    "private_ips": private_ips,
                }
            ),
        ):
            with patch(
                "salt.cloud.clouds.dimensiondata.preferred_ip",
                _preferred_ip(private_ips, [zero_ip]),
            ):
                with patch(
                    "salt.cloud.clouds.dimensiondata.ssh_interface",
                    MagicMock(return_value="private_ips"),
                ):
                    self.assertEqual(
                        dimensiondata._query_node_data(vm, data).public_ips, [zero_ip]
                    )
