# -*- coding: utf-8 -*-
'''
General management and processing of queues.

This runner facilitates interacting with various queue backends such as the
included sqlite3 queue or the planned AWS SQS and Redis queues

The queue functions such as `insert`, `delete`, and `pop` can be used for
typical management of the queue.

The `process_queue` function pops the requested number of items from the queue
and creates a Salt Event that can then be processed by a Reactor. The
`process_queue` function can be called manually, or can be configured to run on
a schedule with the Salt Scheduler or regular system cron. It is also possible
to use the peer system to allow a minion to call the runner.

This runner, as well as the Queues system, is not api stable at this time.

There are many things that could potentially be done with queues within Salt.
For the time being the focus will be on queueing infrastructure actions on
specific minions. The queues generally will be populated with minion IDs.  When
the `process_queue` runner function is called events are created on the Salt
Event bus that indicate the queue and a list of one or more minion IDs. The
reactor is set up to match on event tags for a specific queue and then take
infrastructure actions on those minion IDs. These actions might be to delete
the minion's key from the master, use salt-cloud to destroy the vm, or some
other custom action.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import

# Import salt libs
import salt.loader
import salt.utils.event
from salt.utils.event import tagify
from salt.exceptions import SaltInvocationError


def insert(queue, items, backend='sqlite'):
    '''
    Add an item or items to a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.insert myqueue myitem
        salt-run queue.insert myqueue "['item1', 'item2', 'item3']"
        salt-run queue.insert myqueue myitem backend=sqlite
        salt-run queue.insert myqueue "['item1', 'item2', 'item3']" backend=sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.insert'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd](items=items, queue=queue)
    return ret


def delete(queue, items, backend='sqlite'):
    '''
    Delete an item or items from a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.delete myqueue myitem
        salt-run queue.delete myqueue myitem backend=sqlite
        salt-run queue.delete myqueue "['item1', 'item2', 'item3']"
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.delete'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd](items=items, queue=queue)
    return ret


def list_queues(backend='sqlite'):
    '''
    Return a list of Salt Queues on the backend

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_queues
        salt-run queue.list_queues backend=sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_queues'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd]()
    return ret


def list_length(queue, backend='sqlite'):
    '''
    Provide the number of items in a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_length myqueue
        salt-run queue.list_length myqueue backend=sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_length'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd](queue=queue)
    return ret


def list_items(queue, backend='sqlite'):
    '''
    List contents of a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_items myqueue
        salt-run queue.list_items myqueue backend=sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_items'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd](queue=queue)
    return ret


def pop(queue, quantity=1, backend='sqlite'):
    '''
    Pop one or more or all items from a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.pop myqueue
        salt-run queue.pop myqueue 6
        salt-run queue.pop myqueue all
        salt-run queue.pop myqueue 6 backend=sqlite
        salt-run queue.pop myqueue all backend=sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.pop'.format(backend)
    if cmd not in queue_funcs:
        raise SaltInvocationError('Function "{0}" is not available'.format(cmd))
    ret = queue_funcs[cmd](quantity=quantity, queue=queue)
    return ret


def process_queue(queue, quantity=1, backend='sqlite'):
    '''
    Pop items off a queue and create an event on the Salt event bus to be
    processed by a Reactor.

    CLI Example:

    .. code-block:: bash

        salt-run queue.process_queue myqueue
        salt-run queue.process_queue myqueue 6
        salt-run queue.process_queue myqueue all backend=sqlite
    '''
    # get ready to send an event
    event = salt.utils.event.get_event(
                'master',
                __opts__['sock_dir'],
                __opts__['transport'],
                opts=__opts__,
                listen=False)
    try:
        items = pop(queue=queue, quantity=quantity, backend=backend)
    except SaltInvocationError as exc:
        error_txt = '{0}'.format(exc)
        __jid_event__.fire_event({'errors': error_txt}, 'progress')
        return False

    data = {'items': items,
            'backend': backend,
            'queue': queue,
            }
    event.fire_event(data, tagify([queue, 'process'], prefix='queue'))
