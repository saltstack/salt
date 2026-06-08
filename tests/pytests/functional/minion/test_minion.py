import pytest

import salt.minion
from salt.exceptions import SaltReqTimeoutError


def test_minion_send_req_async(minion_opts):
    """
    Ensure Minion._send_req_sync raises a SaltReqTimeoutError when no reply
    is received.
    """

    minion = salt.minion.Minion(minion_opts)
    with pytest.raises(SaltReqTimeoutError):
        minion._send_req_sync({"load": "meh"}, 10)
