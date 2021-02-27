"""
tests.unit.states.test_esxi
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the esxi state module
"""

import salt.modules.vsphere as vsphere
import salt.states.esxi as esxi
from tests.support.case import TestCase
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch


class TestCertificateVerify(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            esxi: {
                "__opts__": {"test": False},
                "__pillar__": {"proxy": {"host": "hostname", "proxytype": "esxi"}},
            },
            vsphere: {},
        }

    def test_certificate_verify(self):
        kwargs_values = [
            ("ssh_key", "TheSSHKeyFile"),
            ("ssh_key_file", "TheSSHKeyFile"),
        ]
        certificate_verify_values = (None, True, False)
        for kw_key, kw_value in kwargs_values:

            def esxi_cmd_wrapper(target, *args, **kwargs):
                # The esxi salt module just wraps the call to the esxi proxy
                # module which in turn calls the target method on the vsphere
                # execution moduile.
                # That would be a TON of mocking, so we just bypass all of that
                # wrapping
                if target == "upload_ssh_key":
                    return vsphere.upload_ssh_key(
                        "1.2.3.4", "root", "SuperSecret!", *args, **kwargs
                    )
                return {"hostname": {}}

            service_running = patch.dict(esxi.__salt__, {"esxi.cmd": esxi_cmd_wrapper})
            kwargs = {kw_key: kw_value}
            if kw_key == "ssh_key":
                expected_kwargs = {"data": kw_value}
            else:
                expected_kwargs = {"data_file": kw_value, "data_render": False}
            for certificate_verify_value in certificate_verify_values:
                http_query_mock = MagicMock()
                if certificate_verify_value is None:
                    certificate_verify_value = True
                with patch("salt.utils.http.query", http_query_mock), service_running:
                    esxi.ssh_configured(
                        "blah",
                        service_running=True,
                        service_restart=False,
                        certificate_verify=certificate_verify_value,
                        **kwargs
                    )
                http_query_mock.assert_called_once_with(
                    "https://1.2.3.4:443/host/ssh_root_authorized_keys",
                    method="PUT",
                    password="SuperSecret!",
                    status=True,
                    text=True,
                    username="root",
                    verify_ssl=certificate_verify_value,
                    **expected_kwargs
                )
