# -*- coding: utf-8 -*-
'''
Module for configuring Windows Firewall
'''
from __future__ import absolute_import

# Import python libs
import re
import logging

# Import salt libs
import salt.utils
from salt.ext import six

# Define the module's virtual name
__virtualname__ = 'firewall'

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def get_config():
    '''
    Get the status of all the firewall profiles

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_config
    '''
    profiles = {}
    curr = None

    cmd = ['netsh', 'advfirewall', 'show', 'allprofiles']
    for line in __salt__['cmd.run'](cmd, python_shell=False).splitlines():
        if not curr:
            tmp = re.search('(.*) Profile Settings:', line)
            if tmp:
                curr = tmp.group(1)
        elif line.startswith('State'):
            profiles[curr] = line.split()[1] == 'ON'
            curr = None

    return profiles


def disable(profile='allprofiles'):
    '''
    Disable firewall profile :param profile: (default: allprofiles)

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.disable
    '''
    cmd = ['netsh', 'advfirewall', 'set', profile, 'state', 'off']
    return __salt__['cmd.run'](cmd, python_shell=False) == 'Ok.'


def enable(profile='allprofiles'):
    '''
    Enable firewall profile :param profile: (default: allprofiles)

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.enable
    '''
    cmd = ['netsh', 'advfirewall', 'set', profile, 'state', 'on']
    return __salt__['cmd.run'](cmd, python_shell=False) == 'Ok.'


def get_rule(name='all'):
    '''
    .. versionadded:: 2015.5.0

    Get firewall rule(s) info

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_rule 'MyAppPort'
    '''
    ret = {}
    cmd = ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name={0}'.format(name)]
    ret[name] = __salt__['cmd.run'](cmd, python_shell=False)

    if ret[name].strip() == 'No rules match the specified criteria.':
        ret = False

    return ret


def add_rule(name, localport, protocol='tcp', action='allow', dir='in'):
    '''
    .. versionadded:: 2015.5.0

    Add a new firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.add_rule 'test' '8080' 'tcp'
    '''
    cmd = ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
           'name={0}'.format(name),
           'protocol={0}'.format(protocol),
           'dir={0}'.format(dir),
           'localport={0}'.format(localport),
           'action={0}'.format(action)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    if isinstance(ret, six.string_types):
        return ret.strip() == 'Ok.'
    else:
        log.error('firewall.add_rule failed: {0}'.format(ret))
        return False


def delete_rule(name, localport, protocol='tcp', dir='in'):
    '''
    .. versionadded:: 2015.8.0

    Delete an existing firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.delete_rule 'test' '8080' 'tcp' 'in'
    '''
    cmd = ['netsh', 'advfirewall', 'firewall', 'delete', 'rule',
           'name={0}'.format(name),
           'protocol={0}'.format(protocol),
           'dir={0}'.format(dir),
           'localport={0}'.format(localport)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    if isinstance(ret, six.string_types):
        return ret.endswith('Ok.')
    else:
        log.error('firewall.delete_rule failed: {0}'.format(ret))
        return False
