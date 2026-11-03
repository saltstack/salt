import asyncio

import salt.pillar
from tests.support.mock import MagicMock, patch


def test_local_async_pillar_aclose():
    opts = {"file_client": "local", "state_top": "top.sls", "pillar_roots": {}}
    client, fileclient = MagicMock(), MagicMock()
    with (
        patch("salt.fileclient.get_file_client", side_effect=[client, fileclient]),
        patch("salt.loader.matchers", return_value={}),
        patch("salt.loader.render", return_value={}),
        patch("salt.loader.pillars", return_value={}),
    ):
        pillar = salt.pillar.get_async_pillar(opts, {}, "minion", funcs={})
    assert isinstance(pillar, salt.pillar.AsyncPillar)

    async def close_twice():
        try:
            await pillar.aclose()
            client.destroy.assert_called_once_with()
            fileclient.destroy.assert_called_once_with()
            await pillar.aclose()
            client.destroy.assert_called_once_with()
            fileclient.destroy.assert_called_once_with()
        finally:
            pillar.destroy()

    asyncio.run(close_twice())
