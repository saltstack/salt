import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from setuptools import build_meta as _orig

# PEP 517 hooks
prepare_metadata_for_build_wheel = _orig.prepare_metadata_for_build_wheel
build_wheel = _orig.build_wheel
build_sdist = _orig.build_sdist
get_requires_for_build_wheel = _orig.get_requires_for_build_wheel
get_requires_for_build_sdist = _orig.get_requires_for_build_sdist


def _parse_requirements_file(requirements_file):
    parsed_requirements = []
    if not os.path.exists(requirements_file):
        return parsed_requirements
    # pylint: disable=resource-leakage
    with open(requirements_file, encoding="utf-8") as rfh:
        # pylint: enable=resource-leakage
        for line in rfh.readlines():
            line = line.strip()
            if not line or line.startswith(("#", "-r", "--")):
                continue
            # Logic from setup.py for windows libcloud skip
            if sys.platform.startswith("win"):
                if "libcloud" in line:
                    continue
            parsed_requirements.append(line)
    return parsed_requirements


def get_salt_version(dist=None):
    salt_version_module = os.path.join(PROJECT_ROOT, "salt", "version.py")
    # We can't import salt.version directly because dependencies might not be there
    # But we can exec it in a controlled environment
    g = {"__opts__": {}, "__file__": salt_version_module}
    # pylint: disable=resource-leakage
    with open(salt_version_module, encoding="utf-8") as f:
        # pylint: enable=resource-leakage
        exec(f.read(), g)
    return str(g["__saltstack_version__"])


def get_install_requires(dist=None):
    use_static = os.environ.get("USE_STATIC_REQUIREMENTS") == "1"

    is_osx = sys.platform.startswith("darwin")
    is_windows = sys.platform.startswith("win")

    reqs = []
    if use_static:
        if is_osx:
            req_files = [
                os.path.join(
                    PROJECT_ROOT,
                    "requirements",
                    "static",
                    "pkg",
                    f"py{sys.version_info[0]}.{sys.version_info[1]}",
                    "darwin.txt",
                )
            ]
        elif is_windows:
            req_files = [
                os.path.join(
                    PROJECT_ROOT,
                    "requirements",
                    "static",
                    "pkg",
                    f"py{sys.version_info[0]}.{sys.version_info[1]}",
                    "windows.txt",
                )
            ]
        else:
            req_files = [
                os.path.join(
                    PROJECT_ROOT,
                    "requirements",
                    "static",
                    "pkg",
                    f"py{sys.version_info[0]}.{sys.version_info[1]}",
                    "linux.txt",
                )
            ]
    else:
        # Base requirements
        req_files = [
            os.path.join(PROJECT_ROOT, "requirements", "base.txt"),
            os.path.join(PROJECT_ROOT, "requirements", "zeromq.txt"),
        ]
        if is_osx:
            req_files.append(os.path.join(PROJECT_ROOT, "requirements", "darwin.txt"))
        elif is_windows:
            req_files.append(os.path.join(PROJECT_ROOT, "requirements", "windows.txt"))

    for req_file in req_files:
        reqs.extend(_parse_requirements_file(req_file))
    return reqs


def get_extras_require(dist=None):
    crypto_req = os.path.join(PROJECT_ROOT, "requirements", "crypto.txt")
    extras = {}
    if os.path.exists(crypto_req):
        extras["crypto"] = _parse_requirements_file(crypto_req)
    return extras


def get_scripts(dist=None):
    is_windows = sys.platform.startswith("win")
    scripts = ["scripts/salt-call"]

    ssh_packaging = False
    if dist:
        ssh_packaging = getattr(dist, "ssh_packaging", False)
    if not ssh_packaging:
        ssh_packaging = os.path.exists(
            os.path.join(PROJECT_ROOT, "salt", "_ssh_packaging")
        )

    if ssh_packaging:
        scripts.append("scripts/salt-ssh")
        if is_windows and not os.environ.get("SALT_BUILD_ALL_BINS"):
            return scripts
        scripts.extend(["scripts/salt-cloud", "scripts/spm"])
        return scripts

    if is_windows and not os.environ.get("SALT_BUILD_ALL_BINS"):
        scripts.extend(["scripts/salt-cp", "scripts/salt-minion"])
        return scripts

    # *nix or SALT_BUILD_ALL_BINS, so, we need all scripts
    scripts.extend(
        [
            "scripts/salt",
            "scripts/salt-api",
            "scripts/salt-cloud",
            "scripts/salt-cp",
            "scripts/salt-key",
            "scripts/salt-master",
            "scripts/salt-minion",
            "scripts/salt-proxy",
            "scripts/salt-run",
            "scripts/salt-ssh",
            "scripts/salt-syndic",
            "scripts/spm",
        ]
    )
    return scripts
