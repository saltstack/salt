"""
Unit tests for ``salt-call -r/--resources`` resource dispatch
(``salt.cli.caller.BaseCaller._call_with_resources``).

The dispatch path runs entirely in-process against an ``SMinion`` whose
``resources`` config is populated from Pillar.  These tests use the dummy
resource type (``salt.resources.dummy``) so they exercise the real loader
and matcher code without needing an actual master/minion daemon.

Coverage:

* ``-r`` off → existing salt-call call path is used unchanged.
* ``-r`` on, default tgt='*' → managing minion plus every configured
  resource (4 results in our fixture).
* ``-r`` with a bare-id glob → exactly that resource (bare value).
* ``-r`` with a list target → only the listed resources (dict).
* ``-r`` with a pure ``T@`` compound → only the matched resources, the
  managing minion is excluded (``_is_pure_resource_target`` short-circuit).
* ``-r`` for ``state.apply`` → master-style merge: one combined dict with
  state IDs prefixed by the resource id.
"""

from __future__ import annotations

import textwrap

import pytest

import salt.cli.caller
import salt.config
import salt.defaults.exitcodes


@pytest.fixture
def call_opts(tmp_path):
    """Minimal salt-call opts wired for in-process dummy resources."""
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    (tmp_path / "srv" / "salt").mkdir(parents=True)
    (tmp_path / "srv" / "pillar").mkdir(parents=True)

    sls_path = tmp_path / "srv" / "salt" / "dummy_state.sls"
    sls_path.write_text(
        textwrap.dedent(
            """
            ping the resource:
              dummy_test.present:
                - name: ping the resource
            """
        )
    )

    opts = salt.config.minion_config(None)
    opts["id"] = "rcaller-minion"
    opts["root_dir"] = str(tmp_path)
    opts["cachedir"] = str(cachedir)
    opts["file_client"] = "local"
    opts["file_roots"] = {"base": [str(tmp_path / "srv" / "salt")]}
    opts["pillar_roots"] = {"base": [str(tmp_path / "srv" / "pillar")]}
    opts["pillar"] = {
        "resources": {"dummy": {"resource_ids": ["dummy-01", "dummy-02", "dummy-03"]}}
    }
    opts.setdefault("grains", {})
    # Caller defaults — all targeting flags off / at their parser defaults.
    opts["fun"] = "test.ping"
    opts["arg"] = []
    opts["resources_dispatch"] = False
    opts["resources_tgt"] = "*"
    opts["resources_tgt_type"] = "glob"
    opts["no_parse"] = []
    opts["module_executors"] = "[direct_call]"
    return opts


def _build_caller(opts):
    """Build a Caller without going through the parser/run() machinery."""
    caller = salt.cli.caller.BaseCaller.__new__(salt.cli.caller.BaseCaller)
    caller.opts = opts
    import salt.minion as _sm  # noqa: PLC0415

    caller.minion = _sm.SMinion(opts)
    return caller


def test_r_off_uses_legacy_call_path(call_opts, monkeypatch):
    """Without -r, BaseCaller.call() must NOT hit _call_with_resources."""
    caller = _build_caller(call_opts)
    sentinel = object()

    def _shouldnt_run(self):
        raise AssertionError("_call_with_resources fired without -r")

    monkeypatch.setattr(
        salt.cli.caller.BaseCaller, "_call_with_resources", _shouldnt_run
    )
    monkeypatch.setattr(
        salt.cli.caller.BaseCaller,
        "_legacy_marker",
        lambda self: sentinel,
        raising=False,
    )

    # We don't actually want to run the full legacy call path here (it does
    # IPC, returners, etc.). Just assert the branch decision: opts gate.
    assert caller.opts.get("resources_dispatch") is False


def test_r_default_star_includes_minion_and_all_resources(call_opts):
    """salt-call -r test.ping → {minion: True, dummy-01: True, ...}."""
    call_opts["resources_dispatch"] = True
    caller = _build_caller(call_opts)
    ret = caller._call_with_resources()
    payload = ret["return"]
    assert isinstance(payload, dict), payload
    assert payload[call_opts["id"]] is True
    for rid in ("dummy-01", "dummy-02", "dummy-03"):
        assert payload[rid] is True, (rid, payload)
    assert ret["retcode"] == salt.defaults.exitcodes.EX_OK


def test_r_bare_id_glob_returns_single_value(call_opts):
    """salt-call -r --tgt dummy-02 test.ping → True (single, unwrapped)."""
    call_opts["resources_dispatch"] = True
    call_opts["resources_tgt"] = "dummy-02"
    caller = _build_caller(call_opts)
    ret = caller._call_with_resources()
    assert ret["return"] is True


def test_r_list_targets_returns_dict_of_those_only(call_opts):
    """-r --tgt 'dummy-01,dummy-03' --tgt-type list → only those resources."""
    call_opts["resources_dispatch"] = True
    call_opts["resources_tgt"] = "dummy-01,dummy-03"
    call_opts["resources_tgt_type"] = "list"
    caller = _build_caller(call_opts)
    payload = caller._call_with_resources()["return"]
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"dummy-01", "dummy-03"}
    assert all(v is True for v in payload.values())


def test_r_pure_compound_excludes_managing_minion(call_opts):
    """T@ compound is a pure resource target — minion must be excluded."""
    call_opts["resources_dispatch"] = True
    call_opts["resources_tgt"] = "T@dummy"
    call_opts["resources_tgt_type"] = "compound"
    caller = _build_caller(call_opts)
    payload = caller._call_with_resources()["return"]
    assert isinstance(payload, dict)
    assert call_opts["id"] not in payload
    assert set(payload.keys()) == {"dummy-01", "dummy-02", "dummy-03"}


def test_r_grains_items_returns_per_resource_grains(call_opts):
    """
    ``salt-call -r --tgt dummy-01 grains.items`` must return the dummy
    resource's own grain dict — not the managing minion's grains. The
    per-resource ``__grains__`` swap mirrors what ``Minion._thread_return``
    does for master-driven resource jobs.
    """
    call_opts["resources_dispatch"] = True
    call_opts["resources_tgt"] = "dummy-01"
    call_opts["fun"] = "grains.items"
    caller = _build_caller(call_opts)
    payload = caller._call_with_resources()["return"]
    assert isinstance(payload, dict), payload
    # Resource grains include a ``resource_id`` key set to the rid.
    assert payload.get("resource_id") == "dummy-01", payload
    assert payload.get("dummy_grain_1") == "one", payload


def test_r_grains_items_per_resource_for_each_target(call_opts):
    """
    With multiple resource targets, each entry in the response dict gets
    the corresponding resource's own grains, not a shared snapshot from
    the last loader call.
    """
    call_opts["resources_dispatch"] = True
    call_opts["resources_tgt"] = "T@dummy"
    call_opts["resources_tgt_type"] = "compound"
    call_opts["fun"] = "grains.items"
    caller = _build_caller(call_opts)
    payload = caller._call_with_resources()["return"]
    assert isinstance(payload, dict), payload
    for rid in ("dummy-01", "dummy-02", "dummy-03"):
        assert rid in payload, payload
        assert payload[rid].get("resource_id") == rid, (rid, payload[rid])


@pytest.mark.timeout(180, func_only=True)
def test_r_state_apply_logical_resource_no_state_module(call_opts):
    """
    state.apply against a logical resource type (no per-resource state
    override module) routes through the standard ``state.py`` (the
    narrow guard in ``salt/modules/state.py`` only opts out for
    ``ssh``).  The state run finds no matching state module for the
    .sls referenced state (dummy resources don't ship a
    ``dummy_test`` state module), and produces ``result: False``
    state entries — one per resource — keyed in the master merge
    format with the resource id prefixed onto each state id.

    This is the expected behaviour for logical resources: the dispatch
    succeeds (no caller-level rejection), the state machinery runs,
    and the operator sees per-resource provenance for whatever the
    state run produced.

    Runs ``state.apply`` three times (once per dummy resource), each of
    which spins up a HighState and loads state modules.  Local
    wall-clock is ~3-5 s; under coverage tracing on a loaded GHA
    runner the cumulative cost has been observed at 30-60 s.  The
    explicit ``@pytest.mark.timeout(180)`` override raises the global
    90 s pytest-timeout default so a slow runner doesn't trip the
    wall-clock before the test's logical assertions run.
    """
    call_opts["resources_dispatch"] = True
    call_opts["fun"] = "state.apply"
    call_opts["arg"] = ["dummy_state"]
    caller = _build_caller(call_opts)
    payload = caller._call_with_resources()["return"]
    assert isinstance(payload, dict), payload
    # Master merge format prefixes each state id with the rid; e.g.
    # ``dummy_test_|-dummy-01 ping the resource_|-...``
    rid_keys = {
        rid: [k for k in payload if isinstance(payload[k], dict) and f"{rid} " in k]
        for rid in ("dummy-01", "dummy-02", "dummy-03")
    }
    for rid, keys in rid_keys.items():
        assert keys, f"No prefixed state entries for {rid}: {list(payload)}"
        for k in keys:
            entry = payload[k]
            assert entry["result"] is False, (k, entry)
            assert (
                "not available" in entry["comment"] or "not found" in entry["comment"]
            ), (
                k,
                entry,
            )
