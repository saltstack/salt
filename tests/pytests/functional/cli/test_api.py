import os
import sys

import pytest
from salt._logging.impl import get_log_record_factory, set_log_record_factory
from salt.cli.api import SaltAPI


@pytest.mark.slow_test
def test_start_shutdown(monkeypatch, tmp_path):
    pid_file = str(tmp_path / "pid_file")
    log_file = str(tmp_path / "log_file")
    api = SaltAPI()
    orig_factory = get_log_record_factory()
    with pytest.raises(SystemExit):
        # testing environment will fail if we use default pidfile
        # overwrite sys.argv so salt-api does not use testing args
        monkeypatch.setattr(
            "sys.argv", [sys.argv[0], "--pid-file", pid_file, "--log-file", log_file]
        )
        try:
            api.start()
            assert os.path.isfile(pid_file)
            assert os.path.isfile(log_file)
            api.shutdown()
        finally:
            set_log_record_factory(orig_factory)
