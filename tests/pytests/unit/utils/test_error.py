"""
Tests for salt.utils.error.

Includes a regression test for issue #70175: the ``fire_exception``
helper used to construct a bare ``salt.utils.event.SaltEvent``, call
``.fire_event()`` on it, and drop the reference -- so cleanup was
deferred to GC ``__del__`` and each finalization emitted the
three-warning triad (``unclosed publish server`` / ``unclosed publisher
client`` / ``unclosed SyncWrapper``) from the underlying transport
chain.
"""

import gc
import warnings

import salt.exceptions
import salt.utils.error


def test_fire_exception_context_managed_no_unclosed_warnings(tmp_path):
    """
    Regression test for issue #70175 (receive-path leg).

    ``salt.utils.error.fire_exception`` -- called from
    ``salt/minion.py:_thread_return`` (job-exception path), and from
    ``salt/metaproxy/{proxy,deltaproxy}.py`` -- constructed a
    ``SaltEvent`` in a bare local, called ``.fire_event()`` on it, and
    dropped the reference.  With no context manager and no explicit
    ``destroy()``, cleanup ran only when GC eventually invoked
    ``SaltEvent.__del__``.  Each finalization emitted the three-warning
    triad from the underlying transport chain:

        unclosed publish server <PublishServer ...>
        unclosed publisher client <_TCPPubServerPublisher ...>
        unclosed SyncWrapper for cls=<class '..._TCPPubServerPublisher'>

    Companion to PR #70206 (shutdown-time ``MinionManager`` destroy
    chain) and the sibling per-job caller fix on
    ``salt.modules.event.fire_master`` / ``salt.modules.mine._mine_send``.
    This test guards the third leg: the ``fire_exception`` helper.

    Test shape mirrors
    ``test_fire_master_context_managed_no_unclosed_warnings``: drive N=50
    dispatches through the helper and assert no unclosed-resource
    warnings surface after a forced ``gc.collect()``.
    """
    tmp_sock = tmp_path / "sock"
    tmp_sock.mkdir()
    opts = {
        "id": "test-minion",
        "sock_dir": str(tmp_sock),
        "transport": "tcp",
        "ipc_mode": "ipc",
        "hash_type": "sha256",
        "acceptance_wait_time": 0,
        "acceptance_wait_time_max": 0,
        "loop_interval": 60,
        "local": False,
        "max_event_size": 1048576,
    }

    triad_markers = (
        "unclosed publish server",
        "unclosed publisher client",
        "unclosed SyncWrapper",
    )
    n_iterations = 50

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        warnings.simplefilter("always")
        for i in range(n_iterations):
            exc = salt.exceptions.MinionError(f"boom {i}")
            salt.utils.error.fire_exception(exc, opts)
        # Force any deferred ``__del__`` runs.
        gc.collect()
        gc.collect()

    leaked = [
        str(record.message)
        for record in caught
        if any(marker in str(record.message) for marker in triad_markers)
    ]

    assert not leaked, (
        f"fire_exception leaked {len(leaked)} unclosed-resource warnings "
        f"across {n_iterations} iterations (expected 0).  Sample warnings:\n"
        + "\n".join(f"  - {msg[:160]}" for msg in leaked[:6])
    )
