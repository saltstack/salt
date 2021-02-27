import salt.proxy.panos as panos
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class PanosProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {panos: {"DETAILS": {}, "__pillar__": {}}}

    def setUp(self):
        self.opts = {
            "proxy": {"proxytype": "panos", "host": "hosturl.com", "apikey": "api_key"}
        }

    def test_init(self):
        for verify in [True, False, None]:
            self.opts["proxy"]["verify_ssl"] = verify
            if verify is None:
                self.opts["proxy"].pop("verify_ssl")
                verify = True
            mock_http = MagicMock(
                return_value={"status": 200, "text": "<data>some_test_data</data>"}
            )
            patch_http = patch.dict(panos.__utils__, {"http.query": mock_http})
            with patch_http:
                panos.init(self.opts)
            self.assertEqual(
                mock_http.call_args_list,
                [
                    call(
                        "https://hosturl.com/api/",
                        data={
                            "type": "op",
                            "cmd": "<show><system><info></info></system></show>",
                            "key": "api_key",
                        },
                        decode=True,
                        decode_type="plain",
                        method="POST",
                        raise_error=True,
                        status=True,
                        verify_ssl=verify,
                    )
                ],
            )
