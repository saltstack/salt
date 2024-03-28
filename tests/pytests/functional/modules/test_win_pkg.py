import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def pkg_def_contents(state_tree):
    return r"""
    my-software:
      '1.0.1':
        full_name: 'My Software'
        installer: 'C:\files\mysoftware.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'C:\files\mysoftware.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        reboot: False
    """


@pytest.fixture(scope="module")
def pkg(modules):
    yield modules.pkg


def test_refresh_db(pkg, pkg_def_contents, state_tree, minion_opts):
    assert len(pkg.get_package_info("my-software")) == 0
    repo_dir = state_tree / "win" / "repo-ng"
    with pytest.helpers.temp_file("my-software.sls", pkg_def_contents, repo_dir):
        pkg.refresh_db()
    assert len(pkg.get_package_info("my-software")) == 1
