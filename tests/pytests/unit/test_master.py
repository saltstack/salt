import time

import salt.master
from tests.support.mock import patch


def test_fileserver_duration():
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.called_once()
        # Timeout is 1 second
        assert 2 > end - start > 1
