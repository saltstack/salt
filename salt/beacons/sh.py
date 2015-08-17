# -*- coding: utf-8 -*-
'''
Watch the shell commands being executed actively. This beacon requires strace.
'''

# Import python libs
from __future__ import absolute_import
import time

# Import salt libs
import salt.utils
import salt.utils.vt
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

__virtualname__ = 'sh'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if strace is installed
    '''
    return __virtualname__ if salt.utils.which('strace') else False


def _get_shells():
    '''
    Return the valid shells on this system
    '''
    start = time.time()
    if 'sh.last_shells' in __context__:
        if start - __context__['sh.last_shells'] > 5:
            __context__['sh.last_shells'] = start
        else:
            __context__['sh.shells'] = __salt__['cmd.shells']()
    else:
        __context__['sh.last_shells'] = start
        __context__['sh.shells'] = __salt__['cmd.shells']()
    return __context__['sh.shells']


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for sh beacon should be a list of dicts
    if not isinstance(config, dict):
        log.info('Configuration for sh beacon must be a dictionary.')
        return False
    return True


def beacon(config):
    '''
    Scan the shell execve routines. This beacon will convert all login shells

    .. code-block:: yaml

        beacons:
          sh: {}
    '''
    ret = []
    pkey = 'sh.vt'
    shells = _get_shells()
    ps_out = __salt__['status.procs']()
    track_pids = []
    for pid in ps_out:
        if ps_out[pid].get('cmd', '') in shells:
            track_pids.append(pid)
    if pkey not in __context__:
        __context__[pkey] = {}
    for pid in track_pids:
        if pid not in __context__[pkey]:
            cmd = ['strace', '-f', '-e', 'execve', '-p', '{0}'.format(pid)]
            __context__[pkey][pid] = {}
            __context__[pkey][pid]['vt'] = salt.utils.vt.Terminal(
                    cmd,
                    log_stdout=True,
                    log_stderr=True,
                    stream_stdout=False,
                    stream_stderr=False)
            __context__[pkey][pid]['user'] = ps_out[pid].get('user')
    for pid in __context__[pkey]:
        out = ''
        err = ''
        while __context__[pkey][pid]['vt'].has_unread_data:
            tout, terr = __context__[pkey][pid]['vt'].recv()
            if not terr:
                break
            out += tout
            err += terr
        for line in err.split('\n'):
            event = {'args': [],
                     'tag': pid}
            if 'execve' in line:
                comps = line.split('execve')[1].split('"')
                for ind in range(len(comps)):
                    if ind == 1:
                        event['cmd'] = comps[ind]
                        continue
                    if ind % 2 != 0:
                        event['args'].append(comps[ind])
                event['user'] = __context__[pkey][pid]['user']
                ret.append(event)
        if not __context__[pkey][pid]['vt'].isalive():
            __context__[pkey][pid]['vt'].close()
            __context__[pkey].pop(pid)
    return ret
