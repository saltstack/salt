import pytest


def test_salt_upgrade(salt_call_cli, install_salt):
    """
    Test an upgrade of Salt.
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # Verify previous install version is setup correctly and works
    ret = salt_call_cli.run("test.version")
    assert ret.returncode == 0
    assert ret.data == install_salt.prev_version

    # Test pip install before an upgrade
    dep = "PyGithub==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # Verify we can use the module dependent on the installed package
    repo = "https://github.com/saltstack/salt.git"
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr

    # Upgrade Salt from previous version and test
    install_salt.install(upgrade=True)
    new_py_version = install_salt.package_python_version()
    ret = salt_call_cli.run("test.version")
    assert ret.returncode == 0
    assert ret.data == install_salt.artifact_version

    # Install dep following upgrade
    # TODO: This should be removed when we stop testing against versions < 3006.0
    if (
        install_salt.relenv and original_py_version != new_py_version
    ) or not install_salt.relenv:
        install = salt_call_cli.run("--local", "pip.install", dep)
        assert install.returncode == 0

    # test pip install after an upgrade
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr
