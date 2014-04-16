# -*- coding: utf-8 -*-
'''
Execute chef in server or solo mode
'''

import logging


log = logging.getLogger(__name__)

CHEF_BINARIES = (
   'chef-client',
   'chef-solo',
   'ohai',
)

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if chef is installed
    '''
    if salt.utils.which('chef-client'):
        return 'chef'
    return False


def _check_chef():
    '''
    Checks if chef is installed
    '''
    for _ in CHEF_BINARIES:
        salt.utils.check_or_die(_)


def client(*args, **kwargs):
    '''
    Execute a chef client run and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.client server=https://localhost -l debug
    '''
    _check_chef()
    args += ('chef-client',)
    return __exec_cmd(*args, **kwargs)


def solo(*args, **kwargs):
    '''
    Execute a chef solo run and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.solo config=/etc/chef/solo.rb -l debug
    '''
    _check_chef()
    args += ('chef-solo',)
    return __exec_cmd(*args, **kwargs)


def ohai(*args, **kwargs):
    '''
    Execute a ohai and return a dict with the stderr, stdout,
    return code, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' chef.ohai
    '''
    _check_chef()
    args += ('ohai',)
    return __exec_cmd(*args, **kwargs)


def __exec_cmd(*args, **kwargs):
    cmd = ''.join([arg for arg in args])
    cmd_args = ''.join([
         ' --{0} {1}'.format(k, v) for k, v in kwargs.items() if not k.startswith('__')]
    )
    cmd_exec = "{0} {1}".format(cmd, cmd_args)
    log.debug("ChefCommand: %s", cmd_exec)
    return __salt__['cmd.run'](cmd_exec)
