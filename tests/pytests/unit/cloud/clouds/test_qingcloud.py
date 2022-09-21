import pytest

from salt.cloud.clouds import qingcloud
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        qingcloud: {
            "__opts__": {
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
                },
                "profiles": {"qingcloud": {}},
            },
            "__active_provider_name__": "qingcloud:qingcloud",
        },
    }


def test_qingcloud_verify_ssl():
    """
    test qinglcoud when using verify_ssl
    """
    patch_sig = patch("salt.cloud.clouds.qingcloud._compute_signature", MagicMock())

    for verify in [True, False, None]:
        mock_requests = MagicMock()
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.text = '{"ret_code": 0}'
        patch_requests = patch("requests.get", mock_requests)
        with patch.dict(
            qingcloud.__opts__["providers"]["qingcloud"]["qingcloud"],
            {"verify_ssl": verify},
        ):
            with patch_sig, patch_requests:
                ret = qingcloud.query()
                assert ret["ret_code"] == 0
                assert mock_requests.call_args_list[0].kwargs["verify"] == verify
