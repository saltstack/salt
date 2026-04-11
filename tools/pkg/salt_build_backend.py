import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from setuptools import build_meta as _orig

# PEP 517 hooks
def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    # This hook is used by 'pip install' and 'build' to get metadata without building a wheel
    # We need to make sure the metadata we return includes our dynamic fields
    # Setuptools doesn't automatically call get_dynamic_metadata for us in all versions
    
    # First, let setuptools do its thing
    ret = _orig.prepare_metadata_for_build_wheel(metadata_directory, config_settings)
    
    # Now we need to update the PKG-INFO/METADATA file it created
    # The name of the directory is usually salt-<version>.dist-info
    dist_info_dir = os.path.join(metadata_directory, ret)
    metadata_file = os.path.join(dist_info_dir, "METADATA")
    
    with open(metadata_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # If it already has Requires-Dist, we don't want to double it
    if "Requires-Dist:" not in content:
        requires = get_install_requires()
        new_lines = []
        for req in requires:
            new_lines.append(f"Requires-Dist: {req}")
        
        # Insert before the description (first empty line followed by content)
        if "\n\n" in content:
            parts = content.split("\n\n", 1)
            content = parts[0] + "\n" + "\n".join(new_lines) + "\n\n" + parts[1]
        else:
            content += "\n" + "\n".join(new_lines)
            
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(content)
            
    return ret

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    # If metadata_directory is provided, setuptools should use it.
    # If not, we might want to create it ourselves to ensure dependencies are there.
    if metadata_directory is None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            metadata_directory = td
            prepare_metadata_for_build_wheel(metadata_directory, config_settings)
            return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)

build_sdist = _orig.build_sdist
get_requires_for_build_wheel = _orig.get_requires_for_build_wheel
get_requires_for_build_sdist = _orig.get_requires_for_build_sdist


def get_dynamic_metadata(name, settings=None):
    if name == "version":
        return get_salt_version()
    if name == "dependencies":
        return get_install_requires()
    if name == "optional-dependencies":
        return get_extras_require()
    if name == "entry-points":
        return get_entry_points()
    if name == "scripts":
        return get_scripts()
    raise AttributeError(name)


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
            os.path.join(PROJECT_ROOT, "requirements", "crypto.txt"),
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


def get_entry_points(dist=None):
    is_windows = sys.platform.startswith("win")
    entrypoints = {
        "pyinstaller40": [
            "hook-dirs = salt.utils.pyinstaller:get_hook_dirs",
        ],
    }
    # console scripts common to all scenarios
    scripts = [
        "salt-call = salt.scripts:salt_call",
    ]

    ssh_packaging = False
    if dist:
        ssh_packaging = getattr(dist, "ssh_packaging", False)
    if not ssh_packaging:
        ssh_packaging = os.path.exists(
            os.path.join(PROJECT_ROOT, "salt", "_ssh_packaging")
        )

    if ssh_packaging:
        scripts.append("salt-ssh = salt.scripts:salt_ssh")
        if is_windows and not os.environ.get("SALT_BUILD_ALL_BINS"):
            return {"console_scripts": scripts}
        scripts.append("salt-cloud = salt.scripts:salt_cloud")
        entrypoints["console_scripts"] = scripts
        return entrypoints

    if is_windows and not os.environ.get("SALT_BUILD_ALL_BINS"):
        scripts.extend(
            [
                "salt-cp = salt.scripts:salt_cp",
                "salt-minion = salt.scripts:salt_minion",
                "salt-pip = salt.scripts:salt_pip",
            ]
        )
        entrypoints["console_scripts"] = scripts
        return entrypoints

    # *nix, so, we need all scripts
    scripts.extend(
        [
            "salt = salt.scripts:salt_main",
            "salt-api = salt.scripts:salt_api",
            "salt-cloud = salt.scripts:salt_cloud",
            "salt-cp = salt.scripts:salt_cp",
            "salt-key = salt.scripts:salt_key",
            "salt-master = salt.scripts:salt_master",
            "salt-minion = salt.scripts:salt_minion",
            "salt-run = salt.scripts:salt_run",
            "salt-ssh = salt.scripts:salt_ssh",
            "salt-syndic = salt.scripts:salt_syndic",
            "spm = salt.scripts:salt_spm",
            "salt-proxy = salt.scripts:salt_proxy",
            "salt-pip = salt.scripts:salt_pip",
        ]
    )
    entrypoints["console_scripts"] = scripts
    return entrypoints


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
