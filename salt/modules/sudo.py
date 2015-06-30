# -*- coding: utf-8 -*-
'''
Allow for the calling of execution modules via sudo.

This module is invoked by the minion if the ``sudo_user`` minion config is
present.

Example minion config:

.. code-block:: yaml

    sudo_user: saltdev

Once this setting is made, any execution module call done by the minion will be
run under ``sudo -u <sudo_user> salt-call``.  For example, with the above
minion config,

.. code-block:: bash

    salt sudo_minion cmd.run 'cat /etc/sudoers'

is equivalent to

.. code-block:: bash

    sudo -u saltdev salt-call cmd.run 'cat /etc/sudoers'

being run on ``sudo_minion``.
'''
# Import python libs
import json
# Import salt libs
import salt.utils
import salt.syspaths

__virtualname__ = 'sudo'


def __virtual__():
    if salt.utils.which('sudo'):
        return __virtualname__
    return False


def salt_call(runas, fun, *args, **kwargs):
    '''
    Wrap a shell execution out to salt call with sudo

    Example:

    /etc/salt/minion

    .. code-block:: yaml

        sudo_user: saltdev

    .. code-block:: bash

        salt '*' test.ping  # is run as saltdev user
    '''
    cmd = ['sudo',
           '-u', runas,
           'salt-call',
           '--out', 'json',
           '--metadata',
           '-c', salt.syspaths.CONFIG_DIR,
           fun]
    for arg in args:
        cmd.append(arg)
    for key in kwargs:
        cmd.append('{0}={1}'.format(key, kwargs[key]))
    cmd_ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    cmd_meta = json.loads(cmd_ret['stdout'])['local']
    ret = cmd_meta['return']
    __context__['retcode'] = cmd_meta.get('retcode', 0)
    return ret
