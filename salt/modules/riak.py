'''
Riak Salt Module
=======================

Author: David Boucha <boucha@gmail.com>

'''

# Import salt libs
import salt.utils

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

    CLI Example::

        salt '*' riak.start
    '''
    return __salt__['cmd.retcode']('riak start')


def stop():
    '''
    Stop Riak

    CLI Example::

        salt '*' riak.stop
    '''
    return __salt__['cmd.retcode']('riak stop')


def cluster_join(riak_user=None, riak_host=None):
    '''
    Join a Riak cluster
    
    CLI Example::

        salt '*' riak.cluster_join <user> <host>
    '''
    if not all((riak_user, riak_host)):
        return False
    return __salt__['cmd.retcode']('riak-admin cluster join {0}@{1}'.format(riak_user, riak_host))


def cluster_plan():
    '''
    Review Cluster Plan
    
    CLI Example::

        salt '*' riak.cluster_plan
    '''
    return __salt__['cmd.run']('riak-admin cluster plan')


def cluster_commit():
    '''
    Commit Cluster Changes
    
    CLI Example::

        salt '*' riak.cluster_commit
    '''
    return __salt__['cmd.retcode']('riak-admin cluster commit')


def member_status():
    '''
    Get cluster member status

    CLI Example::

        salt '*' riak.member_status
    '''
    return __salt__['cmd.run']('riak-admin member-status')
