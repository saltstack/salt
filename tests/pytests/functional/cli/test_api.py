import os
import sys

import pytest
from salt.cli.api import SaltAPI


@pytest.mark.slow_test
def test_start_shutdown(monkeypatch, tmp_path):
    pid_file = str(tmp_path / "pid_file")
    log_file = str(tmp_path / "log_file")
    api = SaltAPI()
    with pytest.raises(SystemExit):
        # testing environment will fail if we use default pidfile
        # overwrite sys.argv so salt-api does not use testing args
        monkeypatch.setattr(
            "sys.argv", [sys.argv[0], "--pid-file", pid_file, "--log-file", log_file]
        )
        api.start()
        assert os.path.isfile(pid_file)
        assert os.path.isfile(log_file)
        api.shutdown()
