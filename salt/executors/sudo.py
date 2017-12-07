# -*- coding: utf-8 -*-
'''
Sudo executor module
'''
# Import python libs
from __future__ import absolute_import
import json
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils.path
import salt.syspaths

__virtualname__ = u'sudo'


def __virtual__():
    if salt.utils.path.which(u'sudo') and __opts__.get(u'sudo_user'):
        return __virtualname__
    return False


def execute(opts, data, func, args, kwargs):
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
    cmd = [u'sudo',
           u'-u', opts.get(u'sudo_user'),
           u'salt-call',
           u'--out', u'json',
           u'--metadata',
           u'-c', salt.syspaths.CONFIG_DIR,
           u'--',
           data.get(u'fun')]
    if data[u'fun'] in (u'state.sls', u'state.highstate', u'state.apply'):
        kwargs[u'concurrent'] = True
    for arg in args:
        cmd.append(_cmd_quote(str(arg)))
    for key in kwargs:
        cmd.append(_cmd_quote(u'{0}={1}'.format(key, kwargs[key])))

    cmd_ret = __salt__[u'cmd.run_all'](cmd, use_vt=True, python_shell=False)

    if cmd_ret[u'retcode'] == 0:
        cmd_meta = json.loads(cmd_ret[u'stdout'])[u'local']
        ret = cmd_meta[u'return']
        __context__[u'retcode'] = cmd_meta.get(u'retcode', 0)
    else:
        ret = cmd_ret[u'stderr']
        __context__[u'retcode'] = cmd_ret[u'retcode']

    return ret
