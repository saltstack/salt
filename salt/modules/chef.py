# -*- coding: utf-8 -*-
'''
Execute chef in server or solo mode
'''

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if chef is installed
    '''
    if salt.utils.which('chef-client'):
        return True
    return False


@decorators.which('chef-client')
def client(*args, **kwargs):
    '''
    Execute a chef client run and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.client server=https://localhost -l debug
    '''
    args += ('chef-client',)
    return __exec_cmd(*args, **kwargs)


@decorators.which('chef-solo')
def solo(*args, **kwargs):
    '''
    Execute a chef solo run and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.solo config=/etc/chef/solo.rb -l debug
    '''
    args += ('chef-solo',)
    return __exec_cmd(*args, **kwargs)


@decorators.which('ohai')
def ohai(*args, **kwargs):
    '''
    Execute a ohai and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.ohai
    '''
    args += ('ohai',)
    return __exec_cmd(*args, **kwargs)


def __exec_cmd(*args, **kwargs):
    cmd = ''.join([arg for arg in args])
    cmd_args = ''.join([
         ' --{0} {1}'.format(k, v) for k, v in kwargs.items() if not k.startswith('__')]
    )
    cmd_exec = '{0} {1}'.format(cmd, cmd_args)
    log.debug('ChefCommand: {0}'.format(cmd_exec))
    return __salt__['cmd.run'](cmd_exec)
