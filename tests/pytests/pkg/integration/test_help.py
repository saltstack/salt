import subprocess


def test_help(install_salt):
    """
    Test --help works for all salt cmds
    """
    for cmd in install_salt.binary_paths.values():
        cmd = [str(x) for x in cmd]

        if len(cmd) > 1 and "shell" in cmd[1]:
            # Singlebin build, unable to get the version
            continue

        if "python" in cmd[0] and len(cmd) == 1:
            ret = install_salt.proc.run(
                *cmd, "--version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            assert "Python" in ret.stdout
        else:
            ret = install_salt.proc.run(
                *cmd, "--help", stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            assert "Usage" in ret.stdout
            assert ret.returncode == 0
