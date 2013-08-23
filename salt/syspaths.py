# -*- coding: utf-8 -*-
'''
    salt.syspaths
    ~~~~~~~~~~~~~

    Salt's defaults system paths

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import sys
import os.path

try:
    # Let's try loading the system paths from the generated module at
    # installation time.
    from salt._syspaths import (
        ROOT_DIR,
        CONFIG_DIR,
        CACHE_DIR,
        SOCK_DIR,
        BASE_FILE_ROOTS_DIR,
        BASE_PILLAR_ROOTS_DIR,
        BASE_MASTER_ROOTS_DIR,
        LOGS_DIR,
        PIDFILE_DIR,
    )
except ImportError:
    # The installation time was not generated, let's define the default values
    if sys.platform.startswith('win'):
        ROOT_DIR = r'c:\salt' or '/'
        CONFIG_DIR = os.path.join(ROOT_DIR, 'conf')
    else:
        ROOT_DIR = '/'
        CONFIG_DIR = os.path.join(ROOT_DIR, 'etc', 'salt')
    CACHE_DIR = os.path.join(ROOT_DIR, 'var', 'cache', 'salt')
    SOCK_DIR = os.path.join(ROOT_DIR, 'var', 'run', 'salt')
    BASE_FILE_ROOTS_DIR = os.path.join(ROOT_DIR, 'srv', 'salt')
    BASE_PILLAR_ROOTS_DIR = os.path.join(ROOT_DIR, 'srv', 'pillar')
    BASE_MASTER_ROOTS_DIR = os.path.join(ROOT_DIR, 'srv', 'salt-master')
    LOGS_DIR = os.path.join(ROOT_DIR, 'var', 'logs', 'salt')
    PIDFILE_DIR = os.path.join(ROOT_DIR, 'var', 'run')
