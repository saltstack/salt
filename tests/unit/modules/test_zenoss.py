import salt.modules.config as config
import salt.modules.zenoss as zenoss
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class ZenossTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.keystone
    """

    def setup_loader_modules(self):
        return {
            zenoss: {"__salt__": {"config.option": config.option}},
            config: {"__opts__": {}},
        }

    def test_zenoss_session(self):
        """
        test zenoss._session when using verify_ssl
        """
        zenoss_conf = {
            "zenoss": {
                "hostname": "https://test.zenoss.com",
                "username": "admin",
                "password": "test123",
            }
        }

        for verify in [True, False, None]:
            zenoss_conf["zenoss"]["verify_ssl"] = verify
            if verify is None:
                zenoss_conf["zenoss"].pop("verify_ssl")
                verify = True

            patch_opts = patch.dict(config.__opts__, zenoss_conf)
            mock_http = MagicMock(return_value=None)
            patch_http = patch("salt.utils.http.session", mock_http)

            with patch_http, patch_opts:
                zenoss._session()
                self.assertEqual(
                    mock_http.call_args_list,
                    [
                        call(
                            ca_bundle=None,
                            headers={"Content-type": "application/json; charset=utf-8"},
                            password="test123",
                            user="admin",
                            verify_ssl=verify,
                        )
                    ],
                )
