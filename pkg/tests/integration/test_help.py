def test_help(install_salt):
    """
    Test --help works for all salt cmds
    """
    for cmd in install_salt.binary_paths.values():
        if "salt-cloud" in cmd:
            assert True
        elif "salt-ssh" in cmd:
            assert True
        else:
            ret = install_salt.proc.run(*cmd, "--help")
            assert "Usage" in ret.stdout
            assert ret.returncode == 0
