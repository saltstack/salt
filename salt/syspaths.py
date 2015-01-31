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

if 'SETUP_DIRNAME' in globals():
    # This is from the exec() call in Salt's setup.py
    _THIS_FILE = os.path.join(SETUP_DIRNAME, 'salt', 'syspaths.py')  # pylint: disable=E0602
else:
    _THIS_FILE = __file__

try:
    # Let's try loading the system paths from the generated module at
    # installation time.
    from salt import _syspaths  # pylint: disable=W0611,E0611,import-error
                                # because pylint thinks that _syspaths is an
                                # attribute of salt.__init__
except ImportError:
    # pylint: disable=too-few-public-methods
    class Empty(object):
        """An empty class to substitute for _syspaths"""
        __slots__ = ()

    # pylint: disable=invalid-name
    _syspaths = Empty()


_PLATFORM = sys.platform.lower()

# These are tuples of an install path settings and a function that
# generates a default value.  Each is processed individually and added to
# __all__ for export.  This makes it so that a all of the install options
# or a sub-set of them can be written to salt/_syspaths.py.  Previously if
# any one option was missing in salt/_syspaths.py then an exception was
# raised and none of the existing settings were used - only defaults.

# WARNING: These must be dependency-ordered!  Notice that ROOT_DIR comes
# before all settings that use it and similarly INSTALL_DIR and CLOUD_DIR.
_SETTINGS = [
    ('ROOT_DIR', lambda: r'c:\salt' if _PLATFORM.startswith('win') else '/'),
    ('CONFIG_DIR', lambda: (
            os.path.join(globals()['ROOT_DIR'], 'conf')
            if _PLATFORM.startswith('win')
            else (
                os.path.join(globals()['ROOT_DIR'], 'usr', 'local', 'etc', 'salt')
                if 'freebsd' in _PLATFORM
                else (
                    os.path.join(globals()['ROOT_DIR'], 'usr', 'pkg', 'etc', 'salt')
                    if 'netbsd' in _PLATFORM
                    else os.path.join(globals()['ROOT_DIR'], 'etc', 'salt')
                    )
                )
            )
     ),
    ('CACHE_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'var', 'cache', 'salt')),
    ('SOCK_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'var', 'run', 'salt')),
    ('SRV_ROOT_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'srv')),
    ('BASE_FILE_ROOTS_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'salt')),
    ('BASE_PILLAR_ROOTS_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'pillar')),
    ('BASE_MASTER_ROOTS_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'salt-master')),
    ('LOGS_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'var', 'log', 'salt')),
    ('PIDFILE_DIR', lambda: os.path.join(globals()['ROOT_DIR'], 'var', 'run')),
    ('INSTALL_DIR', lambda: os.path.dirname(os.path.realpath(_THIS_FILE))),
    ('CLOUD_DIR', lambda: os.path.join(globals()['INSTALL_DIR'], 'cloud')),
    ('BOOTSTRAP', lambda: os.path.join(globals()['CLOUD_DIR'], 'deploy', 'bootstrap-salt.sh')),
]


__all__ = []
for key, val in _SETTINGS:
    globals()[key] = getattr(_syspaths, key, val()) or val()
    __all__.append(key)
