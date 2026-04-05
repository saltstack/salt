import asyncio
import logging

import salt.client.netapi
from tests.support.mock import MagicMock, Mock, patch


def test_run_log(caplog, master_opts):
    """
    test salt.client.netapi logs correct message
    """
    master_opts["rest_cherrypy"] = {"port": 8000}
    mock_process = MagicMock()
    mock_process.add_process.return_value = True

    # mock_process.run() needs to be a coroutine because
    # netapi.run() calls asyncio.run()
    async def mock_run():
        return True

    mock_process.run = MagicMock(side_effect=mock_run)

    patch_process = patch.object(
        salt.utils.process, "ProcessManager", return_value=mock_process
    )
    with caplog.at_level(logging.INFO):
        with patch_process:
            netapi = salt.client.netapi.NetapiClient(master_opts)
            netapi.run()
    expected = "Starting RunNetapi(salt.loaded.int.netapi.rest_cherrypy)"
    assert expected in caplog.text


def test_run_netapi_can_take_process_kwargs():
    salt.client.netapi.RunNetapi({}, "fname", name="name")
