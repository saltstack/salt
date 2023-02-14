import pytest


def test_salt_upgrade(salt_call_cli, salt_minion, install_salt):
    """
    Test upgrade of Salt
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")
    # verify previous install version is setup correctly and works
    ret = salt_call_cli.run("test.ping")
    assert ret.returncode == 0
    assert ret.data

    # test pip install before an upgrade
    dep = "PyGithub"
    repo = "https://github.com/saltstack/salt.git"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr
    # upgrade Salt from previous version and test
    install_salt.install(upgrade=True)
    ret = salt_call_cli.run("test.ping")
    assert ret.returncode == 0
    assert ret.data

    # install dep following upgrade
    # TODO: Remove this once we figure out how to
    # preserve things installed via PIP between upgrades.
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # test pip install after an upgrade
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr
