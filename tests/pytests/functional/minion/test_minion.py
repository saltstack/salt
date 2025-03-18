import pytest

import salt.minion


def test_minion_send_req_async(minion_opts):
    """
    Ensure Minion._send_req_sync raises a TimeoutError when no reply is
    received.
    """

    minion = salt.minion.Minion(minion_opts)
    with pytest.raises(TimeoutError):
        minion._send_req_sync({"load": "meh"}, 10)
