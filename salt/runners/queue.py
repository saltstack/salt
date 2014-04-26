# -*- coding: utf-8 -*-
'''
General management of queues

This runner facilitates interacting with various queue backends such as the
included sqlite3 queue or the planned AWS SQS and Redis queues

This runner, as well as the Queues system, is not api stable at this time.
'''

# Import python libs
from __future__ import print_function

# Import salt libs
import salt.loader
import salt.output


def insert(backend, queue, items):
    '''
    Add an item or items to a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.insert myqueue sqlite myitem
        salt-run queue.insert myqueue sqlite "['item1', 'item2', 'item3']"
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.insert'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def delete(backend, queue, items):
    '''
    Delete an item or items from a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.delete myqueue sqlite myitem
        salt-run queue.delete myqueue sqlite "['item1', 'item2', 'item3']"
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.delete'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_queues(backend):
    '''
    Return a list of Salt Queues on the backend

    CLI Example:

        salt-run queue.list_queues sqlite
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_queues'.format(backend)
    ret = queue_funcs[cmd]()
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_length(backend, queue):
    '''
    Provide the number of items in a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_length sqlite myqueue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_length'.format(backend)
    ret = queue_funcs[cmd](queue=queue)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_items(backend, queue):
    '''
    List contents of a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.list_items sqlite myqueue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_items'.format(backend)
    ret = queue_funcs[cmd](queue=queue)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def pop(backend, queue, quantity=1):
    '''
    Pop one or more or all items from a queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.pop sqlite myqueue
        salt-run queue.pop sqlite myqueue 6
        salt-run queue.pop sqlite myqueue all
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.pop'.format(backend)
    ret = queue_funcs[cmd](queue=queue, quantity=quantity)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret
