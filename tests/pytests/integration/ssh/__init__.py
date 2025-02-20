import subprocess

import packaging


def check_system_python_version():
    """
    Validate the system python version is greater than 3.9
    """
    try:
        ret = subprocess.run(
            ["/usr/bin/python3", "--version"], capture_output=True, check=True
        )
    except FileNotFoundError:
        return None
    ver = ret.stdout.decode().split(" ", 1)[-1]
    return packaging.version.Version(ver) >= packaging.version.Version("3.9")
