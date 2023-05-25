import urllib.parse

import pytest
import tornado

import salt.utils.json
from salt.netapi.rest_tornado import saltnado
from tests.support.mock import MagicMock, patch


@pytest.fixture
def app_urls():
    return [
        (r"/hook(/.*)?", saltnado.WebhookSaltAPIHandler),
    ]


async def test_hook_can_handle_get_parameters(http_client, app, content_type_map):

    with patch("salt.utils.event.get_event") as get_event:
        with patch.dict(app.mod_opts, {"webhook_disable_auth": True}):
            event = MagicMock()
            event.fire_event.return_value = True
            get_event.return_value = event
            response = await http_client.fetch(
                "/hook/my_service/?param=1&param=2",
                body=salt.utils.json.dumps({}),
                method="POST",
                headers={"Content-Type": content_type_map["json"]},
            )
            assert response.code == 200
            host = urllib.parse.urlparse(response.effective_url).netloc
            event.fire_event.assert_called_once_with(
                {
                    "headers": {
                        "Content-Length": "2",
                        "Connection": "close",
                        "Content-Type": "application/json",
                        "Host": host,
                        "Accept-Encoding": "gzip",
                        "User-Agent": f"Tornado/{tornado.version}",
                    },
                    "post": {},
                    "get": {"param": ["1", "2"]},
                },
                "salt/netapi/hook/my_service/",
            )
