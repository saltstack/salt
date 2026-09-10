"""
Integration tests for per-host ``relenv:`` roster support in salt-ssh.

Regression coverage for https://github.com/saltstack/salt/issues/69885

Prior to the fix, setting ``relenv: True`` on an individual roster entry was
silently ignored -- only the global ``--relenv`` CLI flag (or Saltfile
setting) actually toggled the relenv deployment path.  That forced operators
of mixed fleets to either enable relenv globally (shipping the ~200MB onedir
tarball to every host reached by a wildcard target) or forgo relenv entirely
for hosts that legitimately needed it.

These tests exercise the observable end-to-end behavior of ``Single``:

    * The rendered ``thin_dir`` for a roster entry with ``relenv: True`` ends
      in ``_salt_relenv`` (the suffix ``Single.__init__`` applies when
      ``opts['relenv']`` is truthy).
    * The rendered ``thin_dir`` for a roster entry without ``relenv`` (and
      without global ``--relenv``) has no such suffix.
    * When a roster contains both kinds of entries and salt-ssh targets them
      via wildcard, each host gets its own deployment path -- the relenv host
      gets the relenv thin_dir, the plain host keeps the classic thin_dir.
      This is the mixed-fleet behavior the bug prevented.

Cases that require a fully deployed relenv onedir (cases 1 and 3) reuse the
session-scoped ``relenv_tarball_cached`` fixture from
``tests/pytests/integration/ssh/conftest.py`` and skip when the tarball is
not available locally, mirroring the pattern in ``test_deploy_relenv.py``.
Case 2 does not need the tarball and always runs on supported platforms.
"""

import shutil

import pytest

import salt.utils.files
import salt.utils.yaml

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(autouse=True)
def _cleanup_thin_dirs(salt_ssh_cli):
    """
    Best-effort cleanup of the on-disk thin directories the test creates.

    We do not fail the test on cleanup errors -- the goal is only to keep
    ``/var/tmp/.<user>_<uuid>_salt*`` from accumulating across runs.
    """
    try:
        yield
    finally:
        # Query whichever thin_dir the default roster produced; individual
        # tests may have created additional per-host thin_dirs but this
        # covers the shared baseline.
        try:
            ret = salt_ssh_cli.run("config.get", "thin_dir")
            if ret.returncode == 0 and ret.data:
                shutil.rmtree(ret.data, ignore_errors=True)
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def _write_roster(tmp_path, name, entries):
    """
    Serialize a roster ``dict`` to a temp file under ``tmp_path`` and return
    its path.  Kept local to this module to avoid coupling to unrelated
    fixtures.
    """
    roster_file = tmp_path / name
    with salt.utils.files.fopen(str(roster_file), "w") as wfh:
        salt.utils.yaml.safe_dump(entries, wfh)
    return roster_file


def _base_entry(salt_ssh_roster_file):
    """
    Read the shared roster and return the ``localhost`` entry -- we reuse its
    port/user/known_hosts wiring so the new roster files talk to the same
    session sshd.
    """
    with salt.utils.files.fopen(salt_ssh_roster_file) as rfh:
        data = salt.utils.yaml.safe_load(rfh)
    return data["localhost"]


def test_roster_relenv_true_uses_relenv_thin_dir(
    salt_ssh_cli, salt_ssh_roster_file, tmp_path, relenv_tarball_cached
):
    """
    Case 1: a roster entry with ``relenv: True`` deploys via the relenv path.

    Observable: the target's ``thin_dir`` ends with ``_salt_relenv``.  Before
    the fix, the roster key was dropped and ``thin_dir`` ended in plain
    ``_salt``.
    """
    if relenv_tarball_cached is None:
        pytest.skip("Relenv tarball not available")
    entry = _base_entry(salt_ssh_roster_file)
    entry_relenv = dict(entry)
    entry_relenv["relenv"] = True
    roster = {"localhost": entry_relenv}
    roster_file = _write_roster(tmp_path, "roster-relenv-true", roster)

    ret = salt_ssh_cli.run(f"--roster-file={roster_file}", "config.get", "thin_dir")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data.endswith(
        "_salt_relenv"
    ), f"expected relenv thin_dir suffix, got {ret.data!r}"


def test_roster_relenv_absent_uses_classic_thin_dir(
    salt_ssh_cli, salt_ssh_roster_file, tmp_path
):
    """
    Case 2: no ``relenv`` in the roster and no ``--relenv`` flag -- classic
    thin deployment.

    Observable: ``thin_dir`` ends with plain ``_salt`` (no ``_relenv``
    suffix).  Guards against a regression where roster-relenv might leak into
    hosts that never asked for it.
    """
    entry = _base_entry(salt_ssh_roster_file)
    # Ensure no accidental relenv key survives.
    entry_plain = {k: v for k, v in entry.items() if k != "relenv"}
    roster = {"localhost": entry_plain}
    roster_file = _write_roster(tmp_path, "roster-relenv-absent", roster)

    ret = salt_ssh_cli.run(f"--roster-file={roster_file}", "config.get", "thin_dir")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data.endswith(
        "_salt"
    ), f"expected classic thin_dir suffix, got {ret.data!r}"
    assert not ret.data.endswith("_salt_relenv")


def test_roster_relenv_mixed_fleet(
    salt_ssh_cli, salt_ssh_roster_file, tmp_path, relenv_tarball_cached
):
    """
    Case 3: mixed roster + wildcard target -- only the entry with
    ``relenv: True`` gets the relenv deployment; the plain entry keeps the
    classic thin deployment.

    This is the scenario the bug fix exists for: prior to the fix, a
    ``salt-ssh '*' test.ping`` against a roster where only some hosts had
    ``relenv: True`` would treat every host as classic thin (silently
    ignoring the roster key), forcing operators to opt in globally.
    """
    if relenv_tarball_cached is None:
        pytest.skip("Relenv tarball not available")

    entry = _base_entry(salt_ssh_roster_file)
    entry_plain = {k: v for k, v in entry.items() if k != "relenv"}
    entry_relenv = dict(entry_plain)
    entry_relenv["relenv"] = True

    roster = {
        "host-thin": entry_plain,
        "host-relenv": entry_relenv,
    }
    roster_file = _write_roster(tmp_path, "roster-relenv-mixed", roster)

    ret = salt_ssh_cli.run(
        f"--roster-file={roster_file}",
        "config.get",
        "thin_dir",
        minion_tgt="*",
    )
    assert ret.returncode == 0
    assert isinstance(
        ret.data, dict
    ), f"expected per-host dict, got {type(ret.data).__name__}: {ret.data!r}"
    assert set(ret.data.keys()) == {"host-thin", "host-relenv"}, ret.data

    thin_host_dir = ret.data["host-thin"]
    relenv_host_dir = ret.data["host-relenv"]

    assert thin_host_dir.endswith("_salt")
    assert not thin_host_dir.endswith(
        "_salt_relenv"
    ), f"plain roster entry unexpectedly got relenv thin_dir: {thin_host_dir!r}"
    assert relenv_host_dir.endswith(
        "_salt_relenv"
    ), f"relenv roster entry did not get relenv thin_dir: {relenv_host_dir!r}"

    # Belt-and-suspenders cleanup for the extra per-host thin dirs the
    # mixed-target run created.
    for path in (thin_host_dir, relenv_host_dir):
        shutil.rmtree(path, ignore_errors=True)
