import logging

import salt.config
from tests.support.helpers import PRE_PYTEST_SKIP

# Using the PRE_PYTEST_SKIP decorator since this test still fails on some platforms.
# Will investigate later.


@PRE_PYTEST_SKIP
def test_jid_in_logs(caplog, salt_call_cli):
    """
    Test JID in log_format
    """
    jid_formatted_str = salt.config._DFLT_LOG_FMT_JID.split("%")[0]
    formatter = logging.Formatter(fmt="%(jid)s %(message)s")
    with caplog.at_level(logging.DEBUG):
        previous_formatter = caplog.handler.formatter
        try:
            caplog.handler.setFormatter(formatter)
            ret = salt_call_cli.run("test.ping")
            assert ret.exitcode == 0
            assert ret.json is True

            assert_error_msg = (
                "'{}' not found in log messages:\n>>>>>>>>>{}\n<<<<<<<<<".format(
                    jid_formatted_str, caplog.text
                )
            )
            assert jid_formatted_str in caplog.text, assert_error_msg
        finally:
            caplog.handler.setFormatter(previous_formatter)
