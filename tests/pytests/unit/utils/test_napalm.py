"""
Unit tests for salt.utils.napalm.
"""

import threading
import time

import salt.utils.napalm as napalm_utils
from tests.support.mock import MagicMock, patch


def test_call_serialises_concurrent_access():
    # An always-alive proxy shares one device (and one command channel) across
    # worker threads. call() must serialise them so their driver interactions
    # do not interleave (#55332).
    order = []
    entered = threading.Event()
    release = threading.Event()

    class FakeDriver:
        def cli(self, *args, **kwargs):
            order.append("enter")
            entered.set()
            # Hold the "channel" until the test releases it.
            release.wait(timeout=5)
            order.append("exit")
            return {"show version": "ok"}

    device = {
        "DRIVER": FakeDriver(),
        "UP": True,
        "LOCK": threading.RLock(),
        "__opts__": {},
    }

    def worker():
        napalm_utils.call(device, "cli", ["show version"])

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    # Wait until the first thread is inside cli() holding the lock.
    assert entered.wait(timeout=5)
    second.start()
    # Give the second thread time to reach the lock; it must block, so only the
    # first thread's "enter" is recorded so far.
    time.sleep(0.25)
    assert order == ["enter"]
    # Let the first thread finish; the second may now proceed.
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert not first.is_alive() and not second.is_alive()
    # Strictly serialised: one full enter/exit pair before the next begins.
    assert order == ["enter", "exit", "enter", "exit"]


def test_call_acquires_device_lock():
    # call() must enter and exit the device lock around the driver interaction.
    lock = MagicMock()
    driver = MagicMock()
    driver.cli.return_value = {"show version": "ok"}
    device = {"DRIVER": driver, "UP": True, "LOCK": lock, "__opts__": {}}
    result = napalm_utils.call(device, "cli", ["show version"])
    assert result["result"] is True
    lock.__enter__.assert_called_once()
    lock.__exit__.assert_called_once()
    driver.cli.assert_called_once()


def test_call_uses_reentrant_lock_on_reconnect():
    # On a dropped connection call() recurses into itself (close/open/re-exec)
    # while still holding the device lock, so the lock must be reentrant. A
    # plain Lock would deadlock here; RLock must not.
    class _Disconnect(Exception):
        pass

    driver = MagicMock()
    driver.cli.side_effect = [_Disconnect("dropped"), {"show version": "ok"}]
    lock = threading.RLock()
    device = {
        "DRIVER": driver,
        "UP": True,
        "LOCK": lock,
        "__opts__": {},
        "HOSTNAME": "device1",
    }

    result = []

    def run():
        with patch("salt.utils.napalm.HAS_CONN_CLOSED_EXC_CLASS", True), patch(
            "salt.utils.napalm.ConnectionClosedException", _Disconnect, create=True
        ):
            result.append(napalm_utils.call(device, "cli", ["show version"]))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(timeout=10)
    assert (
        not worker.is_alive()
    ), "call() deadlocked during reconnect; the device lock must be reentrant"
    assert result and result[0]["result"] is True
    assert result[0]["out"] == {"show version": "ok"}
    assert driver.cli.call_count == 2
    # The lock is fully released after the nested reconnect calls unwind.
    assert lock.acquire(blocking=False)
    lock.release()


def test_call_without_lock_runs_unserialised():
    # Devices built without a LOCK (hand-constructed, or inherited via
    # inherit_napalm_device) must still work, unserialised.
    driver = MagicMock()
    driver.cli.return_value = {"show version": "ok"}
    device = {"DRIVER": driver, "UP": True, "__opts__": {}}
    result = napalm_utils.call(device, "cli", ["show version"])
    assert result["result"] is True
    assert result["out"] == {"show version": "ok"}
    driver.cli.assert_called_once()
