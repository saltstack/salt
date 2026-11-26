"""Regression test for the ``issue_async_job`` ``*`` -> ``-L <ids>`` rewrite.

Pins the semantics introduced to bypass the minion-side resource-registry
fan-out on cluster3 (see ``agents/reports/cluster3-glob-fanout-cleanup.md``
and ``agents/reports/cluster3-fleet-death-cascade.md``).

Each ``salt '*' <fn>`` publish fans out via
``salt/minion.py::_resolve_resource_targets`` to
``dummy_resource_count × minion_count`` per-resource jobs on every
minion.  With the five test_master_overload scenarios each firing
``MWORKER_SATURATION_JOBS=50`` or ``RETURNS_BACKPRESSURE_JOBS=20``
``salt_target="*"`` publishes in a burst, a cluster3 run would queue
~500k-1M per-resource jobs per minion and starve the real-minion
returns for the rest of the suite.  The rewrite converts the default
``"*"`` to explicit ``-L <minion_ids>`` list targeting, which hits
the real minions directly and skips the registry fan-out.

Pure-python only.  Stubs ``subprocess.run`` so no docker/compose is
summoned.  Lives under ``lib/`` so the resiliency pytest.ini picks
it up.
"""

from __future__ import annotations

import subprocess

from tests.resiliency.lib.topology import Topology


class _FakeSpec:
    """Minimal stand-in for ``TopologySpec``.

    ``issue_async_job`` reads ``spec.primary_master`` and
    ``spec.minion_ids``; nothing else.
    """

    def __init__(self, n_minions: int = 5) -> None:
        self.primary_master = "c3-salt-master-1"
        self.minion_ids = tuple(f"scale-minion-{i}" for i in range(1, n_minions + 1))


def _build_topology(n_minions: int = 5) -> Topology:
    topology = Topology.__new__(Topology)
    topology.spec = _FakeSpec(n_minions)
    topology._workload_pgid = None
    return topology


class _FakeProc:
    def __init__(self, jid: str = "20261127010203040506") -> None:
        self.returncode = 0
        self.stdout = f"Executed command with job ID: {jid}\n"
        self.stderr = ""


def _patch_run(monkeypatch, captured):
    def fake_run(argv, **kwargs):
        captured.append(argv)
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_issue_async_job_rewrites_wildcard_to_list_targeting(monkeypatch):
    """Default ``salt_target='*'`` must become ``-L scale-minion-1,...``.

    This is the primary fan-out fix: on cluster3 a bare ``*`` glob
    would expand on every minion against 2000 dummy resources per
    minion and dispatch 2000 per-resource jobs per publish.
    """
    topology = _build_topology(n_minions=5)
    captured: list = []
    _patch_run(monkeypatch, captured)

    jid = topology.issue_async_job(function="test.ping")

    assert jid == "20261127010203040506"
    assert len(captured) == 1
    argv = captured[0]
    # No bare '*' anywhere in the argv.
    assert "*" not in argv, f"wildcard not rewritten: {argv!r}"
    # ``-L <ids>`` present with every real minion id.
    assert "-L" in argv, f"-L missing: {argv!r}"
    idx = argv.index("-L")
    assert argv[idx + 1] == (
        "scale-minion-1,scale-minion-2,scale-minion-3," "scale-minion-4,scale-minion-5"
    ), f"wrong minion list: {argv!r}"
    # And the function still lands after the target.
    assert "test.ping" in argv


def test_issue_async_job_keeps_explicit_tgt_type(monkeypatch):
    """Caller that passes ``tgt_type='grain'`` opts out of the rewrite.

    This escape hatch is required for the future (currently unused) case
    where a resiliency test genuinely wants grain- or pcre-targeting.
    The rewrite must only apply to the default ``salt_target='*'`` with
    no ``tgt_type`` passed.
    """
    topology = _build_topology(n_minions=3)
    captured: list = []
    _patch_run(monkeypatch, captured)

    topology.issue_async_job(
        salt_target="os:Debian",
        function="test.ping",
        tgt_type="grain",
    )

    argv = captured[0]
    # Explicit --tgt-type is honoured.
    assert "--tgt-type" in argv
    assert argv[argv.index("--tgt-type") + 1] == "grain"
    # The literal target is preserved, not rewritten.
    assert "os:Debian" in argv
    # And ``-L`` is NOT injected.
    assert "-L" not in argv, f"-L leaked into explicit-tgt_type path: {argv!r}"


def test_issue_async_job_passes_through_literal_minion_id(monkeypatch):
    """A caller passing a specific minion id (not ``*``) must not be rewritten."""
    topology = _build_topology(n_minions=5)
    captured: list = []
    _patch_run(monkeypatch, captured)

    topology.issue_async_job(
        salt_target="scale-minion-2",
        function="test.ping",
    )

    argv = captured[0]
    assert "scale-minion-2" in argv
    # No ``-L`` because the caller gave an exact glob (single minion id).
    assert "-L" not in argv


def test_issue_async_job_rewrite_handles_empty_minion_ids(monkeypatch):
    """With an empty spec.minion_ids tuple the rewrite must fall through.

    Degenerate case -- no resiliency topology ships with zero minions,
    but the guard lets the helper stay usable in unit scaffolding that
    builds a spec incrementally.
    """
    topology = _build_topology(n_minions=0)
    captured: list = []
    _patch_run(monkeypatch, captured)

    topology.issue_async_job(function="test.ping")

    argv = captured[0]
    # Fall through to the literal ``*`` target rather than emitting
    # ``-L ''`` which would mis-publish to zero minions.
    assert "*" in argv
    assert "-L" not in argv


def test_issue_async_job_rewrite_carries_args(monkeypatch):
    """Positional args to the function land after the function name."""
    topology = _build_topology(n_minions=2)
    captured: list = []
    _patch_run(monkeypatch, captured)

    topology.issue_async_job(
        function="state.sleep",
        args=["60"],
    )

    argv = captured[0]
    # Shape: [docker, exec, master, salt, --async, -L, ids, state.sleep, 60]
    assert argv[-1] == "60"
    assert argv[-2] == "state.sleep"
    assert argv[-3] == "scale-minion-1,scale-minion-2"
    assert argv[-4] == "-L"
