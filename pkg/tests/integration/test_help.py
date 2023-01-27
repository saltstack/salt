import os.path


def test_help(install_salt):
    """
    Test --help works for all salt cmds
    """
    for cmd in install_salt.binary_paths.values():
        # TODO: add back salt-cloud and salt-ssh when its fixed
        cmd = [str(x) for x in cmd]
        if "python" in cmd[0]:
            ret = install_salt.proc.run(*cmd, "--version")
            assert "Python" in ret.stdout
        else:
            test_bin = os.path.join(*cmd)
            ret = install_salt.proc.run(test_bin, "--help")
            assert "Usage" in ret.stdout
            assert ret.returncode == 0
