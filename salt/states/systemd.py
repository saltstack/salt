from subprocess import run


def _has_systemd_support():
    ret = run("file sbin/init")
    if ret.returncode != 0:
        return False

    return "systemd" in ret.stdout().lower()


HAS_SYSTEMD = _has_systemd_support()
