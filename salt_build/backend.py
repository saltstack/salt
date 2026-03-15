"""
Custom build backend for Salt.

This module extends setuptools to handle Salt-specific build logic:
- Platform-specific console script generation
- Dynamic version management
- Custom build hooks
"""

import io
import os
import subprocess
import sys
from pathlib import Path

import setuptools.build_meta as _orig

# ----- Platform Detection ---------------------------------------------------------------------------------------------->
IS_OSX_PLATFORM = sys.platform.startswith("darwin")
IS_WINDOWS_PLATFORM = sys.platform.startswith("win")
IS_SMARTOS_PLATFORM = False
if not (IS_WINDOWS_PLATFORM or IS_OSX_PLATFORM):
    # os.uname() not available on Windows.
    IS_SMARTOS_PLATFORM = os.uname()[0] == "SunOS" and os.uname()[3].startswith(
        "joyent_"
    )

PACKAGED_FOR_SALT_SSH_FILE = Path(__file__).parent.parent / ".salt-ssh-package"
PACKAGED_FOR_SALT_SSH = PACKAGED_FOR_SALT_SSH_FILE.is_file()

# ----- Version Management ---------------------------------------------------------------------------------------------->

SETUP_DIRNAME = Path(__file__).parent.parent.absolute()
SALT_VERSION_MODULE = SETUP_DIRNAME / "salt" / "version.py"
SALT_VERSION_HARDCODED = SETUP_DIRNAME / "salt" / "_version.txt"


def _get_salt_version():
    """Get Salt version from version.py or _version.txt."""
    if SALT_VERSION_HARDCODED.exists():
        return SALT_VERSION_HARDCODED.read_text(encoding="utf-8").strip()

    try:
        result = (
            subprocess.check_output(
                [sys.executable, str(SALT_VERSION_MODULE)],
                cwd=str(SETUP_DIRNAME),
                stderr=subprocess.PIPE,
            )
            .decode()
            .strip()
        )
        return result
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback version
        return "3009.0.0.dev0"


def _write_salt_version():
    """Write Salt version to hardcoded file."""
    version = _get_salt_version()
    SALT_VERSION_HARDCODED.write_text(version, encoding="utf-8")
    return version


# ----- Entry Points Generation --------------------------------------------------------------------------------------->


def _get_entry_points():
    """Generate platform-specific entry points based on environment."""
    entrypoints = {
        "pyinstaller40": [
            "hook-dirs = salt.utils.pyinstaller:get_hook_dirs",
        ],
    }

    # console scripts common to all scenarios
    scripts = [
        "salt-call = salt.scripts:salt_call",
    ]

    if PACKAGED_FOR_SALT_SSH:
        # SSH packaging mode
        scripts.append("salt-ssh = salt.scripts:salt_ssh")
        if IS_WINDOWS_PLATFORM and not os.environ.get("SALT_BUILD_ALL_BINS"):
            entrypoints["console_scripts"] = scripts
            return entrypoints
        scripts.append("salt-cloud = salt.scripts:salt_cloud")
        entrypoints["console_scripts"] = scripts
        return entrypoints

    # Regular packaging mode
    if IS_WINDOWS_PLATFORM and not os.environ.get("SALT_BUILD_ALL_BINS"):
        # Windows with limited binaries
        scripts.extend(
            [
                "salt-cp = salt.scripts:salt_cp",
                "salt-minion = salt.scripts:salt_minion",
                "salt-pip = salt.scripts:salt_pip",
            ]
        )
        entrypoints["console_scripts"] = scripts
        return entrypoints

    # Unix - include all scripts
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


def _write_entry_points_txt(egg_info_dir):
    """Write entry_points.txt file in the egg-info directory."""
    entry_points = _get_entry_points()

    # Format entry points as INI-style text
    output = io.StringIO()
    for group, entries in sorted(entry_points.items()):
        output.write(f"[{group}]\n")
        for entry in sorted(entries):
            output.write(f"{entry}\n")
        output.write("\n")

    # Write to egg-info directory if it exists
    entry_points_file = Path(egg_info_dir) / "entry_points.txt"
    entry_points_file.write_text(output.getvalue(), encoding="utf-8")
    return entry_points_file


def _inject_dynamic_entry_points(metadata_directory):
    """Inject dynamic entry points into the egg-info metadata."""
    # The metadata directory is the egg-info directory after wheel metadata preparation
    if metadata_directory:
        try:
            _write_entry_points_txt(metadata_directory)
        except Exception as e:
            print(f"Warning: Failed to inject entry points: {e}")


# ----- Dynamic Metadata Handling -------------------------------------------------------------------------------------->


def _get_dynamic_version(config_settings=None):
    """Determine version dynamically."""
    return _get_salt_version()


# ----- PEP 517 Build Backend Hooks -------------------------------------------------------------------------------------->


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    """Build wheel with proper version and entry points handling."""
    # Ensure version file exists before building
    _write_salt_version()

    # Build the wheel
    wheel_name = _orig.build_wheel(wheel_directory, config_settings, metadata_directory)
    return wheel_name


def build_sdist(sdist_directory, config_settings=None):
    """Build source distribution with proper version handling."""
    # Ensure version file exists before building
    _write_salt_version()
    return _orig.build_sdist(sdist_directory, config_settings)


def get_requires_for_build_wheel(config_settings=None):
    """Get requirements for building wheel."""
    return _orig.get_requires_for_build_wheel(config_settings)


def get_requires_for_build_sdist(config_settings=None):
    """Get requirements for building sdist."""
    return _orig.get_requires_for_build_sdist(config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    """Prepare metadata for wheel build with dynamic entry points."""
    # First, prepare the metadata using setuptools
    dist_info = _orig.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings
    )

    # Now inject our dynamic entry points
    if metadata_directory:
        _inject_dynamic_entry_points(metadata_directory)

    return dist_info


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    """Build an editable wheel with proper version and entry points handling."""
    # Ensure version file exists before building
    _write_salt_version()

    # Build the editable wheel
    wheel_name = _orig.build_editable(
        wheel_directory, config_settings, metadata_directory
    )
    return wheel_name


def get_requires_for_build_editable(config_settings=None):
    """Get requirements for building editable wheel."""
    return _orig.get_requires_for_build_editable(config_settings)


__all__ = [
    "build_wheel",
    "build_sdist",
    "build_editable",
    "get_requires_for_build_wheel",
    "get_requires_for_build_sdist",
    "get_requires_for_build_editable",
    "prepare_metadata_for_build_wheel",
]
