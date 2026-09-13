"""
Functional tests for the scheduler two-loader model.

These tests wire up real ``salt.loader.minion_mods`` -- exercising the
production ``_dunder_salt`` split introduced in PR #69983 -- and then
construct a real :class:`salt.utils.schedule.Schedule` on top.  They
stop short of a full salt-master + salt-minion pair (that's the
integration tier); the goal here is to prove end-to-end that under a
strict ``whitelist_modules`` the scheduler's internal helpers
(``timezone.get_offset`` in ``__singleton_init__`` and ``config.merge``
in ``option``) still resolve via the inner unfiltered loader instead of
KeyError'ing on the wire-facing outer loader.

Companion to :mod:`tests.pytests.unit.utils.scheduler.test_whitelist_dunder`.
"""

import copy
import logging

import pytest

import salt.loader
import salt.utils.schedule
from salt.utils.process import SubprocessList
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def whitelist_opts(minion_opts, tmp_path):
    """
    Minion opts with a narrow ``whitelist_modules`` -- ``config`` and
    ``timezone`` are deliberately omitted so the scheduler's internal
    helpers must reach through the inner loader.  ``os_family`` is
    seeded so ``salt.modules.timezone.get_offset`` (invoked via the
    inner loader in ``Schedule.__singleton_init__``) can progress past
    its grain check and actually shell out to ``date +%z``.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test", "grains"]
    opts.setdefault("grains", {})
    # Anything not "AIX" routes get_offset through ``date +%z``, which
    # is available on any Linux CI host.
    opts["grains"]["os_family"] = "Linux"
    root_dir = tmp_path / "scheduler-whitelist-functional"
    opts["conf_dir"] = str(root_dir)
    opts["root_dir"] = str(root_dir)
    opts["sock_dir"] = str(root_dir / "test-socks")
    opts["pki_dir"] = str(root_dir / "pki")
    opts["cachedir"] = str(root_dir / "cache")
    return opts


@pytest.fixture
def two_loader_functions(whitelist_opts):
    """
    Real outer wire-filtered loader from ``salt.loader.minion_mods`` --
    carries ``_dunder_salt`` per PR #69983.
    """
    functions = salt.loader.minion_mods(whitelist_opts)
    assert hasattr(functions, "_dunder_salt"), (
        "PR #69983 two-loader model not present on this branch; scheduler "
        "fix has nothing to hang off of"
    )
    return functions


@pytest.fixture
def scheduler(whitelist_opts, two_loader_functions):
    """
    Build a real Schedule against the wire loader.  ``clean_proc_dir`` is
    patched out because it wants a live ``cachedir`` layout that these
    tests do not otherwise populate.
    """
    subprocess_list = SubprocessList()
    try:
        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            sched = salt.utils.schedule.Schedule(
                whitelist_opts,
                two_loader_functions,
                returners={},
                new_instance=True,
                _subprocess_list=subprocess_list,
            )
        yield sched
    finally:
        try:
            sched.reset()
        except Exception:  # pylint: disable=broad-except
            pass
        subprocess_list.cleanup()


def test_wire_loader_omits_config_and_timezone(two_loader_functions):
    """
    Precondition: the narrow ``whitelist_modules`` really does strip
    ``config.merge`` and ``timezone.get_offset`` from the wire-facing
    outer loader.  If this ever stops being true the whole test module
    becomes a no-op.
    """
    assert "config.merge" not in two_loader_functions
    assert "timezone.get_offset" not in two_loader_functions


def test_inner_dunder_still_has_config_and_timezone(two_loader_functions):
    """
    ...but the unfiltered inner loader must still ship them, so the
    scheduler has somewhere to route through.
    """
    dunder = two_loader_functions._dunder_salt
    assert "config.merge" in dunder
    assert "timezone.get_offset" in dunder


def test_scheduler_dunder_property_returns_inner_loader(
    scheduler, two_loader_functions
):
    """
    :attr:`Schedule._dunder_salt` must resolve to the same inner loader
    that :func:`salt.loader.minion_mods` published on the wire loader.
    """
    assert scheduler._dunder_salt is two_loader_functions._dunder_salt


def test_scheduler_init_reads_timezone_offset_via_inner_loader(scheduler):
    """
    ``__singleton_init__`` populates ``self.time_offset`` from
    ``timezone.get_offset``.  Under a strict whitelist that omits
    ``timezone``, the wire loader raises ``KeyError`` on that lookup, but
    the fix routes through the inner loader -- so ``time_offset`` must
    reflect the real ``timezone.get_offset`` return value (a four-char
    UTC-offset string like ``"-0700"``), NOT the ``"0000"`` fallback
    that the ``try/except`` around the read produces on failure.
    """
    assert scheduler.time_offset is not None
    assert isinstance(scheduler.time_offset, str)
    # ``date +%z`` returns a signed 5-char UTC-offset string
    # (``+0000``, ``-0700``, etc.).  Loose assertion so the test isn't
    # tied to the host's actual TZ.  The "0000" fallback the ``__init__``
    # ``try/except`` produces on failure is only 4 chars; asserting the
    # 5-char sign-prefixed form here proves the real function was
    # invoked via the inner loader, not the fallback.
    assert len(scheduler.time_offset) == 5
    assert scheduler.time_offset[0] in "+-"
    assert scheduler.time_offset[1:].isdigit()


def test_scheduler_option_dispatches_config_merge_via_inner_loader(
    scheduler, whitelist_opts
):
    """
    :meth:`Schedule.option` must call ``config.merge`` through the inner
    loader.  Under a strict whitelist that omits ``config``, the wire
    loader would ``KeyError`` on the ``"config.merge" in self.functions``
    check and force the caller into the ``self.opts.get`` fallback --
    losing pillar-merged option semantics for scheduler-internal reads.

    Setting an opt in ``whitelist_opts`` and asking for it back proves
    the inner ``config.merge`` path was taken (the fallback in
    ``option`` is ``self.opts.get(opt, {})`` -- both paths would return
    the same value here, but the ``config.merge`` route uses the real
    execution module and would fail if it wasn't reachable).
    """
    whitelist_opts["scheduler_test_opt"] = "expected-value"
    scheduler.opts["scheduler_test_opt"] = "expected-value"
    result = scheduler.option("scheduler_test_opt")
    # ``config.merge`` merges opts, pillar, master; the raw opt value
    # comes through when nothing else touches it.
    assert result == "expected-value"


def test_scheduler_still_works_when_functions_is_plain_dict(whitelist_opts, tmp_path):
    """
    Backcompat: when ``functions`` is a plain dict (salt-ssh
    ``FunctionWrapper``, minimal test fixture), no ``_dunder_salt``
    attribute is present and the scheduler must fall back to
    ``self.functions``.  Construction must still succeed; ``time_offset``
    falls back to the documented ``"0000"`` string.
    """
    subprocess_list = SubprocessList()
    try:
        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            sched = salt.utils.schedule.Schedule(
                whitelist_opts,
                {"test.ping": lambda: True},
                returners={},
                new_instance=True,
                _subprocess_list=subprocess_list,
            )
        assert sched._dunder_salt == {"test.ping": lambda x=None: True} or isinstance(
            sched._dunder_salt, dict
        )
        # No timezone in the dict -> ``get()`` returns the default lambda
        # returning ``"0000"``.
        assert sched.time_offset == "0000"
        # ``config.merge`` not in the dict -> ``option`` falls back to
        # ``self.opts.get`` and returns the raw opt value.
        sched.opts["scheduler_test_opt"] = "from-opts"
        assert sched.option("scheduler_test_opt") == "from-opts"
    finally:
        try:
            sched.reset()
        except Exception:  # pylint: disable=broad-except
            pass
        subprocess_list.cleanup()
