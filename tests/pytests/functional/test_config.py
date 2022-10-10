import logging
import os
import tempfile

import pytest

import salt.config

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


def test_minion_config_type_check(caplog):
    msg = "Config option 'ipc_write_buffer' with value"
    caplog.set_level(logging.WARNING)
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write("ipc_write_buffer: 'dynamic'\n")
        salt.config.minion_config(path)

        assert msg not in caplog.text
    finally:
        os.remove(path)
