import os
import sys
import tempfile

import pytest
from salt.cli.api import SaltAPI
from tests.support.mock import patch


@pytest.mark.slow_test
def test_start_shutdown():
    pidfile = tempfile.mktemp()
    logfile = tempfile.mktemp()
    api = SaltAPI()
    with pytest.raises(SystemExit):
        try:
            # testing environment will fail if we use default pidfile
            # overwrite sys.argv so salt-api does not use testing args
            with patch.object(sys, "argv", [sys.argv[0], "--pid-file", pidfile]):
                api.start()
                assert os.path.isfile(pidfile)
                api.shutdown()
        finally:
            try:
                os.remove(pidfile)
            except OSError:
                pass
            try:
                os.remove(logfile)
            except OSError:
                pass
