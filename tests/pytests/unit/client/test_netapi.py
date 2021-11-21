import logging

import salt.client.netapi
import salt.config
from tests.support.mock import Mock, patch


def test_run_log(caplog):
    """
    test salt.client.netapi logs correct message
    """
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["rest_cherrypy"] = {"port": 8000}
    mock_process = Mock()
    mock_process.add_process.return_value = True
    patch_process = patch.object(salt.utils.process, "ProcessManager", mock_process)
    with caplog.at_level(logging.INFO):
        with patch_process:
            netapi = salt.client.netapi.NetapiClient(opts)
            netapi.run()
    assert "Starting RunNetapi(salt.loaded.int.netapi.rest_cherrypy)" in caplog.text
