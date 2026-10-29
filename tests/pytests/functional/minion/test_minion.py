import pytest

import salt.minion
from salt.exceptions import SaltReqTimeoutError


def test_minion_send_req_sync_timeout(minion_opts):
    """
    Ensure Minion._send_req_sync raises SaltReqTimeoutError when no reply is
    received, so callers like _return_pub can catch it correctly.
    """
    minion = salt.minion.Minion(minion_opts)
    with pytest.raises(SaltReqTimeoutError):
        minion._send_req_sync({"load": "meh"}, 10)
