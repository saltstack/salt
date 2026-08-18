import pytest

import salt.modules.config as config
import salt.modules.msteams as msteams
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts.update({"msteams": {"hook_url": "https://example.com/web_hook"}})
    msteams_obj = {
        msteams: {"__opts__": minion_opts, "__salt__": {"config.get": config.get}},
        config: {
            "__opts__": minion_opts,
            "__grains__": {},
        },
    }
    return msteams_obj


def test_post_card():
    http_ret = {"status": 200}
    http_mock = MagicMock(return_value=http_ret)
    with patch("salt.utils.http.query", http_mock):
        ret = msteams.post_card("test")
        assert ret
        http_mock.assert_called_once_with(
            "https://example.com/web_hook",
            method="POST",
            header_dict={"Content-Type": "application/json"},
            data='{"text": "test", "title": null, "themeColor": null}',
            status=True,
        )
