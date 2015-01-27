# -*- coding: utf-8 -*-
'''
Support for Apache

Please note: The functions in here are Debian-specific. Placing them in this
separate file will allow them to load only on Debian-based systems, while still
loading under the ``apache`` namespace.
'''
from __future__ import absolute_import

# Import python libs
import os
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'apache'


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    cmd = _detect_os()
    if salt.utils.which(cmd) and __grains__['os_family'] == 'Debian':
        return __virtualname__
    return False


def _detect_os():
    '''
    Apache commands and paths differ depending on packaging
    '''
    # TODO: Add pillar support for the apachectl location
    if __grains__['os_family'] == 'RedHat':
        return 'apachectl'
    elif __grains__['os_family'] == 'Debian':
        return 'apache2ctl'
    else:
        return 'apachectl'


def check_site_enabled(site):
    '''
    Checks to see if the specific Site symlink is in /etc/apache2/sites-enabled.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_site_enabled example.com
    '''
    if os.path.islink('/etc/apache2/sites-enabled/{0}'.format(site)):
        return True
    elif site == 'default' and os.path.islink('/etc/apache2/sites-enabled/000-{0}'.format(site)):
        return True
    else:
        return False


def a2ensite(site):
    '''
    Runs a2ensite for the given site.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2ensite example.com
    '''
    ret = {}
    command = ['a2ensite', site]

    try:
        status = __salt__['cmd.retcode'](command, python_shell=False)
    except Exception as e:
        return e

    ret['Name'] = 'Apache2 Enable Site'
    ret['Site'] = site

    if status == 1:
        ret['Status'] = 'Site {0} Not found'.format(site)
    elif status == 0:
        ret['Status'] = 'Site {0} enabled'.format(site)
    else:
        ret['Status'] = status

    return ret


def a2dissite(site):
    '''
    Runs a2dissite for the given site.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2dissite example.com
    '''
    ret = {}
    command = ['a2dissite', site]

    try:
        status = __salt__['cmd.retcode'](command, python_shell=False)
    except Exception as e:
        return e

    ret['Name'] = 'Apache2 Disable Site'
    ret['Site'] = site

    if status == 256:
        ret['Status'] = 'Site {0} Not found'.format(site)
    elif status == 0:
        ret['Status'] = 'Site {0} disabled'.format(site)
    else:
        ret['Status'] = status

    return ret


def check_mod_enabled(mod):
    '''
    Checks to see if the specific mod symlink is in /etc/apache2/mods-enabled.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_mod_enabled status.conf
        salt '*' apache.check_mod_enabled status.load
    '''
    if os.path.islink('/etc/apache2/mods-enabled/{0}'.format(mod)):
        return True
    elif mod == 'default' and os.path.islink('/etc/apache2/mods-enabled/000-{0}'.format(mod)):
        return True
    else:
        return False


def a2enmod(mod):
    '''
    Runs a2enmod for the given mod.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2enmod vhost_alias
    '''
    ret = {}
    command = ['a2enmod', mod]

    try:
        status = __salt__['cmd.retcode'](command, python_shell=False)
    except Exception as e:
        return e

    ret['Name'] = 'Apache2 Enable Mod'
    ret['Mod'] = mod

    if status == 1:
        ret['Status'] = 'Mod {0} Not found'.format(mod)
    elif status == 0:
        ret['Status'] = 'Mod {0} enabled'.format(mod)
    else:
        ret['Status'] = status

    return ret


def a2dismod(mod):
    '''
    Runs a2dismod for the given mod.

    This will only be functional on Debian-based operating systems (Ubuntu,
    Mint, etc).

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.a2dismod vhost_alias
    '''
    ret = {}
    command = ['a2dismod', mod]

    try:
        status = __salt__['cmd.retcode'](command, python_shell=False)
    except Exception as e:
        return e

    ret['Name'] = 'Apache2 Disable Mod'
    ret['Mod'] = mod

    if status == 256:
        ret['Status'] = 'Mod {0} Not found'.format(mod)
    elif status == 0:
        ret['Status'] = 'Mod {0} disabled'.format(mod)
    else:
        ret['Status'] = status

    return ret
