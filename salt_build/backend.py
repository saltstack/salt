"""
Custom build backend for Salt.
This module extends setuptools to handle Salt-specific build logic:
- Dynamic version management
"""

import subprocess
import sys
from pathlib import Path

import setuptools.build_meta as build_meta_orig
from setuptools.build_meta import *

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


## PEP 517 Build Backend Hooks


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    """Build wheel with proper version and entry points handling."""
    # Ensure version file exists before building
    _write_salt_version()
    # Build the wheel
    wheel_name = build_meta_orig.build_wheel(
        wheel_directory, config_settings, metadata_directory
    )
    return wheel_name


def build_sdist(sdist_directory, config_settings=None):
    """Build source distribution with proper version handling."""
    # Ensure version file exists before building
    _write_salt_version()
    return build_meta_orig.build_sdist(sdist_directory, config_settings)


# Default: get_requires_for_build_wheel

# Default: get_requires_for_build_sdist

# Default: prepare_metadata_for_build_wheel


def build_editable(
    wheel_directory, config_settings=None, metadata_directory=None
) -> str:
    """Build an editable wheel with proper version handling."""
    # Ensure version file exists before building
    _write_salt_version()
    # Build the editable wheel
    wheel_name = build_meta_orig.build_editable(
        wheel_directory, config_settings, metadata_directory
    )
    return wheel_name


# Default: get_requires_for_build_editable
