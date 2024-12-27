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
            ip = conn.laddr.ip
            port = conn.laddr.port
            break
    assert port is not None
    assert ip is not None
    assert win_status._get_connected_ips(port) == {ip}
