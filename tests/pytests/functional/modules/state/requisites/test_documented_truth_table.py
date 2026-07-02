"""
Documented requisites truth-table tests.

Each test case here is a cell of the truth table that appears in
``doc/ref/states/requisites.rst`` under "Requisites truth table". The cells
exercise: ``require``, ``require_any``, ``watch``, ``onchanges``,
``onchanges_any``, ``onfail``, ``onfail_any``, ``onfail_all`` and ``prereq``.

If the documented behavior changes (a state runs that didn't before, or stops
running when it used to), one of these tests fails and the documentation must
be updated to match. That is the point: documentation and behavior stay in
lockstep.
"""

import pytest

from . import normalize_ret

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.core_test,
]


# --- helpers --------------------------------------------------------------


def _apply(state, state_tree, sls):
    with pytest.helpers.temp_file("doc_truth.sls", sls, state_tree):
        ret = state.sls("doc_truth")
    return normalize_ret(ret.raw)


def _result(ret, key):
    assert key in ret, f"missing state {key!r} in return {sorted(ret)}"
    return ret[key]


# --- require --------------------------------------------------------------


def test_require_target_succeeded(state, state_tree):
    """require: target succeeded -> dependent runs."""
    sls = """
    target:
      cmd.run:
        - name: echo target-ok

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - require:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    assert _result(ret, "cmd_|-target_|-echo target-ok_|-run")["result"] is True
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


def test_require_target_failed(state, state_tree):
    """require: target failed -> dependent is skipped (result False)."""
    sls = """
    target:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo should-not-run
        - require:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    assert _result(ret, "cmd_|-target_|-false_|-run")["result"] is False
    dep = _result(ret, "cmd_|-dependent_|-echo should-not-run_|-run")
    assert dep["result"] is False
    assert dep["changes"] is False


# --- require_any ----------------------------------------------------------


def test_require_any_one_succeeds(state, state_tree):
    """require_any: at least one target succeeded -> dependent runs."""
    sls = """
    good:
      cmd.run:
        - name: echo good

    bad:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - require_any:
          - cmd: good
          - cmd: bad
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


def test_require_any_all_fail(state, state_tree):
    """require_any: every target failed -> dependent is skipped."""
    sls = """
    bad1:
      cmd.run:
        - name: 'false'

    bad2:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo should-not-run
        - require_any:
          - cmd: bad1
          - cmd: bad2
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo should-not-run_|-run")
    assert dep["result"] is False
    assert dep["changes"] is False


# --- onchanges ------------------------------------------------------------


def test_onchanges_target_has_changes(state, state_tree):
    """onchanges: target succeeded with changes -> dependent runs."""
    sls = """
    target:
      cmd.run:
        - name: echo changing

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - onchanges:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


def test_onchanges_target_failed(state, state_tree):
    """onchanges: target failed -> dependent does not run, result True."""
    sls = """
    target:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo should-not-run
        - onchanges:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo should-not-run_|-run")
    assert dep["result"] is True
    assert dep["changes"] is False


# --- onchanges_any --------------------------------------------------------


def test_onchanges_any_one_has_changes(state, state_tree):
    """onchanges_any: any target with changes -> dependent runs."""
    sls = """
    good_no_change:
      test.succeed_without_changes

    target_with_change:
      cmd.run:
        - name: echo changed

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - onchanges_any:
          - test: good_no_change
          - cmd: target_with_change
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


# --- onfail / onfail_any / onfail_all ------------------------------------


def test_onfail_target_failed(state, state_tree):
    """onfail: target failed -> dependent runs."""
    sls = """
    target:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - onfail:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


def test_onfail_target_succeeded(state, state_tree):
    """onfail: target succeeded -> dependent does not run, result True."""
    sls = """
    target:
      cmd.run:
        - name: echo ok

    dependent:
      cmd.run:
        - name: echo should-not-run
        - onfail:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo should-not-run_|-run")
    assert dep["result"] is True
    assert dep["changes"] is False


def test_onfail_any_one_failed(state, state_tree):
    """onfail_any: at least one failed -> dependent runs (OR semantics)."""
    sls = """
    good:
      cmd.run:
        - name: echo ok

    bad:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - onfail_any:
          - cmd: good
          - cmd: bad
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


def test_onfail_all_requires_all_failed(state, state_tree):
    """onfail_all: only one failed -> dependent does not run (AND semantics)."""
    sls = """
    good:
      cmd.run:
        - name: echo ok

    bad:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo should-not-run
        - onfail_all:
          - cmd: good
          - cmd: bad
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo should-not-run_|-run")
    assert dep["changes"] is False


def test_onfail_all_all_failed_runs(state, state_tree):
    """onfail_all: all targets failed -> dependent runs."""
    sls = """
    bad1:
      cmd.run:
        - name: 'false'

    bad2:
      cmd.run:
        - name: 'false'

    dependent:
      cmd.run:
        - name: echo dependent-ran
        - onfail_all:
          - cmd: bad1
          - cmd: bad2
    """
    ret = _apply(state, state_tree, sls)
    dep = _result(ret, "cmd_|-dependent_|-echo dependent-ran_|-run")
    assert dep["result"] is True
    assert dep["changes"] is True


# --- watch ----------------------------------------------------------------


def test_watch_target_failed_skips_watcher(state, state_tree):
    """watch: target failed -> watcher does not run, result False."""
    sls = """
    target:
      cmd.run:
        - name: 'false'

    watcher:
      cmd.run:
        - name: echo should-not-run
        - watch:
          - cmd: target
    """
    ret = _apply(state, state_tree, sls)
    w = _result(ret, "cmd_|-watcher_|-echo should-not-run_|-run")
    assert w["result"] is False
    assert w["changes"] is False
