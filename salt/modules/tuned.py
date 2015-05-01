# -*- coding: utf-8 -*-
'''
:maintainer:    Syed Ali <alicsyed@gmail.com>
:maturity:      new
:depends:       cmd.run
:platform:      Linux
'''

# Import Python libs
from __future__ import absolute_import
import re

# Import Salt libs
import salt.utils

__func_alias__ = {
    'list_': 'list',
}

__virtualname__ = 'tuned'


def __virtual__():
    '''
    Check to see if tuned-adm binary is installed on the system

    '''
    tuned_adm = salt.utils.which('tuned-adm')
    if not tuned_adm:
        return False
    return __virtualname__


def list_():
    '''
    List the profiles available

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.list
    '''

    result = __salt__['cmd.run']('tuned-adm list').splitlines()
    result.pop(0)
    result.pop()
    result = [i.lstrip('- ') for i in result]
    return result


def active():
    '''
    Return current active profile

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.active
    '''

    # turn off all profiles
    result = __salt__['cmd.run']('tuned-adm active')
    pattern = re.compile(r'''(?P<stmt>Current active profile:) (?P<profile>\w+.*)''')
    match = re.match(pattern, result)
    return '{0}'.format(match.group('profile'))


def off():
    '''
    Turn off all profiles

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.off
    '''

    # turn off all profiles
    result = __salt__['cmd.retcode']('tuned-adm off')
    if int(result) != 0:
        return False
    return True


def profile(profile_name):
    '''
    Activate specified profile

    CLI Example:

    .. code-block:: bash

        salt '*' tuned.profile virtual-guest
    '''

    # run tuned-adm with the profile specified
    result = __salt__['cmd.retcode']('tuned-adm profile {0}'.format(profile_name))
    if int(result) != 0:
        return False
    return '{0}'.format(profile_name)
