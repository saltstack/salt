# -*- coding: utf-8 -*-
'''
Riak Salt Module
=======================

Author: David Boucha <boucha@gmail.com>

'''

# Import salt libs
import salt.utils

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


def __virtual__():
    '''
    Only available on systems with Riak installed.
    '''
    if salt.utils.which('riak'):
        return 'riak'
    return False


def start():
    '''
    Start Riak

    CLI Example:

    .. code-block:: bash

        salt '*' riak.start
    '''
    return not bool(__salt__['cmd.retcode']('riak start'))


def stop():
    '''
    Stop Riak

    CLI Example:

    .. code-block:: bash

        salt '*' riak.stop
    '''
    return not bool(__salt__['cmd.retcode']('riak stop'))


def cluster_join(riak_user=None, riak_host=None):
    '''
    Join a Riak cluster

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_join <user> <host>
    '''
    if not all((riak_user, riak_host)):
        return False
    return not bool(__salt__['cmd.retcode'](
        'riak-admin cluster join {0}@{1}'.format(riak_user, riak_host))
        )


def cluster_plan():
    '''
    Review Cluster Plan

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_plan
    '''
    return not bool(__salt__['cmd.run']('riak-admin cluster plan'))


def cluster_commit():
    '''
    Commit Cluster Changes

    CLI Example:

    .. code-block:: bash

        salt '*' riak.cluster_commit
    '''
    return not bool(__salt__['cmd.retcode']('riak-admin cluster commit'))


def member_status():
    '''
    Get cluster member status

    CLI Example:

    .. code-block:: bash

        salt '*' riak.member_status
    '''
    ret = {'membership': {},
            'summary': {'Valid': 0,
                        'Leaving': 0,
                        'Exiting': 0,
                        'Joining': 0,
                        'Down': 0,
                        }
            }
    cmd = 'riak-admin member-status'
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if line.startswith(('=', '-', 'Status')):
            continue
        if '/' in line:
            # We're in the summary line
            comps = line.split('/')
            for item in comps:
                key, val = item.split(':')
                ret['summary'][key.strip()] = val.strip()
        vals = line.split()
        if len(vals) == 4:
            # We're on a node status line
            ret['membership'][vals[3]] = {'Status': vals[0],
                                          'Ring': vals[1],
                                          'Pending': vals[2],
                                          }
    return ret


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' riak.help

        salt '*' riak.help status
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
