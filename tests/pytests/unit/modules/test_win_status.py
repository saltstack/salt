import psutil
import pytest

import salt.modules.win_status as win_status

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


def test__get_connected_ips():
    # Let's find an active connection to test with
    port = None
    ip = None
    conns = psutil.net_connections()
    for conn in conns:
        if conn.status == psutil.CONN_ESTABLISHED:
            ip = conn.raddr.ip
            port = conn.raddr.port
            break
    assert port is not None
    assert ip is not None
    # Since this may return more than one IP, let's make sure our test IP is in
    # the list of IPs
    assert ip in win_status._get_connected_ips(port)
