# -*- coding: utf-8 -*-
'''
Support for Apache

Please note: The functions in here are OpenSuSE-specific. Placing them in this
separate file will allow them to load only on OpenSuSE-based systems, while still
loading under the ``apache`` namespace.
'''
from __future__ import absolute_import

# Import python libs
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'apache'


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    cmd = _detect_os()
    if salt.utils.which(cmd) and __grains__['os_family'] == 'Suse' and __grains__['os'].startswith('openSUSE'):
        return __virtualname__
    return False


def _detect_os():
    '''
    Apache commands and paths differ depending on packaging
    '''
    # TODO: Add pillar support for the apachectl location
    if __grains__['os_family'] == 'RedHat':
        return 'apachectl'
    elif __grains__['os_family'] == 'Debian' or __grains__['os_family'] == 'Suse':
        return 'apache2ctl'
    else:
        return 'apachectl'


def check_mod_enabled(mod):
    '''
    Checks to see if the specific mod enabled in /etc/sysconfig/apache2 or /etc/apache2/sysconfig.d/loadmodule.conf.

    This will only be functional on OpenSuSE-based operating systems

    CLI Examples:

    .. code-block:: bash

        salt '*' apache.check_mod_enabled status.conf
        salt '*' apache.check_mod_enabled status.load
    '''
    mod = mod.rsplit('.', 1)[0]
    sysconfig_re = "APACHE_MODULES=.*" + mod
    try:
        for line in salt.utils.fopen('/etc/sysconfig/apache2', 'r'):
            if re.search(sysconfig_re,line):
            return True
        if mod in salt.utils.fopen('/etc/apache2/sysconfig.d/loadmodule.conf', 'r').read():
            return True
        else:
            return False
    except IOError:
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
