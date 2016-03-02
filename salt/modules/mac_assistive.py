# -*- coding: utf-8 -*-
'''
This module allows you to manage assistive access on OS X minions with 10.9+

.. code-block:: bash

    salt '*' assistive.install /usr/bin/osascript
'''

# Import Python Libs
from __future__ import absolute_import
from distutils.version import LooseVersion
import re
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'assistive'


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if salt.utils.is_darwin() and LooseVersion(__grains__['osrelease']) >= LooseVersion('10.9'):
        return True
    return False


def install(app_id, enable=True):
    '''
    Install a bundle ID or command as being allowed to use
    assistive access.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.install /usr/bin/osascript
        salt '*' assistive.install com.smileonmymac.textexpander
    '''
    client_type = _client_type(app_id)
    enable_str = '1' if enable else '0'
    cmd = 'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" ' \
          '"INSERT or REPLACE INTO access VALUES(\'kTCCServiceAccessibility\',\'{0}\',{1},{2},1,NULL)"'.\
        format(app_id, client_type, enable_str)

    __salt__['cmd.run'](cmd)
    return True


def installed(app_id):
    '''
    Check if a bundle ID or command is listed in assistive access.
    This will not check to see if it's enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.installed /usr/bin/osascript
        salt '*' assistive.installed com.smileonmymac.textexpander
    '''
    for a in _get_assistive_access():
        if app_id == a[0]:
            return True

    return False


def enable(app_id, enabled=True):
    '''
    Enable or disable an existing assitive access application.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enable /usr/bin/osascript
        salt '*' assistive.enable com.smileonmymac.textexpander enabled=False
    '''
    enable_str = '1' if enabled else '0'
    for a in _get_assistive_access():
        if app_id == a[0]:
            cmd = 'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" ' \
                  '"UPDATE access SET allowed=\'{0}\' WHERE client=\'{1}\'"'.format(enable_str, app_id)

            __salt__['cmd.run'](cmd)

            return True

    return False


def enabled(app_id):
    '''
    Check if a bundle ID or command is listed in assistive access and
    enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' assistive.enabled /usr/bin/osascript
        salt '*' assistive.enabled com.smileonmymac.textexpander
    '''
    for a in _get_assistive_access():
        if app_id == a[0] and a[1] == '1':
            return True

    return False


def _client_type(app_id):
    '''
    Determine whether the given ID is a bundle ID or a
    a path to a command
    '''
    return '1' if app_id[0] == '/' else '0'


def _get_assistive_access():
    '''
    Get a list of all of the assistive access applications installed,
    returns as a ternary showing whether each app is enabled or not.
    '''
    cmd = 'sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" "SELECT * FROM access"'
    out = __salt__['cmd.run'](cmd)
    return re.findall(r'kTCCServiceAccessibility\|(.*)\|[0-9]{1}\|([0-9]{1})\|[0-9]{1}\|', out, re.MULTILINE)
