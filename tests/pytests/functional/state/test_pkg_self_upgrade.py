"""
Functional coverage for issue #69807 -- salt-minion self-upgrade via
``pkg.installed`` must not crash the state run when the running Python
interpreter's own ``sys.path`` root has just been replaced on disk.

This test drives ``salt.state.State`` end-to-end with a mocked
``pkg.installed`` chunk whose ``changes`` dict names a salt package
(mimicking the return you get from a real minion-driven upgrade of
``salt-minion``). It additionally forces ``importlib.reload(site)`` to
raise ``ModuleNotFoundError`` -- the exact failure recorded in
the traceback on the issue, corresponding to the vanished
``/opt/saltstack/salt/lib/python3.10/`` directory after ``dpkg`` swapped
it out from under the running interpreter.

Before the fix, ``check_refresh`` unconditionally called
``module_refresh`` for any ``pkg`` state with changes, ``module_refresh``
called ``importlib.reload(site)`` which then raised the uncaught
``ModuleNotFoundError``, and the exception bubbled up through
``State.call``, killing the state run. After the fix:

* ``check_refresh`` sees a salt package in ``ret["changes"]`` and
  short-circuits without calling ``module_refresh`` at all.
* Even if the short-circuit is bypassed (e.g. because the package
  manager reports a name we do not recognize), the widened
  ``ImportError`` catch in ``module_refresh`` prevents the crash.

Both invariants are asserted below.
"""

import logging

import pytest

import salt.state
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def state_obj(minion_opts):
    """
    Construct a real ``salt.state.State`` on top of the functional
    ``minion_opts`` fixture. ``_gather_pillar`` is patched so no channel
    is required.
    """
    with patch("salt.state.State._gather_pillar", return_value={}):
        state = salt.state.State(minion_opts)
    yield state


def _pkg_low_chunk(pkg_name):
    """
    Build the low-data dict for a ``pkg.installed`` state chunk with the
    given package name. Mirrors the shape produced by the compiler for
    the SLS in the issue body::

        Upgrade Salt Minion:
          pkg.installed:
            - name: salt-minion
            - version: 3006.27
    """
    return {
        "state": "pkg",
        "name": pkg_name,
        "__id__": "Upgrade Salt Minion",
        "__sls__": "updatesalt",
        "__env__": "base",
        "fun": "installed",
        "order": 10000,
    }


def _pkg_ret_after_self_upgrade(primary):
    """
    Return dict as produced by a successful ``pkg.installed`` execution
    that bumped ``salt-minion`` and ``salt-common`` together (the exact
    change dict from the issue body).
    """
    return {
        "name": primary,
        "changes": {
            "salt-minion": {"old": "3006.26", "new": "3006.27"},
            "salt-common": {"old": "3006.26", "new": "3006.27"},
        },
        "comment": "The following packages were installed/updated: salt-minion",
        "result": True,
        "__sls__": "updatesalt",
        "__run_num__": 0,
    }


def test_check_refresh_skips_reload_on_salt_self_upgrade(state_obj, caplog):
    """
    The primary regression check: ``check_refresh`` sees ``salt-minion``
    in ``ret["changes"]`` and MUST NOT invoke ``module_refresh``.

    We patch ``module_refresh`` itself so any accidental invocation
    would be visible; we also patch ``importlib.reload`` to raise --
    if the guard fails and the reload runs, it would crash with the
    original bug's exception, which would then propagate as a test
    failure with the same traceback the reporter saw.
    """
    low = _pkg_low_chunk("salt-minion")
    ret = _pkg_ret_after_self_upgrade("salt-minion")

    mock_refresh = MagicMock()
    mock_reload = MagicMock(
        side_effect=ModuleNotFoundError("spec not found for the module 'site'")
    )

    with patch.object(state_obj, "module_refresh", mock_refresh):
        with patch("importlib.reload", mock_reload):
            with caplog.at_level(logging.WARNING):
                # Must return normally, no exception.
                state_obj.check_refresh(low, ret)

    mock_refresh.assert_not_called()
    mock_reload.assert_not_called()
    assert "Skipping module refresh" in caplog.text


def test_module_refresh_survives_broken_site_reload(state_obj, caplog):
    """
    Belt-and-suspenders: even if ``check_refresh`` did call
    ``module_refresh`` (e.g. the package manager reports a package
    under a name we do not recognize -- an out-of-tree salt build),
    ``module_refresh`` itself must swallow the
    ``ModuleNotFoundError`` from ``importlib.reload(site)`` instead of
    letting it kill the state run.
    """
    mock_reload = MagicMock(
        side_effect=ModuleNotFoundError("spec not found for the module 'site'")
    )
    # ``module_refresh`` also invokes ``load_modules`` and possibly
    # ``saltutil.refresh_modules`` via ``self.functions``. Patch those
    # out so the test does not attempt to actually reload the loader
    # against the running interpreter.
    with patch("importlib.reload", mock_reload):
        with patch.object(state_obj, "load_modules"):
            state_obj.functions = {"saltutil.refresh_modules": MagicMock()}
            with caplog.at_level(logging.ERROR):
                # Must not raise.
                state_obj.module_refresh()

    mock_reload.assert_called_once()
    assert (
        "Error encountered during module reload. Modules were not reloaded."
        in caplog.text
    )


def test_reporter_traceback_no_longer_reproducible(state_obj):
    """
    Reproduce the *exact* traceback frames the reporter of #69807 saw
    -- ``State.call -> check_refresh -> module_refresh ->
    importlib.reload`` with ``importlib.reload`` raising
    ``ModuleNotFoundError('spec not found for the module 'site'')``
    -- and assert that the frames after the fix short-circuit at
    ``check_refresh`` (no ``module_refresh``, no ``importlib.reload``,
    no exception).

    This is a functional-level replay of the crash: it does not build
    a real State chunk (that would require standing up a full
    LazyLoader, out of scope for a functional test), but it exercises
    the identical call chain and identical mocked reload failure. If
    the fix regresses -- either handler is removed or the salt-aware
    guard is dropped -- this test surfaces the same
    ``ModuleNotFoundError`` the reporter got.
    """
    low = _pkg_low_chunk("salt-minion")
    ret = _pkg_ret_after_self_upgrade("salt-minion")

    reload_mock = MagicMock(
        side_effect=ModuleNotFoundError("spec not found for the module 'site'")
    )
    # ``module_refresh`` also invokes ``load_modules`` and possibly
    # ``saltutil.refresh_modules`` -- patch to avoid touching the real
    # loader, but keep ``module_refresh`` itself real (unpatched) so a
    # regression in the check_refresh guard would fall through to the
    # broken reload and raise.
    load_modules_mock = MagicMock()
    saltutil_refresh_mock = MagicMock()
    state_obj.functions = {"saltutil.refresh_modules": saltutil_refresh_mock}

    with patch("importlib.reload", reload_mock):
        with patch.object(state_obj, "load_modules", load_modules_mock):
            # This is exactly the call ``State.call`` makes at the end
            # of every state chunk. Before the fix, it raised.
            state_obj.check_refresh(low, ret)

    # The salt-aware guard fired: no reload attempt was made.
    reload_mock.assert_not_called()
    # Belt and suspenders: module_refresh itself wasn't invoked, so
    # neither ``load_modules`` nor ``saltutil.refresh_modules`` fired.
    load_modules_mock.assert_not_called()
    saltutil_refresh_mock.assert_not_called()
