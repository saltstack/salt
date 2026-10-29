"""
Regression tests for the RPM ``%pre minion`` / ``%post minion`` /
``%posttrans minion`` scriptlets.

Two long-standing packaging bugs are guarded here.

1. Issue #69605: The ``%pre minion`` scriptlet unconditionally stops the
   running minion service on upgrade so the ownership-restoration chowns
   in ``%post`` / ``%posttrans`` don't race a live process. The historical
   ``%post`` / ``%posttrans`` scriptlets only called
   ``systemctl try-restart salt-minion.service``, which by design is a
   no-op when the unit is inactive. The combination silently broke RPM
   upgrades on every EL host: the minion was stopped by ``%pre`` and
   never started again, leaving operators with no automatic recovery
   short of logging into each host.

2. Issue #69656: When the upgrade is driven by the *running minion* (via
   ``pkg.installed`` from a state run), the blocking ``systemctl stop``
   in ``%pre`` deadlocks. The stop waits for every process in the
   ``KillMode=mixed`` cgroup to exit, including the salt worker running
   the state, which is waiting on ``dnf``, which is waiting on ``%pre``.
   After ``TimeoutStopSec`` systemd SIGKILLs the whole cgroup, the state
   return is lost, and orchestrated minion upgrades cannot work at all.
   ``%pre minion`` now detects the self-upgrade case (by walking the
   scriptlet's parent process chain) and skips the stop; ``%post`` and
   ``%posttrans`` then honour a ``.salt-minion-self-upgrade`` marker to
   leave the still-running minion alone. The FAQ's ``cmd.run bg: True``
   pattern performs the actual restart in a detached child after the
   state returns.

This file is a *static audit* of ``pkg/rpm/salt.spec`` plus a bash-level
functional test of the ``_salt_minion_upgrade_from_running_minion``
helper. Both run in ordinary unit-test CI - no rpmbuild, no systemd, no
fixtures - so the guard kicks in on every PR rather than only in the
packaging matrix.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_FILE = REPO_ROOT / "pkg" / "rpm" / "salt.spec"


def _extract_scriptlet(spec_text, directive):
    """
    Return the body of an RPM scriptlet ``directive`` (e.g. ``%pre minion``)
    up to the next scriptlet directive or end of file.
    """
    # Match the directive at the start of a line, then capture until the
    # next directive that begins at column 0.
    pattern = re.compile(
        rf"^{re.escape(directive)}\s*\n(.*?)(?=^%(?:pre|post|posttrans|preun|postun|files|changelog|description|package)\b|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(spec_text)
    assert match is not None, f"{directive!r} scriptlet not found in salt.spec"
    return match.group(1)


def _strip_shell_comments(text):
    """
    Remove ``#``-style comments from a shell scriptlet body so subsequent
    substring searches don't false-positive against explanatory prose. We
    only strip lines whose first non-whitespace character is ``#`` and
    trailing ``# ...`` comments on ordinary lines; the crude form is enough
    for the audit checks in this file.
    """
    stripped_lines = []
    for line in text.splitlines():
        # Full-line comment.
        if re.match(r"^\s*#", line):
            continue
        # Trailing comment on an otherwise-live line. Avoid stripping ``#``
        # inside single-quoted strings because the scriptlet uses phrases
        # like ``echo '...issue #69656...'``.
        in_single = False
        out = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" and not in_single:
                in_single = True
            elif ch == "'" and in_single:
                in_single = False
            elif ch == "#" and not in_single:
                break
            out.append(ch)
            i += 1
        stripped_lines.append("".join(out))
    return "\n".join(stripped_lines)


@pytest.fixture(scope="module")
def spec_text():
    assert SPEC_FILE.is_file(), f"spec file missing: {SPEC_FILE}"
    return SPEC_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pre_minion_body(spec_text):
    return _extract_scriptlet(spec_text, "%pre minion")


@pytest.fixture(scope="module")
def pre_minion_body_no_comments(pre_minion_body):
    return _strip_shell_comments(pre_minion_body)


@pytest.fixture(scope="module")
def post_minion_body(spec_text):
    return _extract_scriptlet(spec_text, "%post minion")


@pytest.fixture(scope="module")
def posttrans_minion_body(spec_text):
    return _extract_scriptlet(spec_text, "%posttrans minion")


def test_pre_minion_records_was_active_before_stop(pre_minion_body_no_comments):
    """
    ``%pre minion`` must record the unit's pre-upgrade active state
    before invoking ``systemctl stop``. Otherwise ``%posttrans`` has no
    way to know whether the service should be brought back up. See
    https://github.com/saltstack/salt/issues/69605.
    """
    body = pre_minion_body_no_comments
    stop_idx = body.find("systemctl stop salt-minion.service")
    assert stop_idx != -1, (
        "%pre minion no longer stops salt-minion.service on upgrade. "
        "If this was deliberate, drop the matching marker handling in "
        "%posttrans minion too."
    )
    is_active_idx = body.find("systemctl is-active")
    assert is_active_idx != -1, (
        "%pre minion stops salt-minion.service but never records whether "
        "the unit was previously active. %posttrans minion cannot bring "
        "it back without that marker. See issue #69605."
    )
    assert is_active_idx < stop_idx, (
        "%pre minion records the active-state marker *after* the "
        "systemctl stop. The check must happen before the stop or it "
        "will always observe ``inactive``. See issue #69605."
    )


def test_posttrans_minion_starts_when_was_active(posttrans_minion_body):
    """
    ``%posttrans minion`` must use ``systemctl start`` (not just
    ``try-restart``) when the ``%pre`` scriptlet recorded that the unit
    was previously active. ``try-restart`` is a documented no-op for an
    inactive unit, so on its own it cannot recover from the deliberate
    stop in ``%pre``. See https://github.com/saltstack/salt/issues/69605.
    """
    body = posttrans_minion_body
    # The scriptlet must reference the marker file dropped by %pre.
    assert "salt-minion-upgrade-was-active" in body, (
        "%posttrans minion does not consult the pre-upgrade-active "
        "marker; an upgrade that finds the minion running will leave "
        "it stopped. See issue #69605."
    )
    # And it must run ``systemctl start`` (not just ``try-restart``) in
    # response. The cheapest robust check is to ensure both tokens
    # appear in the scriptlet text.
    assert re.search(r"systemctl\s+start\s+salt-minion\.service", body), (
        "%posttrans minion does not call ``systemctl start "
        "salt-minion.service``; ``try-restart`` is a no-op when the "
        "unit is inactive and cannot recover from %pre's stop. See "
        "issue #69605."
    )


# ---------------------------------------------------------------------------
# Issue #69656 -- self-upgrade guard.
# ---------------------------------------------------------------------------


def test_pre_minion_guards_stop_with_self_upgrade_detection(
    pre_minion_body_no_comments,
):
    """
    ``%pre minion`` must not unconditionally invoke ``systemctl stop
    salt-minion.service`` on upgrade -- that deadlocks a minion-driven
    upgrade and causes systemd to SIGKILL the state run. The scriptlet
    must first check whether the transaction was initiated from inside
    ``salt-minion.service`` (self-upgrade case) and, in that case, skip
    the stop. See https://github.com/saltstack/salt/issues/69656.
    """
    body = pre_minion_body_no_comments
    assert "_salt_minion_upgrade_from_running_minion" in body, (
        "%pre minion is missing the "
        "_salt_minion_upgrade_from_running_minion helper that detects a "
        "self-upgrade. Without it the blocking systemctl stop deadlocks "
        "and systemd SIGKILLs the state run. See issue #69656."
    )
    # The stop must be inside an ``else`` branch of the self-upgrade
    # guard, not at top level. Match the fenced structure explicitly.
    guard = re.search(
        r"if\s+_salt_minion_upgrade_from_running_minion.*?"
        r"else\s+.*?systemctl\s+stop\s+salt-minion\.service.*?fi",
        body,
        re.DOTALL,
    )
    assert guard is not None, (
        "%pre minion does not fence ``systemctl stop salt-minion.service`` "
        "behind the self-upgrade detection helper. The stop must live in "
        "the ``else`` branch of ``if "
        "_salt_minion_upgrade_from_running_minion; then ... else ... fi``. "
        "See issue #69656."
    )


def test_pre_minion_drops_self_upgrade_marker(pre_minion_body_no_comments):
    """
    When ``%pre minion`` skips the stop it must drop a marker file so
    ``%post`` and ``%posttrans`` know to leave the still-running minion
    alone; otherwise a subsequent ``try-restart`` would kill the state
    run driving the upgrade. See issue #69656.
    """
    assert "/tmp/.salt-minion-self-upgrade" in pre_minion_body_no_comments, (
        "%pre minion does not drop the /tmp/.salt-minion-self-upgrade "
        "marker in the self-upgrade branch; %post's try-restart would "
        "then kill the still-running state run. See issue #69656."
    )


def test_post_minion_skips_restart_on_self_upgrade(post_minion_body):
    """
    ``%post minion`` runs ``systemctl try-restart salt-minion.service``
    on upgrade. That would interrupt a self-upgrade -- the running state
    would be killed. The scriptlet must skip the ``try-restart`` when
    ``%pre`` left the ``.salt-minion-self-upgrade`` marker. See issue
    #69656.
    """
    body = post_minion_body
    # ``%post minion`` must reference the self-upgrade marker.
    assert "/tmp/.salt-minion-self-upgrade" in body, (
        "%post minion does not consult the self-upgrade marker; a "
        "``systemctl try-restart`` here kills the state run driving the "
        "upgrade. See issue #69656."
    )
    # And it must fence the try-restart behind that marker check.
    stripped = _strip_shell_comments(body)
    guard = re.search(
        r"if\s+\[\s+!\s+-f\s+/tmp/\.salt-minion-self-upgrade\s+\]\s*;\s*then"
        r".*?systemctl\s+try-restart\s+salt-minion\.service.*?fi",
        stripped,
        re.DOTALL,
    )
    assert guard is not None, (
        "%post minion does not fence ``systemctl try-restart`` behind "
        "the /tmp/.salt-minion-self-upgrade guard. See issue #69656."
    )


def test_posttrans_minion_cleans_self_upgrade_marker(posttrans_minion_body):
    """
    ``%posttrans minion`` must remove the ``/tmp/.salt-minion-self-upgrade``
    marker so it does not leak across subsequent transactions. See issue
    #69656.
    """
    assert re.search(
        r"rm\s+-f\s+/tmp/\.salt-minion-self-upgrade", posttrans_minion_body
    ), (
        "%posttrans minion does not remove /tmp/.salt-minion-self-upgrade; "
        "the marker will leak into the next upgrade transaction. See "
        "issue #69656."
    )


# ---------------------------------------------------------------------------
# Functional test of the shell helper against a fake /proc tree.
# ---------------------------------------------------------------------------


def _extract_helper_function(spec_text):
    """
    Return the shell source of ``_salt_minion_upgrade_from_running_minion``
    from ``%pre minion``, isolated so we can source it directly.
    """
    match = re.search(
        r"(_salt_minion_upgrade_from_running_minion\(\)\s*\{.*?\n\})",
        spec_text,
        re.DOTALL,
    )
    assert match is not None, (
        "_salt_minion_upgrade_from_running_minion helper missing from "
        "pkg/rpm/salt.spec. See issue #69656."
    )
    return match.group(1)


def _make_proc(tmpdir, entries):
    """
    Build a fake ``/proc`` layout under ``tmpdir`` for the supplied
    ``entries`` list. Each entry is ``(pid, ppid, cgroup_text)``. Returns
    the fake proc root path.
    """
    proc = tmpdir / "proc"
    proc.mkdir()
    for pid, ppid, cgroup in entries:
        pid_dir = proc / str(pid)
        pid_dir.mkdir()
        (pid_dir / "status").write_text(f"Name:\tfoo\nPPid:\t{ppid}\n")
        (pid_dir / "cgroup").write_text(cgroup)
    return proc


def _run_helper(spec_text, tmp_path, ppid, entries):
    """
    Source the helper against a fake ``/proc`` tree and return its exit
    status. We rewrite the hardcoded ``/proc`` path to point at the
    fake tree and set ``$PPID`` by using a subshell that starts with
    the requested pid on its walk.
    """
    helper = _extract_helper_function(spec_text)
    fake_proc = _make_proc(tmp_path, entries)
    # Patch the helper to read from ``$FAKE_PROC`` instead of ``/proc``.
    helper_patched = helper.replace("/proc/", "${FAKE_PROC}/")
    # Fake the ``$PPID`` bash builtin: it is read-only in bash so we
    # rewrite the reference in the helper to a variable we control.
    helper_patched = helper_patched.replace("_pid=$PPID", "_pid=$PPID_OVERRIDE")
    script = f"""
set -e
FAKE_PROC={fake_proc}
PPID_OVERRIDE={ppid}
{helper_patched}
_salt_minion_upgrade_from_running_minion && echo YES || echo NO
"""
    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover
        pytest.skip("bash not available")
    result = subprocess.run(
        [bash, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"helper harness failed: stdout={result.stdout!r} " f"stderr={result.stderr!r}"
    )
    return result.stdout.strip().splitlines()[-1]


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="bash-executable /proc walk test only runs on Linux",
)
def test_helper_detects_ancestor_in_salt_minion_cgroup(spec_text, tmp_path):
    """
    Simulate the salt-driven upgrade path: dnf (parent of scriptlet)
    was spawned by a salt worker that is still inside
    ``salt-minion.service``. The helper must walk up and report YES.
    """
    # Fake tree: pid 100 (scriptlet's parent, dnf) -> pid 200
    # (systemd-run, still in the transient scope) -> pid 300 (salt
    # worker, in salt-minion.service). The helper starts at $PPID=100.
    entries = [
        (100, 200, "0::/system.slice/run-r1234.scope\n"),
        (200, 300, "0::/system.slice/run-r1234.scope\n"),
        (300, 1, "0::/system.slice/salt-minion.service\n"),
    ]
    assert _run_helper(spec_text, tmp_path, 100, entries) == "YES"


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="bash-executable /proc walk test only runs on Linux",
)
def test_helper_reports_no_when_run_from_root_shell(spec_text, tmp_path):
    """
    A regular administrator invocation (``dnf upgrade salt-minion`` from
    a user session, or a cron job) must NOT match the self-upgrade
    detection. The stop is still required to keep the ownership
    restoration safe. Fake a chain that never enters
    ``salt-minion.service``.
    """
    entries = [
        (100, 200, "0::/user.slice/user-1000.slice/session-3.scope\n"),
        (200, 1, "0::/user.slice/user-1000.slice/session-3.scope\n"),
    ]
    assert _run_helper(spec_text, tmp_path, 100, entries) == "NO"


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="bash-executable /proc walk test only runs on Linux",
)
def test_helper_reports_no_when_ppid_chain_reaches_pid1(spec_text, tmp_path):
    """
    A short PPID chain that terminates at pid 1 without hitting
    ``salt-minion.service`` must return NO. Regression guard against
    the walk mistaking ``init`` for a match.
    """
    entries = [
        (
            100,
            1,
            "0::/init.scope\n",
        ),
    ]
    assert _run_helper(spec_text, tmp_path, 100, entries) == "NO"
