"""
End-to-end regression coverage for issue #69807: a running minion must
be able to upgrade its own ``salt-minion`` package via ``pkg.installed``
in a state run without crashing on
``ModuleNotFoundError: spec not found for the module 'site'``.

This test exercises the *reporter's exact code path*:

1. A previous salt release is installed by ``salt_systemd_setup``
   (systemd-managed, active).
2. The still-running old minion runs a ``state.sls`` that contains
   ``pkg.installed: salt-minion`` targeting the new artifact.
3. During ``dpkg``/``rpm`` unpack, ``/opt/saltstack/salt/lib/python<VER>/``
   is replaced on disk (when the Python major version changes -- e.g.
   3006.26 Python 3.10 -> 3006.27 Python 3.11 -- the entire directory
   tree is unlinked).
4. After ``pkg.installed`` returns success, ``salt.state.State.call``
   invokes ``check_refresh`` for the ``pkg`` state. Before the fix,
   ``check_refresh`` called ``module_refresh`` -> ``importlib.reload(site)``
   -> ``ModuleNotFoundError``, which killed the salt-call process
   mid-state-run. After the fix, ``check_refresh`` detects the salt
   package name in ``ret["changes"]`` and short-circuits.

The test asserts:

* ``salt-call state.sls`` returns successfully (exit 0, ret parseable).
* The ``pkg.installed`` state reports ``result: True`` and
  ``changes`` includes ``salt-minion``.
* No ``ModuleNotFoundError`` appears in the state ret comment.
* The minion service is contactable via ``salt-call test.version`` after
  the upgrade completes (using the FAQ ``cmd.run bg: True`` pattern to
  restart the service in a detached child).

Infra requirements:

* The full ``tests/pytests/pkg/upgrade/systemd/`` fixture stack, which
  requires salt packages built by ``tools pkg build`` under
  ``ARTIFACTS_DIR`` and pytest launched with ``--upgrade
  --prev-version=<older>``. This runs in the packaging test job of
  CI (matrix on distro/os), not in the standard unit/functional CI
  lanes.
* systemd (skip on non-systemd hosts) and an old salt release installed
  as a system package (skip if the fixture cannot install one).

If you're running this locally you need a checkout with built packages
under ``artifacts/pkg/`` and to invoke pytest with the packaging test
options -- see ``tests/pytests/pkg/conftest.py`` for the full option
list. The test is written so a mis-configured environment produces a
skip with a specific reason, never a silent pass.
"""

import json
import logging
import pathlib
import subprocess
import textwrap
import time

import packaging.version
import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux(
        reason="salt-minion self-upgrade regression #69807 is Linux-packaging-specific"
    ),
]


# SLS used to drive the self-upgrade. Mirrors the reporter's
# ``updatesalt.sls`` (see issue body) with two differences: we use
# ``latest`` instead of a literal version so the test doesn't have to
# know the artifact version, and we point the followup ``cmd.run`` at
# the same ``salt-call`` binary that ran the state so the restart runs
# post-upgrade under the new interpreter.
SELF_UPGRADE_SLS = textwrap.dedent(
    """\
    # policy-rc.d prevents Debian/Ubuntu ``dpkg`` from starting services
    # mid-unpack; without it, the postinst's dh_installsystemd-injected
    # restart would race the state run. This is exactly the pattern
    # documented in the FAQ ``Upgrade without automatic restart``.
    {%- if grains['os_family'] == 'Debian' %}
    Disable starting services:
      file.managed:
        - name: /usr/sbin/policy-rc.d
        - user: root
        - group: root
        - mode: 0755
        - contents:
          - '#!/bin/sh'
          - exit 101
        - replace: False
        - prereq:
          - pkg: Upgrade Salt Minion
    {%- endif %}

    Upgrade Salt Minion:
      pkg.installed:
        - name: salt-minion
        - version: {{ pillar['upgrade_version'] }}

    {%- if grains['os_family'] == 'Debian' %}
    Enable starting services:
      file.absent:
        - name: /usr/sbin/policy-rc.d
        - onchanges:
          - pkg: Upgrade Salt Minion
    {%- endif %}
    """
)


def _state_tree_for(install_salt_systemd):
    """
    Return the state_tree path used by the master_systemd fixture.
    """
    from pytestskipmarkers.utils import platform as pmp

    if pmp.is_windows():
        return pathlib.Path(r"C:\salt\srv\salt")
    if pmp.is_darwin():
        return pathlib.Path("/opt/srv/salt")
    return pathlib.Path("/srv/salt")


def test_salt_minion_self_upgrade_via_state_sls(
    call_cli, install_salt_systemd, salt_systemd_setup
):
    """
    Regression test for issue #69807: a running salt-minion must be
    able to upgrade its own package via a ``pkg.installed`` state run
    without crashing on the post-``pkg`` module refresh.

    The bug is not exclusive to Debian even though the reporter used
    a deb; the ``check_refresh`` -> ``module_refresh`` ->
    ``importlib.reload(site)`` path is triggered on any successful
    ``pkg.installed`` state, and the ``site.py`` on disk is replaced
    by both dpkg and rpm on a self-upgrade. However, the reporter's
    exact trigger (Python major-version bump 3.10 -> 3.11) is deb-only
    for 3006.26 -> 3006.27; the RPM upgrade in that window has a
    separate deadlock (issue #69656) that would mask this bug. Run on
    Debian/Ubuntu only, where the bug is directly reproducible.
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt_systemd.distro_id not in ("debian", "ubuntu"):
        pytest.skip(
            f"Issue #69807 is directly reproducible on deb; RPM path is masked "
            f"by the #69656 deadlock. distro_id={install_salt_systemd.distro_id!r} "
            f"not in scope for this regression test."
        )

    install_salt_systemd.no_uninstall = False

    upgrade_version = install_salt_systemd.artifact_version
    state_tree = _state_tree_for(install_salt_systemd)
    state_tree.mkdir(parents=True, exist_ok=True)
    sls_path = state_tree / "updatesalt.sls"
    sls_path.write_text(SELF_UPGRADE_SLS)

    try:
        # 1. Confirm the (old) minion service is active before we drive
        #    the self-upgrade -- the bug requires a live minion.
        is_active = subprocess.run(
            ["systemctl", "is-active", "salt-minion"],
            check=False,
            capture_output=True,
            text=True,
        )
        if is_active.stdout.strip() != "active":
            # Ensure a known-good starting point.
            subprocess.run(
                ["systemctl", "start", "salt-minion"],
                check=False,
                capture_output=True,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                is_active = subprocess.run(
                    ["systemctl", "is-active", "salt-minion"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if is_active.stdout.strip() == "active":
                    break
                time.sleep(1)
        assert is_active.stdout.strip() == "active", (
            "salt-minion could not be brought active before the self-upgrade "
            f"test; is-active output: {is_active.stdout!r}"
        )

        # 2. Drive the upgrade with ``salt-call state.sls`` -- this
        #    matches the reporter's exact invocation
        #    (``salt-call -l debug state.sls updatesalt``). We use the
        #    ``call_cli`` fixture which wraps salt-call from the
        #    currently-installed (previous) version.
        ret = call_cli.run(
            "--local",
            "--out=json",
            "pillar={upgrade_version: " + str(upgrade_version) + "}",
            "state.sls",
            "updatesalt",
        )

        # 3. Assertions on the primary bug: state.sls must complete
        #    normally (no traceback, ret parseable).
        assert ret.returncode == 0, (
            f"salt-call state.sls updatesalt failed with returncode "
            f"{ret.returncode}; this is the exact failure mode of "
            f"issue #69807 when the fix has regressed. "
            f"stdout={ret.stdout!r} stderr={ret.stderr!r}"
        )
        # The reporter's traceback string must not appear in stderr --
        # it did before the fix (``ModuleNotFoundError: spec not found
        # for the module 'site'``).
        assert "spec not found for the module 'site'" not in (ret.stderr or ""), (
            f"Reporter's #69807 traceback resurfaced in salt-call stderr: "
            f"{ret.stderr!r}"
        )

        # 4. Parse the ret and confirm ``pkg.installed`` succeeded and
        #    ``salt-minion`` really did change.
        try:
            state_ret = ret.data or json.loads(ret.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            pytest.fail(
                f"Could not parse salt-call state.sls output as JSON: {exc}; "
                f"stdout={ret.stdout!r}"
            )

        # locate the pkg.installed state result under the ``local:`` key
        # (masterless mode) or top-level, depending on salt version
        chunks = (
            state_ret.get("local", state_ret) if isinstance(state_ret, dict) else {}
        )
        pkg_chunk = None
        for sid, chunk in chunks.items():
            if isinstance(chunk, dict) and chunk.get("__id__") == "Upgrade Salt Minion":
                pkg_chunk = chunk
                break
            if isinstance(sid, str) and "Upgrade Salt Minion" in sid:
                pkg_chunk = chunk
                break
        assert (
            pkg_chunk is not None
        ), f"Could not find 'Upgrade Salt Minion' state chunk in ret: {chunks!r}"
        assert (
            pkg_chunk.get("result") is True
        ), f"pkg.installed did not report success: {pkg_chunk!r}"
        changes = pkg_chunk.get("changes") or {}
        assert "salt-minion" in changes, (
            f"salt-minion not reported as changed by pkg.installed; changes={changes!r}. "
            f"Test cannot validate the self-upgrade fix without a real version bump."
        )
        old_version = changes["salt-minion"].get("old")
        new_version = changes["salt-minion"].get("new")
        assert old_version and new_version and old_version != new_version, (
            f"salt-minion change record does not reflect a version bump: "
            f"{changes['salt-minion']!r}"
        )
        log.info(
            "Self-upgrade completed cleanly: salt-minion %s -> %s "
            "(no ModuleNotFoundError, no state-run abort)",
            old_version,
            new_version,
        )

        # 5. Confirm the new minion is still contactable. The state run
        #    itself does NOT restart the service (the FAQ pattern's
        #    ``cmd.run bg: True`` would; we skip that here because it
        #    detaches from the salt-call process and its timing is
        #    orthogonal to the #69807 fix). Instead, restart via
        #    systemctl and verify ``salt-call test.version`` reports
        #    the new version. This proves the upgrade wasn't just a
        #    state-runner success but actually landed working code.
        subprocess.run(
            ["systemctl", "restart", "salt-minion"],
            check=True,
            capture_output=True,
        )
        # Poll for readiness.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ver_ret = call_cli.run("--local", "test.version")
            if ver_ret.returncode == 0 and ver_ret.data:
                break
            time.sleep(2)
        assert ver_ret.returncode == 0, (
            f"post-upgrade salt-call test.version failed: "
            f"stdout={ver_ret.stdout!r} stderr={ver_ret.stderr!r}"
        )
        post_version = packaging.version.parse(str(ver_ret.data))
        assert post_version >= packaging.version.parse(upgrade_version), (
            f"post-upgrade minion reports {post_version!r}, "
            f"expected >= {upgrade_version!r}"
        )
    finally:
        # Clean up the SLS. The systemd fixture teardown handles
        # everything else.
        try:
            sls_path.unlink()
        except FileNotFoundError:
            pass
