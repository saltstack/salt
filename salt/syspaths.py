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
import sys
import os.path

if 'SETUP_DIRNAME' in globals():
    # This is from the exec() call in Salt's setup.py
    THIS_FILE = os.path.join(SETUP_DIRNAME, 'salt', 'syspaths.py')  # pylint: disable=E0602
else:
    THIS_FILE = __file__

try:
    # Let's try loading the system paths from the generated module at
    # installation time.
    from salt._syspaths import (  # pylint: disable=W0611,E0611,import-error
        ROOT_DIR,                 # because pylint thinks that _syspaths is an
        CONFIG_DIR,               # attribute of salt.__init__
        CACHE_DIR,
        SOCK_DIR,
        SRV_ROOT_DIR,
        BASE_FILE_ROOTS_DIR,
        BASE_PILLAR_ROOTS_DIR,
        BASE_MASTER_ROOTS_DIR,
        LOGS_DIR,
        PIDFILE_DIR,
    )
except ImportError:
    # The installation time was not generated, let's define the default values
    __platform = sys.platform.lower()
    if __platform.startswith('win'):
        ROOT_DIR = r'c:\salt' or '/'
        CONFIG_DIR = os.path.join(ROOT_DIR, 'conf')
    else:
        ROOT_DIR = '/'
        if 'freebsd' in __platform:
            CONFIG_DIR = os.path.join(ROOT_DIR, 'usr', 'local', 'etc', 'salt')
        elif 'netbsd' in __platform:
            CONFIG_DIR = os.path.join(ROOT_DIR, 'usr', 'pkg', 'etc', 'salt')
        else:
            CONFIG_DIR = os.path.join(ROOT_DIR, 'etc', 'salt')
    CACHE_DIR = os.path.join(ROOT_DIR, 'var', 'cache', 'salt')
    SOCK_DIR = os.path.join(ROOT_DIR, 'var', 'run', 'salt')
    SRV_ROOT_DIR = os.path.join(ROOT_DIR, 'srv')
    BASE_FILE_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, 'salt')
    BASE_PILLAR_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, 'pillar')
    BASE_MASTER_ROOTS_DIR = os.path.join(SRV_ROOT_DIR, 'salt-master')
    LOGS_DIR = os.path.join(ROOT_DIR, 'var', 'log', 'salt')
    PIDFILE_DIR = os.path.join(ROOT_DIR, 'var', 'run')
    INSTALL_DIR = os.path.dirname(os.path.realpath(THIS_FILE))
    CLOUD_DIR = os.path.join(INSTALL_DIR, 'cloud')
    BOOTSTRAP = os.path.join(CLOUD_DIR, 'deploy', 'bootstrap-salt.sh')
