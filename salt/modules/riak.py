'''
Riak Salt Module
=======================

Author: David Boucha <boucha@gmail.com>

'''

# Import python Libs
import os

# Import salt libs
import salt.utils

def __virtual__():
    '''
    '''
    if salt.utils.which('riak'):
        return 'riak'
    return False

def start():
    '''
    Start riak

    CLI Example::

        salt '*' riak.start
    '''
    return __salt__['cmd.run']('riak start')



def stop():
    '''
    Stop riak

    CLI Example::

        salt '*' riak.stop
    '''
    return __salt__['cmd.run']('riak stop')
