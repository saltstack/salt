"""
    :codeauthor: Eric Radman <ericshane@eradman.com>
"""

import pytest

from salt.cloud.clouds import joyent
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        joyent.HAS_REQUIRED_CRYPTO is False,
        reason="PyCrypto or Cryptodome not installed",
    )
]


def _fake_wait_for_ip(
    check_for_ip_fn, interval=None, timeout=None, interval_multiplier=None
):
    """
    Callback that returns immediately instead of waiting
    """
    assert isinstance(interval, int)
    assert isinstance(timeout, int)
    assert isinstance(interval_multiplier, int)
    return check_for_ip_fn()


@pytest.fixture
def configure_loader_modules():
    with patch("salt.utils.cloud.wait_for_ip", _fake_wait_for_ip):
        yield {
            joyent: {
                "__utils__": {
                    "cloud.fire_event": MagicMock(),
                    "cloud.bootstrap": MagicMock(),
                },
                "__opts__": {
                    "sock_dir": True,
                    "transport": True,
                    "providers": {"my_joyent": {}},
                    "profiles": {"my_joyent": {}},
                },
                "__active_provider_name__": "my_joyent:joyent",
            }
        }


@pytest.fixture
def vm_():
    return {
        "profile": "my_joyent",
        "name": "vm3",
        "driver": "joyent",
        "size": "k4-highcpu-kvm-750M",
        "image": "freebsd10",
        "location": "us-east-1",
    }


def test_query_instance_init(vm_):
    """
    Initial provisioning, no IP assigned
    """
    # Not yet reachable
    reply = (200, {"state": "provisioning"})
    with patch.object(joyent, "show_instance", return_value=reply):
        result = joyent.query_instance(vm_)
    joyent.__utils__["cloud.fire_event"].assert_called_once()
    assert result is None


def test_query_instance_has_ip(vm_):
    """
    IP address assigned but not yet ready
    """
    reply = (200, {"primaryIp": "1.1.1.1", "state": "provisioning"})
    with patch.object(joyent, "show_instance", return_value=reply):
        result = joyent.query_instance(vm_)
    joyent.__utils__["cloud.fire_event"].assert_called_once()
    assert result is None


def test_query_instance_ready(vm_):
    """
    IP address assigned, and VM is ready
    """
    reply = (200, {"primaryIp": "1.1.1.1", "state": "running"})
    with patch.object(joyent, "show_instance", return_value=reply):
        result = joyent.query_instance(vm_)
    joyent.__utils__["cloud.fire_event"].assert_called_once()
    assert result == "1.1.1.1"
