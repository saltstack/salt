# -*- coding: utf-8 -*-
"""
    salt.syspaths
    ~~~~~~~~~~~~~

    Salt's defaults system paths

    This module allows defining Salt's default paths at build time by writing a
    ``_syspath.py`` file to the filesystem. This is useful, for example, for
    setting platform-specific defaults that differ from the standard Linux
    paths.

    These values are static values and must be considered as secondary to any
    paths that are set in the master/minion config files.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os.path
import sys

__PLATFORM = sys.platform.lower()
typo_warning = True
log = logging.getLogger(__name__)
EXPECTED_VARIABLES = (
    "ROOT_DIR",
    "CONFIG_DIR",
    "CACHE_DIR",
    "SOCK_DIR",
    "SRV_ROOT_DIR",
    "BASE_FILE_ROOTS_DIR",
    "HOME_DIR",
    "BASE_PILLAR_ROOTS_DIR",
    "BASE_THORIUM_ROOTS_DIR",
    "BASE_MASTER_ROOTS_DIR",
    "LOGS_DIR",
    "PIDFILE_DIR",
    "SPM_PARENT_PATH",
    "SPM_FORMULA_PATH",
    "SPM_PILLAR_PATH",
    "SPM_REACTOR_PATH",
    "SHARE_DIR",
)

try:
    # Let's try loading the system paths from the generated module at
    # installation time.
    import salt._syspaths as __generated_syspaths  # pylint: disable=no-name-in-module
except ImportError:
    import types

    __generated_syspaths = types.ModuleType(
        str("salt._syspaths")
    )  # future lint: blacklisted-function
    for key in EXPECTED_VARIABLES:
        setattr(__generated_syspaths, key, None)
else:
    for key in EXPECTED_VARIABLES:
        if hasattr(__generated_syspaths, key):
            continue
        else:
            if typo_warning:
                log.warning("Possible Typo?")
                log.warning(
                    "To dissolve this warning add `[variable] = None` to _syspaths.py"
                )
            typo_warning = False
            log.warning("Variable %s is missing, value set to None", key)
            setattr(
                __generated_syspaths, key, None
            )  # missing variables defaulted to None

# Let's find out the path of this module
if "SETUP_DIRNAME" in globals():
    # This is from the exec() call in Salt's setup.py
    # pylint: disable=undefined-variable
    __THIS_FILE = os.path.join(SETUP_DIRNAME, "salt", "syspaths.py")
    # pylint: enable=undefined-variable
else:
    __THIS_FILE = __file__


# These values are always relative to salt's installation directory
INSTALL_DIR = os.path.dirname(os.path.realpath(__THIS_FILE))
CLOUD_DIR = os.path.join(INSTALL_DIR, "cloud")
BOOTSTRAP = os.path.join(CLOUD_DIR, "deploy", "bootstrap-salt.sh")

ROOT_DIR = __generated_syspaths.ROOT_DIR
if ROOT_DIR is None:
    # The installation time value was not provided, let's define the default
    if __PLATFORM.startswith("win"):
        ROOT_DIR = r"c:\salt"
    else:
        ROOT_DIR = "/"

CONFIG_DIR = __generated_syspaths.CONFIG_DIR
if CONFIG_DIR is None:
    if __PLATFORM.startswith("win"):
        CONFIG_DIR = os.path.join(ROOT_DIR, "conf")
    elif "freebsd" in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, "usr", "local", "etc", "salt")
    elif "netbsd" in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, "usr", "pkg", "etc", "salt")
    elif "sunos5" in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, "opt", "local", "etc", "salt")
    else:
        CONFIG_DIR = os.path.join(ROOT_DIR, "etc", "salt")

SHARE_DIR = __generated_syspaths.SHARE_DIR
if SHARE_DIR is None:
    if __PLATFORM.startswith("win"):
        SHARE_DIR = os.path.join(ROOT_DIR, "share")
    elif "freebsd" in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, "usr", "local", "share", "salt")
    elif "netbsd" in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, "usr", "share", "salt")
    elif "sunos5" in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, "usr", "share", "salt")
    else:
        SHARE_DIR = os.path.join(ROOT_DIR, "usr", "share", "salt")

CACHE_DIR = __generated_syspaths.CACHE_DIR
if CACHE_DIR is None:
    CACHE_DIR = os.path.join(ROOT_DIR, "var", "cache", "salt")

SOCK_DIR = __generated_syspaths.SOCK_DIR
if SOCK_DIR is None:
    SOCK_DIR = os.path.join(ROOT_DIR, "var", "run", "salt")

SRV_ROOT_DIR = __generated_syspaths.SRV_ROOT_DIR
if SRV_ROOT_DIR is None:
    SRV_ROOT_DIR = os.path.join(ROOT_DIR, "srv")

BASE_FILE_ROOTS_DIR = __generated_syspaths.BASE_FILE_ROOTS_DIR
if BASE_FILE_ROOTS_DIR is None:
    BASE_FILE_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, "salt")

BASE_PILLAR_ROOTS_DIR = __generated_syspaths.BASE_PILLAR_ROOTS_DIR
if BASE_PILLAR_ROOTS_DIR is None:
    BASE_PILLAR_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, "pillar")

BASE_THORIUM_ROOTS_DIR = __generated_syspaths.BASE_THORIUM_ROOTS_DIR
if BASE_THORIUM_ROOTS_DIR is None:
    BASE_THORIUM_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, "thorium")

BASE_MASTER_ROOTS_DIR = __generated_syspaths.BASE_MASTER_ROOTS_DIR
if BASE_MASTER_ROOTS_DIR is None:
    BASE_MASTER_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, "salt-master")

LOGS_DIR = __generated_syspaths.LOGS_DIR
if LOGS_DIR is None:
    LOGS_DIR = os.path.join(ROOT_DIR, "var", "log", "salt")

PIDFILE_DIR = __generated_syspaths.PIDFILE_DIR
if PIDFILE_DIR is None:
    PIDFILE_DIR = os.path.join(ROOT_DIR, "var", "run")

SPM_PARENT_PATH = __generated_syspaths.SPM_PARENT_PATH
if SPM_PARENT_PATH is None:
    SPM_PARENT_PATH = os.path.join(SRV_ROOT_DIR, "spm")

SPM_FORMULA_PATH = __generated_syspaths.SPM_FORMULA_PATH
if SPM_FORMULA_PATH is None:
    SPM_FORMULA_PATH = os.path.join(SPM_PARENT_PATH, "salt")

SPM_PILLAR_PATH = __generated_syspaths.SPM_PILLAR_PATH
if SPM_PILLAR_PATH is None:
    SPM_PILLAR_PATH = os.path.join(SPM_PARENT_PATH, "pillar")

SPM_REACTOR_PATH = __generated_syspaths.SPM_REACTOR_PATH
if SPM_REACTOR_PATH is None:
    SPM_REACTOR_PATH = os.path.join(SPM_PARENT_PATH, "reactor")

HOME_DIR = __generated_syspaths.HOME_DIR
if HOME_DIR is None:
    HOME_DIR = os.path.expanduser("~")


__all__ = [
    "ROOT_DIR",
    "SHARE_DIR",
    "CONFIG_DIR",
    "CACHE_DIR",
    "SOCK_DIR",
    "SRV_ROOT_DIR",
    "BASE_FILE_ROOTS_DIR",
    "BASE_PILLAR_ROOTS_DIR",
    "BASE_MASTER_ROOTS_DIR",
    "BASE_THORIUM_ROOTS_DIR",
    "LOGS_DIR",
    "PIDFILE_DIR",
    "INSTALL_DIR",
    "CLOUD_DIR",
    "BOOTSTRAP",
    "SPM_PARENT_PATH",
    "SPM_FORMULA_PATH",
    "SPM_PILLAR_PATH",
    "SPM_REACTOR_PATH",
]
