# -*- coding: utf-8 -*-
'''
Allow for the calling of execution modules via sudo
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

    CLI Example::

        salt '*' sudo.salt_call root test.ping
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
