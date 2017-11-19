# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.syspaths
    ~~~~~~~~~~~~~

    Salt's defaults system paths

    This module allows defining Salt's default paths at build time by writing a
    ``_syspath.py`` file to the filesystem. This is useful, for example, for
    setting platform-specific defaults that differ from the standard Linux
    paths.

    These values are static values and must be considered as secondary to any
    paths that are set in the master/minion config files.
'''

# Import python libs
from __future__ import absolute_import
import sys
import os.path

# Import Salt libs
from salt.utils.locales import sdecode

__PLATFORM = sys.platform.lower()


try:
    # Let's try loading the system paths from the generated module at
    # installation time.
    import salt._syspaths as __generated_syspaths  # pylint: disable=no-name-in-module
except ImportError:
    import types
    __generated_syspaths = types.ModuleType('salt._syspaths')
    for key in ('ROOT_DIR', 'CONFIG_DIR', 'CACHE_DIR', 'SOCK_DIR',
                'SRV_ROOT_DIR', 'BASE_FILE_ROOTS_DIR', 'HOME_DIR',
                'BASE_PILLAR_ROOTS_DIR', 'BASE_THORIUM_ROOTS_DIR',
                'BASE_MASTER_ROOTS_DIR', 'LOGS_DIR', 'PIDFILE_DIR',
                'SPM_FORMULA_PATH', 'SPM_PILLAR_PATH', 'SPM_REACTOR_PATH',
                'SHARE_DIR'):
        setattr(__generated_syspaths, key, None)


# Let's find out the path of this module
if u'SETUP_DIRNAME' in globals():
    # This is from the exec() call in Salt's setup.py
    __THIS_FILE = os.path.join(SETUP_DIRNAME, u'salt', u'syspaths.py')  # pylint: disable=E0602
else:
    __THIS_FILE = __file__


# These values are always relative to salt's installation directory
INSTALL_DIR = os.path.dirname(os.path.realpath(__THIS_FILE))
CLOUD_DIR = os.path.join(INSTALL_DIR, u'cloud')
BOOTSTRAP = os.path.join(CLOUD_DIR, u'deploy', u'bootstrap-salt.sh')

ROOT_DIR = __generated_syspaths.ROOT_DIR
if ROOT_DIR is None:
    # The installation time value was not provided, let's define the default
    if __PLATFORM.startswith(u'win'):
        ROOT_DIR = sdecode(r'c:\salt')  # future lint: disable=non-unicode-string
    else:
        ROOT_DIR = u'/'

CONFIG_DIR = __generated_syspaths.CONFIG_DIR
if CONFIG_DIR is None:
    if __PLATFORM.startswith(u'win'):
        CONFIG_DIR = os.path.join(ROOT_DIR, u'conf')
    elif u'freebsd' in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, u'usr', u'local', u'etc', u'salt')
    elif u'netbsd' in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, u'usr', u'pkg', u'etc', u'salt')
    elif u'sunos5' in __PLATFORM:
        CONFIG_DIR = os.path.join(ROOT_DIR, u'opt', u'local', u'etc', u'salt')
    else:
        CONFIG_DIR = os.path.join(ROOT_DIR, u'etc', u'salt')

SHARE_DIR = __generated_syspaths.SHARE_DIR
if SHARE_DIR is None:
    if __PLATFORM.startswith(u'win'):
        SHARE_DIR = os.path.join(ROOT_DIR, u'share')
    elif u'freebsd' in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, u'usr', u'local', u'share', u'salt')
    elif u'netbsd' in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, u'usr', u'share', u'salt')
    elif u'sunos5' in __PLATFORM:
        SHARE_DIR = os.path.join(ROOT_DIR, u'usr', u'share', u'salt')
    else:
        SHARE_DIR = os.path.join(ROOT_DIR, u'usr', u'share', u'salt')

CACHE_DIR = __generated_syspaths.CACHE_DIR
if CACHE_DIR is None:
    CACHE_DIR = os.path.join(ROOT_DIR, u'var', u'cache', u'salt')

SOCK_DIR = __generated_syspaths.SOCK_DIR
if SOCK_DIR is None:
    SOCK_DIR = os.path.join(ROOT_DIR, u'var', u'run', u'salt')

SRV_ROOT_DIR = __generated_syspaths.SRV_ROOT_DIR
if SRV_ROOT_DIR is None:
    SRV_ROOT_DIR = os.path.join(ROOT_DIR, u'srv')

BASE_FILE_ROOTS_DIR = __generated_syspaths.BASE_FILE_ROOTS_DIR
if BASE_FILE_ROOTS_DIR is None:
    BASE_FILE_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, u'salt')

BASE_PILLAR_ROOTS_DIR = __generated_syspaths.BASE_PILLAR_ROOTS_DIR
if BASE_PILLAR_ROOTS_DIR is None:
    BASE_PILLAR_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, u'pillar')

BASE_THORIUM_ROOTS_DIR = __generated_syspaths.BASE_THORIUM_ROOTS_DIR
if BASE_THORIUM_ROOTS_DIR is None:
    BASE_THORIUM_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, u'thorium')

BASE_MASTER_ROOTS_DIR = __generated_syspaths.BASE_MASTER_ROOTS_DIR
if BASE_MASTER_ROOTS_DIR is None:
    BASE_MASTER_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, u'salt-master')

LOGS_DIR = __generated_syspaths.LOGS_DIR
if LOGS_DIR is None:
    LOGS_DIR = os.path.join(ROOT_DIR, u'var', u'log', u'salt')

PIDFILE_DIR = __generated_syspaths.PIDFILE_DIR
if PIDFILE_DIR is None:
    PIDFILE_DIR = os.path.join(ROOT_DIR, u'var', u'run')

SPM_FORMULA_PATH = __generated_syspaths.SPM_FORMULA_PATH
if SPM_FORMULA_PATH is None:
    SPM_FORMULA_PATH = os.path.join(SRV_ROOT_DIR, u'spm', u'salt')

SPM_PILLAR_PATH = __generated_syspaths.SPM_PILLAR_PATH
if SPM_PILLAR_PATH is None:
    SPM_PILLAR_PATH = os.path.join(SRV_ROOT_DIR, u'spm', u'pillar')

SPM_REACTOR_PATH = __generated_syspaths.SPM_REACTOR_PATH
if SPM_REACTOR_PATH is None:
    SPM_REACTOR_PATH = os.path.join(SRV_ROOT_DIR, u'spm', u'reactor')

HOME_DIR = __generated_syspaths.HOME_DIR
if HOME_DIR is None:
    HOME_DIR = os.path.expanduser('~')


__all__ = [
    u'ROOT_DIR',
    u'SHARE_DIR',
    u'CONFIG_DIR',
    u'CACHE_DIR',
    u'SOCK_DIR',
    u'SRV_ROOT_DIR',
    u'BASE_FILE_ROOTS_DIR',
    u'BASE_PILLAR_ROOTS_DIR',
    u'BASE_MASTER_ROOTS_DIR',
    u'BASE_THORIUM_ROOTS_DIR',
    u'LOGS_DIR',
    u'PIDFILE_DIR',
    u'INSTALL_DIR',
    u'CLOUD_DIR',
    u'BOOTSTRAP',
    u'SPM_FORMULA_PATH',
    u'SPM_PILLAR_PATH',
    u'SPM_REACTOR_PATH'
]
