"""
Regression tests for the scheduler two-loader model.

The scheduler is an internal Salt subsystem: it must be able to call the
``timezone.get_offset`` and ``config.merge`` execution modules for its own
bookkeeping regardless of the operator's ``whitelist_modules`` setting.
Only user-configured scheduled jobs should be gated by the whitelist.

Salt's :func:`salt.loader.minion_mods` factory exposes the unfiltered inner
LazyLoader as ``ret._dunder_salt`` on the outer (whitelist-filtered) loader
so downstream subsystems can propagate the two-loader model.  These tests
verify that :class:`salt.utils.schedule.Schedule` reads internal helpers
through that inner loader (via the ``Schedule._dunder_salt`` property) and
falls back to ``self.functions`` when the inner loader is not present
(salt-ssh FunctionWrapper, plain-dict tests).
"""

import copy
import logging

import pytest

import salt.config
import salt.utils.schedule
from salt.utils.process import SubprocessList
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def _make_minion_opts(tmp_path):
    root_dir = tmp_path / "schedule-whitelist-tests"
    default_config = salt.config.minion_config(None)
    default_config["conf_dir"] = str(root_dir)
    default_config["root_dir"] = str(root_dir)
    default_config["sock_dir"] = str(root_dir / "test-socks")
    default_config["pki_dir"] = str(root_dir / "pki")
    default_config["cachedir"] = str(root_dir / "cache")
    return default_config


class _FakeOuterLoader(dict):
    """
    Minimal stand-in for the whitelist-filtered outer LazyLoader.

    Only ``__contains__`` / ``__getitem__`` / ``get`` are exercised by the
    scheduler paths under test; a dict is a sufficient shape.  The
    ``_dunder_salt`` attribute mirrors the real LazyLoader attribute
    :func:`salt.loader.minion_mods` sets at ``ret._dunder_salt = salt_dunder``.
    """


@pytest.fixture
def _dunder_test_env(tmp_path):
    subprocess_list = SubprocessList()
    try:
        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            yield tmp_path, subprocess_list
    finally:
        subprocess_list.cleanup()


def test_dunder_salt_prefers_inner_loader(_dunder_test_env):
    """
    When ``functions._dunder_salt`` is set (real two-loader model),
    :attr:`Schedule._dunder_salt` returns the inner unfiltered loader.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    inner = {"test.ping": lambda: True, "config.merge": lambda *a, **k: {}}
    outer._dunder_salt = inner

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched._dunder_salt is inner
    finally:
        sched.reset()


def test_dunder_salt_falls_back_when_attribute_missing(_dunder_test_env):
    """
    When ``functions`` is a plain dict (no ``_dunder_salt``), the property
    falls back to ``self.functions`` -- existing test / salt-ssh behavior.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    functions = {"test.ping": lambda: True}

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        functions,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched._dunder_salt is functions
    finally:
        sched.reset()


def test_dunder_salt_falls_back_when_attribute_none(_dunder_test_env):
    """
    ``_dunder_salt`` explicitly set to ``None`` on the outer loader also
    falls back to ``self.functions``.  Guards against a loader factory
    that sets the attribute defensively before populating it.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    outer._dunder_salt = None

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched._dunder_salt is outer
    finally:
        sched.reset()


def test_option_dispatches_config_merge_via_inner_loader(_dunder_test_env):
    """
    :meth:`Schedule.option` must call ``config.merge`` through the inner
    loader so it works even when the operator's ``whitelist_modules``
    excludes ``config`` from the wire-facing outer loader.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    outer_merge = MagicMock(name="outer.config.merge")
    inner_merge = MagicMock(name="inner.config.merge", return_value={"from": "inner"})

    outer = _FakeOuterLoader({"config.merge": outer_merge})
    inner = {"config.merge": inner_merge}
    outer._dunder_salt = inner

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        # ``__singleton_init__`` invokes ``self.option("schedule_returner")``
        # once as part of setup; reset the mocks so this test only asserts
        # against the explicit call below.
        inner_merge.reset_mock()
        outer_merge.reset_mock()
        result = sched.option("some_opt")
        assert result == {"from": "inner"}
        inner_merge.assert_called_once_with("some_opt", {}, omit_master=True)
        outer_merge.assert_not_called()
    finally:
        sched.reset()


def test_option_works_when_config_absent_from_outer_but_present_in_inner(
    _dunder_test_env,
):
    """
    Concrete whitelist scenario: operator has ``whitelist_modules: [test]``
    so the outer wire loader has no ``config.merge``, but the shipped
    inner loader still does.  :meth:`Schedule.option` must succeed.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    inner = {
        "test.ping": lambda: True,
        "config.merge": lambda opt, default, omit_master=False: {"merged": opt},
    }
    outer._dunder_salt = inner

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched.option("schedule_returner") == {"merged": "schedule_returner"}
    finally:
        sched.reset()


def test_option_falls_back_to_opts_when_neither_loader_has_config(_dunder_test_env):
    """
    When neither the outer nor the inner loader ships ``config.merge``,
    :meth:`Schedule.option` must fall back to ``self.opts.get(opt, {})``
    -- preserved behavior for standalone / minimal-fixture callers.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)
    opts["some_opt"] = "value-from-opts"

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    outer._dunder_salt = {"test.ping": lambda: True}

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched.option("some_opt") == "value-from-opts"
    finally:
        sched.reset()


def test_time_offset_read_from_inner_loader(_dunder_test_env):
    """
    ``__singleton_init__`` calls ``timezone.get_offset`` to seed
    ``self.time_offset``.  With a whitelist that omits ``timezone``, the
    outer loader will not have the function -- the inner loader must.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    inner_get_offset = MagicMock(return_value="-0700")

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    outer._dunder_salt = {
        "test.ping": lambda: True,
        "timezone.get_offset": inner_get_offset,
    }

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched.time_offset == "-0700"
        inner_get_offset.assert_called_once_with()
    finally:
        sched.reset()


def test_time_offset_defaults_to_0000_when_inner_loader_raises(_dunder_test_env):
    """
    If the inner ``timezone.get_offset`` raises, the scheduler must still
    initialize with the documented ``"0000"`` fallback.  Preserves
    behavior in the ``try/except`` around the offset read.
    """
    tmp_path, subprocess_list = _dunder_test_env
    opts = _make_minion_opts(tmp_path)

    def _boom():
        raise RuntimeError("timezone lookup failed")

    outer = _FakeOuterLoader({"test.ping": lambda: True})
    outer._dunder_salt = {"timezone.get_offset": _boom}

    sched = salt.utils.schedule.Schedule(
        copy.deepcopy(opts),
        outer,
        returners={},
        new_instance=True,
        _subprocess_list=subprocess_list,
    )
    try:
        assert sched.time_offset == "0000"
    finally:
        sched.reset()
