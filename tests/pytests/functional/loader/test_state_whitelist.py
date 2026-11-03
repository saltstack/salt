"""
Functional tests for the ``whitelist_state_modules`` minion option.

Companion to :mod:`tests.pytests.unit.loader.test_state_whitelist`.  These
tests wire up a real state LazyLoader (no mocks) and exercise the actual
load path -- forcing a state module to load and confirming the gate.
"""

import textwrap

import pytest

import salt.exceptions
import salt.loader
import salt.state


@pytest.fixture
def wl_opts(minion_opts, tmp_path):
    """Minion opts with ``whitelist_state_modules`` restricting the state loader."""
    opts = minion_opts.copy()
    opts["whitelist_state_modules"] = ["test", "file"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    return opts


@pytest.fixture
def wl_state_loader(wl_opts):
    """A real state loader built with ``whitelist_state_modules`` in effect."""
    minion_mods = salt.loader.minion_mods(wl_opts)
    utils = salt.loader.utils(wl_opts)
    serializers = salt.loader.serializers(wl_opts)
    return salt.loader.states(wl_opts, minion_mods, utils, serializers)


def test_whitelisted_state_resolves(wl_state_loader):
    """
    A state module whose name is on ``whitelist_state_modules`` must
    resolve normally via dict-style access.
    """
    assert "file.managed" in wl_state_loader
    assert callable(wl_state_loader["file.managed"])


def test_non_whitelisted_state_raises_keyerror(wl_state_loader):
    """
    A state module whose name is NOT on ``whitelist_state_modules`` must
    fail to load; dict-style access raises ``KeyError`` and the loader's
    contains-check returns False.
    """
    assert "cmd.run" not in wl_state_loader
    with pytest.raises(KeyError):
        _ = wl_state_loader["cmd.run"]


def test_compile_high_data_of_whitelisted_state_succeeds(wl_opts, tmp_path):
    """
    An SLS whose highstate declares a whitelisted state module must
    compile without errors.
    """
    st = salt.state.State(wl_opts)
    high = {
        "example_id": {
            "test": [{"name": "example"}, "succeed_without_changes"],
            "__sls__": "example",
            "__env__": "base",
        }
    }
    chunks, errors = st.compile_high_data(high)
    assert errors == []
    assert len(chunks) == 1
    assert chunks[0]["state"] == "test"


def test_call_high_of_non_whitelisted_state_reports_not_found(wl_opts):
    """
    An SLS whose highstate declares a NON-whitelisted state module must
    fail at ``call_high`` with a ``"Specified state '<mod>.<fun>' was
    not found"`` result for that chunk -- the state doesn't silently
    execute.
    """
    st = salt.state.State(wl_opts)
    high = {
        "example_id": {
            "grafana_datasource": [{"name": "example"}, "present"],
            "__sls__": "example",
            "__env__": "base",
        }
    }
    ret = st.call_high(high)
    # call_high returns a dict keyed by state chunk id, each with
    # result/name/changes/comment.  A non-loadable state surfaces as
    # ``result: False`` with a "not found" comment.
    assert isinstance(ret, dict), ret
    chunk_id = next(iter(ret))
    chunk = ret[chunk_id]
    assert chunk["result"] is False
    assert (
        "grafana_datasource" in chunk["comment"]
        or "not found" in chunk["comment"].lower()
    )
    # Confirm the state module wasn't magically resolved -- no changes.
    assert not chunk["changes"]


def test_render_sls_string_with_whitelisted_state(wl_opts):
    """
    A rendered SLS string that declares a whitelisted state must compile
    into a high-data dict without errors.  Uses ``call_template_str`` to
    exercise the full render + compile pipeline (jinja renderer + state
    loader lookup).
    """
    st = salt.state.State(wl_opts)
    template = textwrap.dedent(
        """\
        probe:
          test.succeed_without_changes:
            - name: example
        """
    )
    ret = st.call_template_str(template)
    assert isinstance(ret, dict), ret
    chunk_id = next(iter(ret))
    assert ret[chunk_id]["result"] is True


def test_render_sls_string_with_non_whitelisted_state_fails_compile(wl_opts):
    """
    A rendered SLS string that references a NON-whitelisted state
    module must fail compile (``verify_data`` reports
    ``State '<mod>.<fun>' was not found in SLS ...``) instead of
    silently executing.
    """
    st = salt.state.State(wl_opts)
    template = textwrap.dedent(
        """\
        probe:
          grafana_datasource.present:
            - name: example
        """
    )
    ret = st.call_template_str(template)
    # Runtime lookup failure surfaces as a dict-of-chunks with
    # ``result: False`` and a "not found" comment, rather than silently
    # executing.
    assert isinstance(ret, dict), ret
    chunk_id = next(iter(ret))
    chunk = ret[chunk_id]
    assert chunk["result"] is False
    assert (
        "grafana_datasource" in chunk["comment"]
        or "not found" in chunk["comment"].lower()
    )
    assert not chunk["changes"]


def test_backcompat_unset_opt_loads_all_states(minion_opts, tmp_path):
    """
    With the opt unset (default), every discoverable state module must
    still be loadable -- no regression for the un-hardened case.
    """
    opts = minion_opts.copy()
    opts.pop("whitelist_state_modules", None)
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    minion_mods = salt.loader.minion_mods(opts)
    utils = salt.loader.utils(opts)
    serializers = salt.loader.serializers(opts)
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    # Both should resolve.
    assert callable(loader["file.managed"])
    assert callable(loader["cmd.run"])


def test_whitelist_modules_does_not_gate_state_modules(minion_opts, tmp_path):
    """
    Cross-contamination check: setting ``whitelist_modules`` (the exec-
    loader gate) must not affect state-module loading.  ``cmd`` state
    must still load when only ``whitelist_modules`` is scoped down.
    """
    opts = minion_opts.copy()
    opts["whitelist_modules"] = ["test"]
    opts.pop("whitelist_state_modules", None)
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    minion_mods = salt.loader.minion_mods(opts)
    utils = salt.loader.utils(opts)
    serializers = salt.loader.serializers(opts)
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    # ``cmd`` state loads even though ``cmd`` exec module is
    # whitelist-blocked.
    assert callable(loader["cmd.run"])
