# -*- coding: utf-8 -*-
'''
Control concurrency of steps within state execution using zookeeper
=========================================================================

This module allows you to "wrap" a state's execution with concurrency control.
This is useful to protect against all hosts executing highstate simultaneously
if your services don't all HUP restart. The common way of protecting against this
is to run in batch mode, but that doesn't protect from another person running
the same batch command (and thereby having 2x the number of nodes deploying at once).

This module will bock while acquiring a slot, meaning that however the command gets
called it will coordinate with zookeeper to ensure that no more than max_concurrency
steps are executing with a single path.

.. code-block:: yaml

    acquire_lock:
      zk_concurrency.lock:
        - zk_hosts: 'zookeeper:2181'
        - path: /trafficserver
        - max_concurrency: 4
        - prereq:
            - service: trafficserver

    trafficserver:
      service.running:
        - watch:
          - file: /etc/trafficserver/records.config

    /etc/trafficserver/records.config:
      file.managed:
        - source: salt://records.config

    release_lock:
      zk_concurrency.unlock:
        - path: /trafficserver
        - require:
            - service: trafficserver

This example would allow the file state to change, but would limit the
concurrency of the trafficserver service restart to 4.
'''

REQUIRED_FUNCS = ('zk_concurrency.lock', 'zk_concurrency.unlock')
__virtualname__ = 'zk_concurrency'


def __virtual__():
    if not all(func in __salt__ for func in REQUIRED_FUNCS):
        return False

    return __virtualname__


def lock(path,
         zk_hosts,
         identifier=None,
         max_concurrency=1,
         timeout=None,
         ephemeral_lease=False,
         ):
    '''
    Block state execution until you are able to get the lock (or hit the timeout)

    '''
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Attempt to acquire lock'
        return ret

    if identifier is None:
        identifier = __grains__['id']

    locked = __salt__['zk_concurrency.lock'](path,
                                             zk_hosts,
                                             identifier=identifier,
                                             max_concurrency=max_concurrency,
                                             timeout=timeout,
                                             ephemeral_lease=ephemeral_lease)
    if locked:
        ret['result'] = True
        ret['comment'] = 'lock acquired'
    else:
        ret['comment'] = 'Unable to acquire lock'

    return ret


def unlock(path,
           zk_hosts=None,  # in case you need to unlock without having run lock (failed execution for example)
           identifier=None,
           max_concurrency=1,
           ephemeral_lease=False
           ):
    '''
    Remove lease from semaphore
    '''
    ret = {'name': path,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Released lock if it is here'
        return ret

    if identifier is None:
        identifier = __grains__['id']

    unlocked = __salt__['zk_concurrency.unlock'](path,
                                                 zk_hosts=zk_hosts,
                                                 identifier=identifier,
                                                 max_concurrency=max_concurrency,
                                                 ephemeral_lease=ephemeral_lease)

    if unlocked:
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to find lease for path {0}'.format(path)

    return ret
