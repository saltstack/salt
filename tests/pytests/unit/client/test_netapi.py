import logging

import salt.client.netapi
from tests.support.mock import Mock, patch


def test_run_log(caplog, master_opts):
    """
    test salt.client.netapi logs correct message
    """
    master_opts["rest_cherrypy"] = {"port": 8000}
    mock_process = Mock()
    mock_process.add_process.return_value = True
    patch_process = patch.object(salt.utils.process, "ProcessManager", mock_process)
    with caplog.at_level(logging.INFO):
        with patch_process:
            netapi = salt.client.netapi.NetapiClient(master_opts)
            netapi.run()
    assert "Starting RunNetapi(salt.loaded.int.netapi.rest_cherrypy)" in caplog.text


def test_run_netapi_can_take_process_kwargs():
    salt.client.netapi.RunNetapi({}, "fname", name="name")
