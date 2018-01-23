# -*- coding: utf-8 -*-
'''
General management and processing of queues.
============================================

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

Queued runners
==============

Using the Salt Queues, references to the commandline arguments of other runners
can be saved to be processed later.  The queue runners require a queue backend
that can store json data (default: :mod:`pgjsonb <salt.queues.pgjsonb_queue>`).

Once the queue is setup, the `runner_queue` will need to be configured.

.. code-block:: yaml

    runner_queue:
      queue: runners
      backend: pgjsonb

.. note:: only the queue is required, this defaults to using pgjsonb

Once this is set, then the following can be added to the scheduler on the
master and it will run the specified amount of commands per time period.

.. code-block:: yaml

    schedule:
      runner queue:
        schedule:
          function: queue.process_runner
          minutes: 1
          kwargs:
            quantity: 2

The above configuration will pop 2 runner jobs off the runner queue, and then
run them.  And it will do this every minute, unless there are any jobs that are
still running from the last time the process_runner task was executed.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.loader
from salt.ext import six
from salt.utils.event import get_event, tagify
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


def pop(queue, quantity=1, backend='sqlite', is_runner=False):
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
    ret = queue_funcs[cmd](quantity=quantity, queue=queue, is_runner=is_runner)
    return ret


def process_queue(queue, quantity=1, backend='sqlite', is_runner=False):
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
    event = get_event(
                'master',
                __opts__['sock_dir'],
                __opts__['transport'],
                opts=__opts__,
                listen=False)
    try:
        items = pop(queue=queue, quantity=quantity, backend=backend, is_runner=is_runner)
    except SaltInvocationError as exc:
        error_txt = '{0}'.format(exc)
        __jid_event__.fire_event({'errors': error_txt}, 'progress')
        return False

    data = {'items': items,
            'backend': backend,
            'queue': queue,
            }
    event.fire_event(data, tagify([queue, 'process'], prefix='queue'))
    return data


def __get_queue_opts(queue=None, backend=None):
    '''
    Get consistent opts for the queued runners
    '''
    if queue is None:
        queue = __opts__.get('runner_queue', {}).get('queue')
    if backend is None:
        backend = __opts__.get('runner_queue', {}).get('backend', 'pgjsonb')
    return {'backend': backend,
            'queue': queue}


def insert_runner(fun, args=None, kwargs=None, queue=None, backend=None):
    '''
    Insert a reference to a runner into the queue so that it can be run later.

    fun
        The runner function that is going to be run

    args
        list or comma-seperated string of args to send to fun

    kwargs
        dictionary of keyword arguments to send to fun

    queue
        queue to insert the runner reference into

    backend
        backend that to use for the queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.insert_runner test.stdout_print
        salt-run queue.insert_runner event.send test_insert_runner kwargs='{"data": {"foo": "bar"}}'

    '''
    if args is None:
        args = []
    elif isinstance(args, six.string_types):
        args = args.split(',')
    if kwargs is None:
        kwargs = {}
    queue_kwargs = __get_queue_opts(queue=queue, backend=backend)
    data = {'fun': fun, 'args': args, 'kwargs': kwargs}
    return insert(items=data, **queue_kwargs)


def process_runner(quantity=1, queue=None, backend=None):
    '''
    Process queued runners

    quantity
        number of runners to process

    queue
        queue to insert the runner reference into

    backend
        backend that to use for the queue

    CLI Example:

    .. code-block:: bash

        salt-run queue.process_runner
        salt-run queue.process_runner 5

    '''
    queue_kwargs = __get_queue_opts(queue=queue, backend=backend)
    data = process_queue(quantity=quantity, is_runner=True, **queue_kwargs)
    for job in data['items']:
        __salt__[job['fun']](*job['args'], **job['kwargs'])
