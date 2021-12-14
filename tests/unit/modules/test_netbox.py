"""
    :codeauthor: :email:`Zach Moody <zmoody@do.co>`
"""


import salt.modules.netbox as netbox
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase, skipIf

try:
    import pynetbox  # pylint: disable=unused-import

    HAS_PYNETBOX = True
except ImportError:
    HAS_PYNETBOX = False


NETBOX_RESPONSE_STUB = {
    "device_name": "test1-router1",
    "url": "http://test/",
    "device_role": {"name": "router", "url": "http://test/"},
}


def mocked_clean_kwargs_filter(**kwargs):
    """
    Mocked args.clean_kwargs for filter tests
    """
    return {"site": "test"}


def mocked_clean_kwargs_get(**kwargs):
    """
    Mocked args.clean_kwargs for get tests
    """
    return {"name": "test"}


@skipIf(HAS_PYNETBOX is False, "pynetbox lib not installed")
@patch("salt.modules.netbox._config", MagicMock())
class NetBoxTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            netbox: {},
        }

    def test_get_by_id(self):
        with patch("pynetbox.api", MagicMock()) as mock:
            with patch.dict(
                netbox.__utils__, {"args.clean_kwargs": mocked_clean_kwargs_get}
            ):
                netbox.get_("dcim", "devices", id=1)
                self.assertEqual(mock.mock_calls[1], call().dcim.devices.get(1))

    def test_get_by_name(self):
        with patch("pynetbox.api", MagicMock()) as mock:
            with patch.dict(
                netbox.__utils__, {"args.clean_kwargs": mocked_clean_kwargs_get}
            ):
                netbox.get_("dcim", "devices", name="test")
                self.assertEqual(
                    mock.mock_calls[1], call().dcim.devices.get(name="test")
                )

    def test_filter_by_site(self):
        with patch("pynetbox.api", MagicMock()) as mock:
            with patch.dict(
                netbox.__utils__, {"args.clean_kwargs": mocked_clean_kwargs_filter}
            ):
                netbox.filter_("dcim", "devices", site="test")
                self.assertEqual(
                    mock.mock_calls[1], call().dcim.devices.filter(site="test")
                )

    def test_filter_url(self):
        strip_url = netbox._strip_url_field(NETBOX_RESPONSE_STUB)
        self.assertTrue(
            "url" not in strip_url and "url" not in strip_url["device_role"]
        )

    def test_get_secret(self):
        with patch("pynetbox.api", MagicMock()) as mock:
            with patch.dict(
                netbox.__utils__, {"args.clean_kwargs": mocked_clean_kwargs_get}
            ):
                netbox.get_("secrets", "secrets", name="test")
                self.assertTrue("token" and "private_key_file" in mock.call_args[1])

    def test_token_present(self):
        with patch("pynetbox.api", MagicMock()) as mock:
            with patch.dict(
                netbox.__utils__, {"args.clean_kwargs": mocked_clean_kwargs_get}
            ):
                netbox.get_("dcim", "devices", name="test")
                self.assertTrue("token" in mock.call_args[1])
