"""
Signal handling for the salt-proxy daemon.
"""

import signal

import salt.cli.daemons
import salt.utils.parsers
from tests.support.mock import MagicMock, patch


def _proxy_daemon(minion):
    """
    A ProxyMinion daemon instance without running the option-parser __init__.
    """
    daemon = salt.cli.daemons.ProxyMinion.__new__(salt.cli.daemons.ProxyMinion)
    daemon.minion = minion
    return daemon


def test_proxy_minion_signal_leaves_exit_to_the_graceful_stop():
    """
    ``MinionManager.stop()`` only *schedules* ``stop_async`` on the io_loop and
    hands it the parent signal handler to run once the graceful shutdown has
    finished.  Calling the parent handler here as well exits the process
    immediately, so the io_loop never runs ``stop_async`` -- Python reports it
    as "coroutine 'MinionManager.stop_async' was never awaited" -- and nothing
    is flushed or torn down.  ``Minion._handle_signals`` already gets this
    right; the proxy daemon did not.
    """
    minion = MagicMock()
    daemon = _proxy_daemon(minion)

    with patch.object(salt.utils.parsers.DaemonMixIn, "_handle_signals") as parent:
        daemon._handle_signals(signal.SIGTERM, None)

    # The graceful stop is asked for ...
    assert minion.stop.called
    # ... and the process is NOT torn down out from under it.
    assert not parent.called


def test_proxy_minion_signal_still_exits_without_a_stop_method():
    """
    Inverse: when the minion has no ``stop`` there is no graceful path to wait
    for, so the parent handler must still run -- the guard must not leave the
    daemon unable to exit on a signal.
    """
    minion = MagicMock(spec=[])
    daemon = _proxy_daemon(minion)

    with patch.object(salt.utils.parsers.DaemonMixIn, "_handle_signals") as parent:
        daemon._handle_signals(signal.SIGTERM, None)

    assert parent.called
