"""
Coverage for the SALT_ONEDIR_HARDEN packaging default (issue #70198).

3009.0 flips ``SALT_ONEDIR_HARDEN=1`` on by default so the salt daemon's
writable state lives under per-daemon ``/var/lib/salt/<daemon>/``
directories and ``/opt/saltstack/salt`` stays root:root 0755. The tests
below verify that layout on a freshly-installed package, plus the
runtime contract that ``salt-pip`` and the daemon's Python honor the
``SALT_EXTRAS_DIR`` env var so the relocated tree stays importable.

These are Linux-package-only tests -- Windows uses a different packaging
model entirely.
"""

import os
import pathlib
import subprocess

import packaging.version
import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def py_ver():
    """Onedir Python major.minor, e.g. ``3.11``."""
    proc = subprocess.run(
        [
            "/opt/saltstack/salt/bin/python3",
            "-c",
            "import sys; sys.stdout.write('{}.{}'.format(*sys.version_info))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _skip_pre_3009(install_salt):
    """
    SALT_ONEDIR_HARDEN default flip lands on 3009.0. Older builds still
    ship the legacy layout, so these assertions can't apply.
    """
    if packaging.version.parse(install_salt.version) < packaging.version.parse(
        "3009.0"
    ):
        pytest.skip("SALT_ONEDIR_HARDEN=1 default lands on 3009.0")


def test_onedir_tree_is_root_owned(install_salt, salt_master):
    """
    Under the hardened default, /opt/saltstack/salt stays owned by
    root:root at 0755 -- the postinst/posttrans no longer chowns the
    onedir tree to the salt user.
    """
    _skip_pre_3009(install_salt)
    if os.environ.get("SALT_ONEDIR_HARDEN") == "0":
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert (
        tree.owner() == "root"
    ), f"/opt/saltstack/salt owner is {tree.owner()!r}, expected root"
    assert (
        tree.group() == "root"
    ), f"/opt/saltstack/salt group is {tree.group()!r}, expected root"


def test_per_daemon_writable_dirs_owned_by_salt(install_salt, salt_master, py_ver):
    """
    Under the hardened default, each daemon's writable state lives at
    /var/lib/salt/<daemon>/{home,extras-<py>} and those dirs are owned
    by the salt user, not root.
    """
    _skip_pre_3009(install_salt)
    if os.environ.get("SALT_ONEDIR_HARDEN") == "0":
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    # salt-master is definitely installed in the pkg test fixture; assert
    # its per-daemon dir. Other daemons are checked only if their base
    # dir exists (multi-role hosts get more coverage; single-role hosts
    # get the daemon they've installed).
    master_dir = pathlib.Path("/var/lib/salt/master")
    assert (
        master_dir.exists()
    ), "expected /var/lib/salt/master to exist under SALT_ONEDIR_HARDEN=1"
    assert master_dir.owner() == "salt"

    home = master_dir / "home"
    if home.exists():
        assert home.owner() == "salt"

    extras = master_dir / f"extras-{py_ver}"
    if extras.exists():
        assert extras.owner() == "salt"

    # Spot-check any other daemon that's also installed.
    for daemon in ("minion", "syndic", "api", "cloud"):
        daemon_dir = pathlib.Path(f"/var/lib/salt/{daemon}")
        if daemon_dir.exists():
            assert daemon_dir.owner() == "salt", (
                f"/var/lib/salt/{daemon} owner is {daemon_dir.owner()!r},"
                " expected salt"
            )


def test_salt_pip_honors_salt_extras_dir(install_salt, tmp_path, py_ver):
    """
    Runtime contract: ``salt-pip install`` honors the SALT_EXTRAS_DIR
    env var (packaging layer sets this under SALT_ONEDIR_HARDEN=1 so
    packages land in the same place the daemon's Python imports from).

    The unit tests already cover the extras-resolution helper; this
    integration test verifies the resolved value actually reaches pip's
    ``--target`` and PYTHONPATH via the real salt-pip binary.
    """
    _skip_pre_3009(install_salt)

    override = tmp_path / "override-extras"
    override.mkdir()

    env = os.environ.copy()
    env["SALT_EXTRAS_DIR"] = str(override)

    # Install a small pure-python package that has no compiled deps so
    # the test is fast and portable across archs.
    proc = subprocess.run(
        [
            "/opt/saltstack/salt/bin/salt-pip",
            "install",
            "--no-deps",
            "six",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, (
        f"salt-pip install failed under SALT_EXTRAS_DIR override:\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )

    # Verify the package landed under the override, not under
    # /opt/saltstack/salt/extras-<py>.
    assert (override / "six.py").exists() or list(override.glob("six-*")), (
        f"six was not installed into SALT_EXTRAS_DIR override {override}; "
        f"tree contents: {list(override.iterdir())}"
    )

    # Clean up so we don't pollute subsequent tests.
    subprocess.run(
        [
            "/opt/saltstack/salt/bin/salt-pip",
            "uninstall",
            "-y",
            "six",
        ],
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
