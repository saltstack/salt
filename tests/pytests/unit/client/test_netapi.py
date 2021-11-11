import pytest
import salt.client.netapi
import salt.config
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import Mock, patch


def test_run_log():
    """
    test salt.client.netapi logs correct message
    """
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["rest_cherrypy"] = {"port": 8000}
    mock_process = Mock()
    mock_process.add_process.return_value = True
    patch_process = patch.object(salt.utils.process, "ProcessManager", mock_process)
    exp_msg = "INFO:Starting RunNetapi(salt.loaded.int.netapi.rest_cherrypy)"
    found = False
    with TstSuiteLoggingHandler() as handler:
        with patch_process:
            netapi = salt.client.netapi.NetapiClient(opts)
            netapi.run()
        for message in handler.messages:
            if "RunNetapi" in message:
                assert exp_msg == message
                found = True
                break
    if not found:
        pytest.fail("Log message not found: {}".format(exp_msg))
