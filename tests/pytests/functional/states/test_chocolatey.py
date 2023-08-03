import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def chocolatey(states):
    if not salt.utils.path.which("choco.exe"):
        pytest.skip("The `chocolatey` binary is not available")
    yield states.chocolatey


@pytest.fixture(scope="module")
def chocolatey_mod(modules):
    yield modules.chocolatey


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


@pytest.mark.destructive_test
def test_installed_latest(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result


@pytest.mark.destructive_test
def test_installed_version(clean, chocolatey, chocolatey_mod):
    chocolatey.installed(name="vim", version="9.0.1672")
    result = chocolatey_mod.version(name="vim")
    assert "vim" in result
    assert result["vim"]["installed"][0] == "9.0.1672"


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
