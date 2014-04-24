# -*- coding: utf-8 -*-
'''
General management of queues
'''

# Import python libs
from __future__ import print_function

# Import salt libs
import salt.loader
import salt.output


def insert(backend, queue, items):
    '''
    Add one or more items to a queue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.insert'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def delete(backend, queue, items):
    '''
    Delete one or more items to a queue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.delete'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_queues(backend):
    '''
    Return a list of queues in the specified backend.
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_queues'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_length(backend, queue):
    '''
    Provide the number of items in a queue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_length'.format(backend)
    ret = queue_funcs[cmd](queue=queue, items=items)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def list_items(backend, queue):
    '''
    List contents of a queue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.list_items'.format(backend)
    ret = queue_funcs[cmd](queue=queue)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret


def pop(backend, queue, quantity=1):
    '''
    Pop one or more or all items from a queue
    '''
    queue_funcs = salt.loader.queues(__opts__)
    cmd = '{0}.pop'.format(backend)
    ret = queue_funcs[cmd](queue=queue, quantity=quantity)
    salt.output.display_output(ret, 'nested', __opts__)
    return ret
