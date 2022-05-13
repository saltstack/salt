import copy

from salt.cloud.clouds import qingcloud
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class QingCloudTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for salt.cloud.clouds.qingcloud module.
    """

    def setUp(self):
        self.provider = {
            "providers": {
                "qingcloud": {
                    "qingcloud": {
                        "access_key_id": "key_1234",
                        "secret_access_key": "1234",
                        "zone": "test_zone",
                        "key_filename": "/testfilename",
                        "driver": "qingcloud",
                    }
                }
            }
        }

    def setup_loader_modules(self):
        return {
            qingcloud: {
                "__opts__": {
                    "providers": {"qingcloud": {}},
                    "profiles": {"qingcloud": {}},
                },
                "__active_provider_name__": "qingcloud:qingcloud",
            },
        }

    def test_qingcloud_verify_ssl(self):
        """
        test qinglcoud when using verify_ssl
        """
        patch_sig = patch("salt.cloud.clouds.qingcloud._compute_signature", MagicMock())

        for verify in [True, False, None]:
            mock_requests = MagicMock()
            mock_requests.return_value.status_code = 200
            mock_requests.return_value.text = '{"ret_code": 0}'
            patch_requests = patch("requests.get", mock_requests)
            opts = copy.deepcopy(self.provider)
            opts["providers"]["qingcloud"]["qingcloud"]["verify_ssl"] = verify
            patch_opts = patch.dict(qingcloud.__opts__, opts)
            with patch_sig, patch_requests, patch_opts:
                ret = qingcloud.query()
                self.assertEqual(ret["ret_code"], 0)
                self.assertEqual(
                    mock_requests.call_args_list[0].kwargs["verify"], verify
                )
