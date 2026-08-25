"""
Functional tests for chocolatey state with Chocolatey 2.0+
"""

import logging
import os
import pathlib
import time

import pytest

import salt.utils.path
import salt.utils.win_reg
from salt.exceptions import MinionError

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
]

# HTTP status codes and error substrings that indicate a transient failure of
# the Chocolatey Community Repository (proxy/CDN blips, rate limits, TCP
# resets). Matched against the ``MinionError`` message text raised by
# ``cp.get_url`` -- that is the only signal available to the fixture.
_TRANSIENT_HTTP_MARKERS = (
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "HTTP 429",
    "Connection reset",
    "Connection aborted",
    "Connection refused",
    "Read timed out",
    "timed out",
    "Temporary failure",
)


@pytest.fixture(scope="module")
def chocolatey(states):
    yield states.chocolatey


@pytest.fixture(scope="module")
def chocolatey_mod(modules):

    current_path = salt.utils.win_reg.read_value(
        hive="HKLM",
        key=r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        vname="PATH",
    )["vdata"]
    url = "https://community.chocolatey.org/api/v2/package/chocolatey/"
    with pytest.helpers.temp_file(name="choco.nupkg") as nupkg:
        choco_pkg = pathlib.Path(str(nupkg))
    choco_dir = choco_pkg.parent / "choco_dir"
    choco_script = choco_dir / "tools" / "chocolateyInstall.ps1"

    def _download_installer(attempts=5, base_delay=2, max_delay=30):
        # The Chocolatey Community Repository (community.chocolatey.org)
        # intermittently returns HTTP 5xx/429 from its CDN, which breaks
        # nightly CI runs whose only crime is timing. Retry with exponential
        # backoff on those transient errors before giving up.
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                modules.cp.get_url(path=url, dest=str(choco_pkg))
                return
            except MinionError as exc:
                message = str(exc)
                if not any(marker in message for marker in _TRANSIENT_HTTP_MARKERS):
                    raise
                last_error = exc
                if attempt == attempts:
                    break
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                log.warning(
                    "Transient error fetching chocolatey installer (attempt "
                    "%d/%d): %s; retrying in %ds",
                    attempt,
                    attempts,
                    message,
                    delay,
                )
                time.sleep(delay)
        pytest.skip(
            "Chocolatey Community Repository unavailable after "
            f"{attempts} attempts: {last_error}"
        )

    def install():
        # Install Chocolatey 1.2.1

        # Download Package
        _download_installer()

        # Unzip Package
        modules.archive.unzip(
            zip_file=str(choco_pkg),
            dest=str(choco_dir),
            extract_perms=False,
        )

        # Run installer script
        assert choco_script.exists()
        result = modules.cmd.script(
            source=str(choco_script),
            cwd=str(choco_script.parent),
            shell="powershell",
            python_shell=True,
        )
        assert result["retcode"] == 0

    def uninstall():
        choco_dir = os.environ.get("ChocolateyInstall", False)
        if choco_dir:
            # Remove Chocolatey Directory
            modules.file.remove(path=choco_dir, force=True)
            # Remove Chocolatey Environment Variables
            for env_var in modules.environ.items():
                if env_var.lower().startswith("chocolatey"):
                    modules.environ.setval(
                        key=env_var, val=False, false_unsets=True, permanent="HKLM"
                    )
                    modules.environ.setval(
                        key=env_var, val=False, false_unsets=True, permanent="HKCU"
                    )
        salt.utils.win_reg.set_value(
            hive="HKLM",
            key=r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            vname="PATH",
            vdata=current_path,
        )
        modules.win_path.rehash()

    # Remove unknown version
    if salt.utils.path.which("choco.exe"):
        uninstall()

    # Install known version
    install()

    yield modules.chocolatey

    # Remove
    uninstall()


@pytest.fixture(scope="function")
def clean(chocolatey_mod):
    chocolatey_mod.uninstall(name="vim", force=True)
    yield
    chocolatey_mod.uninstall(name="vim", force=True)


@pytest.fixture(scope="function")
def vim(chocolatey_mod):
    chocolatey_mod.install(name="vim", version="9.0.1672")
    yield
    chocolatey_mod.uninstall(name="vim", force=True)


@pytest.fixture(scope="function")
def sudo(chocolatey_mod):
    chocolatey_mod.install(name="sudo", version="1.1.2")
    yield
    chocolatey_mod.uninstall(name="sudo", force=True)


def test_installed_latest(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result


def test_installed_version(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim", version="9.0.1672")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1672"


# @pytest.mark.skipif(True, reason="Timing out, skipping for now")
def test_installed_version_existing_capitalization(sudo, chocolatey, chocolatey_mod):
    result = chocolatey.installed(name="sudo", version="1.1.3")
    expected_changes = {"Sudo": {"new": ["1.1.3"], "old": ["1.1.2"]}}
    assert result["changes"] == expected_changes


def test_uninstalled(vim, chocolatey, chocolatey_mod):
    chocolatey.uninstalled(name="vim")
    result = chocolatey_mod.version(name="vim")
    assert "vim" not in result


def test_upgraded(vim, chocolatey, chocolatey_mod):
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1672"
    chocolatey.upgraded(name="vim", version="9.0.1677")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1677"
