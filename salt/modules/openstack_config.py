# -*- coding: utf-8 -*-
'''
Modify, retrieve, or delete values from OpenStack configuration files.

:maintainer: Jeffrey C. Ollie <jeff@ocjtech.us>
:maturity: new
:depends:
:platform: linux

'''
# Import Salt libs
import salt.utils
import salt.exceptions

from salt.utils.decorators import which as _which

import shlex
import pipes
if hasattr(shlex, 'quote'):
    _quote = shlex.quote
elif hasattr(pipes, 'quote'):
    _quote = pipes.quote
else:
    _quote = None

# Don't shadow built-in's.
__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    if _quote is None:
        return False
    return 'openstack_config'


def _fallback(*args, **kw):
    return 'The "openstack-config" command needs to be installed for this function to work.  Typically this is included in the "openstack-utils" package.'


@_which('openstack-config')
def set_(filename, section, parameter, value):
    '''
    Set a value in an OpenStack configuration file.

    filename
        The full path to the configuration file

    section
        The section in which the parameter will be set

    parameter
        The parameter to change

    value
        The value to set

    CLI Example:

    .. code-block:: bash

        salt-call openstack_config.set /etc/keystone/keystone.conf sql connection foo
    '''

    filename = _quote(filename)
    section = _quote(section)
    parameter = _quote(parameter)
    value = _quote(value)

    result = __salt__['cmd.run_all'](
            'openstack-config --set {0} {1} {2} {3}'.format(
                filename, section, parameter, value
                )
            )

    if result['retcode'] == 0:
        return result['stdout']
    else:
        raise salt.exceptions.CommandExecutionError(result['stderr'])


@_which('openstack-config')
def get(filename, section, parameter):
    '''
    Get a value from an OpenStack configuration file.

    filename
        The full path to the configuration file

    section
        The section from which to search for the parameter

    parameter
        The parameter to return

    CLI Example:

    .. code-block:: bash

        salt-call openstack_config.get /etc/keystone/keystone.conf sql connection

    '''

    filename = _quote(filename)
    section = _quote(section)
    parameter = _quote(parameter)

    result = __salt__['cmd.run_all'](
            'openstack-config --get {0} {1} {2}'.format(
                filename, section, parameter
                )
            )

    if result['retcode'] == 0:
        return result['stdout']
    else:
        raise salt.exceptions.CommandExecutionError(result['stderr'])


@_which('openstack-config')
def delete(filename, section, parameter):
    '''
    Delete a value from an OpenStack configuration file.

    filename
        The full path to the configuration file

    section
        The section from which to delete the parameter

    parameter
        The parameter to delete

    CLI Example:

    .. code-block:: bash

        salt-call openstack_config.delete /etc/keystone/keystone.conf sql connection
    '''

    filename = _quote(filename)
    section = _quote(section)
    parameter = _quote(parameter)

    result = __salt__['cmd.run_all'](
            'openstack-config --del {0} {1} {2}'.format(
                filename, section, parameter
                )
            )

    if result['retcode'] == 0:
        return result['stdout']
    else:
        raise salt.exceptions.CommandExecutionError(result['stderr'])
