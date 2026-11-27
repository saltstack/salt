"""Regression tests for ``Topology._parse_ping_stdout`` / ``salt_ping_all``.

Pins two semantics discovered via CI 45869625842's cluster3-fast run
(see ``agents/reports/cluster3-post-ping-fix-recovery.md``):

* **Partial-output salvage on subprocess timeout.**  The ``salt --out=json
  -L <ids> test.ping`` stream is incremental: by the time the subprocess
  wall-clock kills the CLI, several ``{"minion-N": true}`` objects have
  typically already been flushed.  The old ``return {}`` on
  ``TimeoutExpired`` discarded that salvage, and the ``assert_reconnect``
  union across 3 masters came up empty-handed even when enough minions
  had answered to close the set.

* **String values are negative, not truthy.**  Salt emits
  ``{"scale-minion-1": "Minion did not return. [No response]..."}`` for
  unreachable minions in an otherwise-successful call.  The old
  ``bool(v)`` coerced that string to ``True`` and misclassified a
  jammed minion (455k-file job queue backlog) as reachable.  Only
  literal ``True`` counts as a successful ping.

Pure-python only; no docker / subprocess invocation.
"""

from __future__ import annotations

import subprocess

from tests.resiliency.lib.topology import Topology


class _FakeSpec:
    """Minimal spec stand-in.  ``salt_ping_all`` reads ``minion_ids`` only."""

    def __init__(self, n_minions: int = 5) -> None:
        self.minion_ids = tuple(f"scale-minion-{i}" for i in range(1, n_minions + 1))


def _build_topology(n_minions: int = 5) -> Topology:
    topology = Topology.__new__(Topology)
    topology.spec = _FakeSpec(n_minions)
    topology._workload_pgid = None
    return topology


# ---------------------------------------------------------------------------
# _parse_ping_stdout: happy paths
# ---------------------------------------------------------------------------


def test_parse_single_dict_form():
    """``{"a": true, "b": true}`` -> ``{"a": True, "b": True}``."""
    out = Topology._parse_ping_stdout('{"a": true, "b": true}')
    assert out == {"a": True, "b": True}


def test_parse_streaming_form():
    """Concatenated per-minion dicts parse to the union."""
    stdout = (
        '{\n    "scale-minion-1": true\n}\n'
        '{\n    "scale-minion-2": true\n}\n'
        '{\n    "scale-minion-3": true\n}\n'
    )
    out = Topology._parse_ping_stdout(stdout)
    assert out == {
        "scale-minion-1": True,
        "scale-minion-2": True,
        "scale-minion-3": True,
    }


def test_parse_empty_stdout():
    assert Topology._parse_ping_stdout("") == {}
    assert Topology._parse_ping_stdout("   \n\t") == {}


# ---------------------------------------------------------------------------
# _parse_ping_stdout: "Minion did not return" must be False, not True
# ---------------------------------------------------------------------------


_MISSING_STR = (
    "Minion did not return. [No response]\n"
    "The minions may not have all finished running and any remaining "
    "minions will return upon completion. To look up the return data "
    "for this job later, run the following command:\n\nsalt-run "
    "jobs.lookup_jid 20261127010203040506"
)


def test_parse_missing_minion_string_is_false_single_dict():
    """In the single-dict shape, a string value is a failure, not True.

    ``bool(v)`` would coerce this non-empty string to ``True`` -- the
    exact regression that let cluster3-fast report every minion as
    reachable while scale-minion-1 was buried under its queue backlog.
    """
    stdout = (
        '{"scale-minion-1": '
        + '"Minion did not return. [No response]"'
        + ', "scale-minion-2": true}'
    )
    out = Topology._parse_ping_stdout(stdout)
    assert out == {"scale-minion-1": False, "scale-minion-2": True}


def test_parse_missing_minion_string_is_false_streaming():
    """Streaming form: same semantics."""
    stdout = (
        '{"scale-minion-1": "' + _MISSING_STR.replace("\n", "\\n") + '"}\n'
        '{"scale-minion-2": true}\n'
    )
    out = Topology._parse_ping_stdout(stdout)
    assert out == {"scale-minion-1": False, "scale-minion-2": True}


def test_parse_false_values_remain_false():
    """``false`` is not ``True`` either; don't accidentally flip it."""
    stdout = '{"a": false, "b": true}'
    assert Topology._parse_ping_stdout(stdout) == {"a": False, "b": True}


def test_parse_non_dict_object_is_ignored():
    """A top-level list / number / string must not crash or match."""
    assert Topology._parse_ping_stdout("[1, 2, 3]") == {}
    # A bare number parses as JSON but isn't a dict; fall through to
    # the streaming path which also gives up on the non-object.
    assert Topology._parse_ping_stdout("42") == {}


# ---------------------------------------------------------------------------
# _parse_ping_stdout: truncated / partial streams
# ---------------------------------------------------------------------------


def test_parse_truncated_mid_object_preserves_prior_objects():
    """Subprocess timeout salvage: trailing object is cut off mid-value.

    The decoder stops at the parse error and returns whatever already
    decoded.  Without this, ``assert_reconnect`` would come up empty on
    every sweep that hit the 135s subprocess-timeout wall even when
    multiple minions had already answered True.
    """
    stdout = (
        '{"scale-minion-3": true}\n'
        '{"scale-minion-5": true}\n'
        '{"scale-minion-1": "Minion did not return. [No respons'
    )
    out = Topology._parse_ping_stdout(stdout)
    # The two complete objects decode; the truncated tail is dropped.
    assert out == {"scale-minion-3": True, "scale-minion-5": True}


def test_parse_realworld_cluster3_partial_output():
    """Verbatim 200-byte partial from CI 45869625842 cluster3-fast log.

    Reflects the real failure mode: master's stdout buffer flushed
    scale-minion-4 as True and then started emitting the "did not
    return" error for scale-minion-1 just as the subprocess timeout
    fired.  Salvage must recover minion-4; minion-1 (truncated string
    value) must NOT be classified as True.
    """
    # Byte-for-byte reproduction of line 1181 of job.log (first sweep
    # of test_clock_minion_fwd_60s).  The error value is truncated
    # mid-string because the subprocess was killed before emitting the
    # closing ``"}``.
    stdout = (
        '{\n    "scale-minion-4": true\n}\n'
        '{\n    "scale-minion-1": '
        '"Minion did not return. [No response]\\n'
        "The minions may not have all finished running and any remaining "
        "minions will return upon completion. To lo"
    )
    out = Topology._parse_ping_stdout(stdout)
    # minion-4 recovered; minion-1 did not (truncated string, decoder
    # stops at parse error -> no entry for minion-1 at all).
    assert out == {"scale-minion-4": True}


# ---------------------------------------------------------------------------
# salt_ping_all: TimeoutExpired path salvages partial stdout
# ---------------------------------------------------------------------------


def _patch_run_timeout(monkeypatch, *, output: bytes = b"", stderr: bytes = b""):
    """Make ``Topology._run`` raise ``TimeoutExpired`` with the given buffers.

    ``TimeoutExpired.output`` / ``.stderr`` are always ``bytes`` even
    when ``text=True`` was passed -- quirk of ``Popen.communicate``'s
    timeout branch -- so the test fixtures match the real shape.
    """

    def fake_run(self, argv, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=argv, timeout=1, output=output, stderr=stderr
        )

    monkeypatch.setattr(Topology, "_run", fake_run, raising=True)


def test_salt_ping_all_timeout_salvages_partial_output(monkeypatch):
    """TimeoutExpired must salvage any decoded minion responses.

    Previously ``return {}`` discarded a partial stream that often
    already contained several ``{"minion-N": true}`` objects.  The
    first-sweep union across 3 masters in cluster3-fast CI 45869625842
    would have been minion-4 ∪ minion-3/5 ∪ ∅ == {-3, -4, -5}, a
    non-empty partial coverage; the ``return {}`` turned that into
    ∅ ∪ ∅ ∪ ∅ == ∅ and failed the sweep.
    """
    topology = _build_topology(n_minions=5)
    partial = (
        b'{\n    "scale-minion-3": true\n}\n'
        b'{\n    "scale-minion-5": true\n}\n'
        b'{\n    "scale-minion-1": "Minion did not return. [No respons'
    )
    _patch_run_timeout(monkeypatch, output=partial)

    out = topology.salt_ping_all(master="c3-salt-master-1", timeout=15)

    # Recovered what the CLI already emitted before the kill.
    assert out == {"scale-minion-3": True, "scale-minion-5": True}


def test_salt_ping_all_timeout_with_empty_output(monkeypatch):
    """TimeoutExpired with no buffered output must still return ``{}``."""
    topology = _build_topology()
    _patch_run_timeout(monkeypatch, output=b"")
    assert topology.salt_ping_all(master="c3-salt-master-1", timeout=15) == {}


def test_salt_ping_all_timeout_with_none_output(monkeypatch):
    """TimeoutExpired.output can be ``None`` (no stdin written).

    Reproduces the sandbox behaviour: ``subprocess.run(['sleep', '5'],
    timeout=1, capture_output=True, text=True)`` on a timeout gives
    ``exc.output is None``, not ``b""``.  The salvage path must tolerate
    ``None`` without raising ``AttributeError``.
    """
    topology = _build_topology()
    _patch_run_timeout(monkeypatch, output=None)  # type: ignore[arg-type]
    assert topology.salt_ping_all(master="c3-salt-master-1", timeout=15) == {}


# ---------------------------------------------------------------------------
# salt_ping_all: non-timeout rc!=0 still returns {} (no salvage path)
# ---------------------------------------------------------------------------


class _FakeProcBad:
    def __init__(self) -> None:
        self.returncode = 1
        self.stdout = ""
        self.stderr = "ERROR: Minion could not be contacted"


def test_salt_ping_all_rc_nonzero_empty_stdout_returns_empty(monkeypatch):
    """rc!=0 with no stdout -> ``{}`` (publish refused, master down)."""
    topology = _build_topology()

    def fake_run(self, argv, **kwargs):
        return _FakeProcBad()

    monkeypatch.setattr(Topology, "_run", fake_run, raising=True)
    assert topology.salt_ping_all(master="c3-salt-master-1", timeout=15) == {}
