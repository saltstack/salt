"""
Regression test for https://github.com/saltstack/salt/issues/65317.

When the master runs the EventPublisher with ``publisher_acl`` (or
``external_auth``) configured, ``sock_dir`` must end up traversable
by non-root users so the publisher_acl-authorised salt CLI can reach
``master_event_pub.ipc`` and ``publish_pull.ipc``.

Since 3006.3 the master defaults to running as the ``salt`` user,
leaving ``sock_dir`` mode ``0o750`` and breaking non-root CLI
callers.  Fix: ``EventPublisher.run`` adds ``o+x`` to ``sock_dir``
when ``publisher_acl``/``external_auth`` is set.
"""

import logging
import os
import stat
import time

import pytest

import salt.config
import salt.utils.event
import salt.utils.process

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def sock_dir(tmp_path):
    path = tmp_path / "sock"
    path.mkdir(mode=0o750)
    # mkdir respects umask on some filesystems; force the mode we
    # are reproducing.
    os.chmod(str(path), 0o750)
    return path


def _master_opts(sock_dir, publisher_acl=None, external_auth=None):
    opts = salt.config.master_config("")
    opts["sock_dir"] = str(sock_dir)
    opts["publisher_acl"] = publisher_acl or {}
    opts["external_auth"] = external_auth or {}
    opts["ipc_mode"] = "ipc"
    return opts


def _wait_for_pub_socket(sock_dir, timeout=10.0):
    """
    Block until the EventPublisher has created its publish socket so we
    know the chmod path has been executed.
    """
    target = sock_dir / "master_event_pub.ipc"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if target.exists():
            return True
        time.sleep(0.05)
    return False


def _start_publisher(opts):
    pm = salt.utils.process.ProcessManager(wait_for_kill=5)
    proc = pm.add_process(
        salt.utils.event.EventPublisher,
        args=(opts,),
        name="EventPublisher",
    )
    return pm, proc


def test_event_publisher_makes_sock_dir_traversable_with_publisher_acl(sock_dir):
    """
    EventPublisher with publisher_acl set must add o+x to sock_dir so
    non-root CLI users can traverse into it.
    """
    opts = _master_opts(sock_dir, publisher_acl={"alice": [".*"]})
    assert not stat.S_IMODE(os.stat(str(sock_dir)).st_mode) & stat.S_IXOTH

    pm, _proc = _start_publisher(opts)
    try:
        assert _wait_for_pub_socket(
            sock_dir
        ), "EventPublisher never bound master_event_pub.ipc"
        # Give the chmod (which runs immediately after start()) a moment.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if stat.S_IMODE(os.stat(str(sock_dir)).st_mode) & stat.S_IXOTH:
                break
            time.sleep(0.05)
        mode = stat.S_IMODE(os.stat(str(sock_dir)).st_mode)
        assert mode & stat.S_IXOTH, (
            f"sock_dir mode {oct(mode)} missing o+x after EventPublisher "
            f"started with publisher_acl"
        )
    finally:
        pm.terminate()


def test_event_publisher_leaves_sock_dir_alone_without_publisher_acl(sock_dir):
    """
    Without publisher_acl/external_auth, the EventPublisher must NOT
    relax sock_dir perms.
    """
    opts = _master_opts(sock_dir)
    original_mode = stat.S_IMODE(os.stat(str(sock_dir)).st_mode)

    pm, _proc = _start_publisher(opts)
    try:
        assert _wait_for_pub_socket(sock_dir)
        # Wait a beat to ensure any chmod logic would have run.
        time.sleep(0.5)
        mode = stat.S_IMODE(os.stat(str(sock_dir)).st_mode)
        assert mode == original_mode, (
            f"sock_dir mode changed unexpectedly: {oct(original_mode)} -> "
            f"{oct(mode)}"
        )
    finally:
        pm.terminate()
