"""Regression tests for ``test_salt_ops._parse_async_jid`` and the
master-iteration dispatch helper used by
``test_saltop_kill_job_mid_flight``.

Context: CI run 45718582847 (dwoz/salt) failed on
``resiliency-test (multimaster-failover, fast)`` with::

    Failed: saltop_kill_job_mid_flight: could not determine state.sleep
    JID (neither --async output nor jobs.list_jobs returned one)

Two root-cause bugs:

1. ``_parse_async_jid`` was ``json.loads``-ing ``salt --async`` output.
   ``salt --async`` ignores ``--out=json`` and always prints the plain
   text line ``"Executed command with job ID: <jid>"`` (see
   ``salt/cli/salt.py``), so the JSON path returned ``""`` on every
   topology.  Only the ``jobs.list_jobs`` fallback was ever working.

2. The test hard-coded ``topology.spec.primary_master`` (``mm-salt-
   master-a``) for both dispatch and the fallback scrape.  On
   ``master_type: failover`` topologies (currently
   ``multimaster-failover`` and ``cluster5``) ``master_shuffle: True``
   means the minion can attach to any peer; dispatching from a master
   with no attached minions yields ``jid=0`` and no job-cache entry on
   that master.  The fallback scrape then returns ``""`` from the
   wrong master's cache.

The fix parses the plain-text format and iterates ``spec.masters``
until a master with the attached minion responds.  These unit tests
pin both behaviors.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[4]
TEST_SALT_OPS_PATH = REPO_ROOT / "tests" / "resiliency" / "test_salt_ops.py"


@pytest.fixture(scope="module")
def ops():
    """Import ``tests/resiliency/test_salt_ops.py`` as a module WITHOUT
    letting pytest collect its tests (which require the docker-backed
    ``topology`` fixture).
    """
    spec = importlib.util.spec_from_file_location(
        "resiliency_test_salt_ops", TEST_SALT_OPS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# _parse_async_jid
# ---------------------------------------------------------------------------


def _proc(stdout: str) -> SimpleNamespace:
    """subprocess.CompletedProcess-like stub."""
    return SimpleNamespace(stdout=stdout, stderr="", returncode=0)


def test_parse_async_jid_plain_text(ops):
    """``salt --async`` prints plain text, not JSON."""
    jid = ops._parse_async_jid(
        _proc("Executed command with job ID: 20261125234410123456\n")
    )
    assert jid == "20261125234410123456"


def test_parse_async_jid_treats_zero_as_missing(ops):
    """``cmd_async`` returns 0 on "No minions matched" -- not a real jid."""
    jid = ops._parse_async_jid(_proc("Executed command with job ID: 0\n"))
    assert jid == ""


def test_parse_async_jid_empty_stdout(ops):
    assert ops._parse_async_jid(_proc("")) == ""


def test_parse_async_jid_unrelated_text(ops):
    """Any output that doesn't contain the expected line → "".

    Guards against swallowing noise from a failed docker exec, salt
    stacktrace, etc.
    """
    assert ops._parse_async_jid(_proc("Traceback (most recent call last):\n")) == ""


def test_parse_async_jid_no_minions_matched_banner(ops):
    """On a master with no attached minions, salt CLI prints the
    ``No minions matched the target.`` banner AND the jid=0 line.
    Parser must still return ""."""
    stdout = (
        "No minions matched the target. No command was sent, no jid was assigned.\n"
        "Executed command with job ID: 0\n"
    )
    assert ops._parse_async_jid(_proc(stdout)) == ""


def test_parse_async_jid_still_rejects_bare_json(ops):
    """Legacy JSON path is dead; pass JSON-shaped stdout through and
    confirm parser doesn't accidentally match a json field named ``jid``.
    """
    assert ops._parse_async_jid(_proc('{"jid": "20261125234410123456"}')) == ""


# ---------------------------------------------------------------------------
# _dispatch_state_sleep_jid
# ---------------------------------------------------------------------------


class _FakeTopology:
    """Minimal topology stub that records ``.exec`` calls and returns
    canned stdout per container.
    """

    def __init__(self, stdout_by_master: dict[str, str]):
        self._stdout_by_master = stdout_by_master
        self.calls: list[str] = []

    def exec(self, container, *cmd, check=True, timeout=None):  # noqa: ARG002
        self.calls.append(container)
        stdout = self._stdout_by_master.get(container, "")
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)


def test_dispatch_state_sleep_jid_first_master_wins(ops):
    """Single/hothot/cluster topologies: every master works; the first
    one dispatched returns a jid and the helper stops immediately."""
    topo = _FakeTopology(
        {
            "master-a": "Executed command with job ID: 20261125230000000001\n",
            "master-b": "Executed command with job ID: 20261125230000000002\n",
        }
    )
    jid, master = ops._dispatch_state_sleep_jid(topo, ["master-a", "master-b"])
    assert jid == "20261125230000000001"
    assert master == "master-a"
    # Didn't bother the second master.
    assert topo.calls == ["master-a"]


def test_dispatch_state_sleep_jid_falls_through_to_peer(ops):
    """mm-failover with minion on master-b: master-a prints jid=0, the
    helper falls through and succeeds on master-b."""
    topo = _FakeTopology(
        {
            "master-a": (
                "No minions matched the target. No command was sent, "
                "no jid was assigned.\n"
                "Executed command with job ID: 0\n"
            ),
            "master-b": "Executed command with job ID: 20261125230000000099\n",
        }
    )
    jid, master = ops._dispatch_state_sleep_jid(topo, ["master-a", "master-b"])
    assert jid == "20261125230000000099"
    assert master == "master-b"
    assert topo.calls == ["master-a", "master-b"]


def test_dispatch_state_sleep_jid_all_masters_empty(ops):
    """No master has an attached minion → ("", "")."""
    topo = _FakeTopology(
        {
            "master-a": "Executed command with job ID: 0\n",
            "master-b": "Executed command with job ID: 0\n",
        }
    )
    jid, master = ops._dispatch_state_sleep_jid(topo, ["master-a", "master-b"])
    assert jid == ""
    assert master == ""
    # Tried every master before giving up.
    assert topo.calls == ["master-a", "master-b"]


def test_dispatch_state_sleep_jid_exec_raises(ops):
    """Transient docker-exec error on master-a must not short-circuit
    the iteration: the helper has to try master-b."""
    topo = MagicMock()

    def _exec(container, *cmd, check=True, timeout=None):  # noqa: ARG001
        if container == "master-a":
            raise RuntimeError("docker exec died")
        return SimpleNamespace(
            stdout="Executed command with job ID: 20261125230000000050\n",
            stderr="",
            returncode=0,
        )

    topo.exec.side_effect = _exec
    jid, master = ops._dispatch_state_sleep_jid(topo, ["master-a", "master-b"])
    assert jid == "20261125230000000050"
    assert master == "master-b"
