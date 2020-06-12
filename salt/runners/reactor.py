# -*- coding: utf-8 -*-
'''
A convenience system to manage reactors

Beginning in the 2017.7 release, the reactor runner requires that the reactor
system is running.  This is accomplished one of two ways, either
by having reactors configured or by including ``reactor`` in the
engine configuration for the Salt master.

    .. code-block:: yaml

    engines:
        - reactor

'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
import salt.config
import salt.utils.master
import salt.utils.reactor
import salt.syspaths
import salt.utils.event
import salt.utils.process
from salt.ext.six import string_types

log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list',
}


def list_(saltenv='base', test=None):
    '''
    List currently configured reactors

    CLI Example:

    .. code-block:: bash

        salt-run reactor.list
    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    master_key = salt.utils.master.get_master_key('root', __opts__)

    __jid_event__.fire_event({'key': master_key}, 'salt/reactors/manage/list')

    results = sevent.get_event(wait=30, tag='salt/reactors/manage/list-results')
    reactors = results['reactors']
    return reactors


def add(event, reactors, saltenv='base', test=None):
    '''
    Add a new reactor

    CLI Example:

    .. code-block:: bash

        salt-run reactor.add 'salt/cloud/*/destroyed' reactors='/srv/reactor/destroy/*.sls'
    '''
    if isinstance(reactors, string_types):
        reactors = [reactors]

    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    master_key = salt.utils.master.get_master_key('root', __opts__)

    __jid_event__.fire_event({'event': event,
                              'reactors': reactors,
                              'key': master_key},
                             'salt/reactors/manage/add')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/add-complete')
    return res['result']


def delete(event, saltenv='base', test=None):
    '''
    Delete a reactor

    CLI Example:

    .. code-block:: bash

        salt-run reactor.delete 'salt/cloud/*/destroyed'
    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    master_key = salt.utils.master.get_master_key('root', __opts__)

    __jid_event__.fire_event({'event': event, 'key': master_key}, 'salt/reactors/manage/delete')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/delete-complete')
    return res['result']


def is_leader():
    '''
    Return whether the running reactor is acting as a leader (responding to events).

    CLI Example:

    .. code-block:: bash

        salt-run reactor.is_leader
    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    master_key = salt.utils.master.get_master_key('root', __opts__)

    __jid_event__.fire_event({'key': master_key}, 'salt/reactors/manage/is_leader')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/leader/value')
    return res['result']


def set_leader(value=True):
    '''
    Set the current reactor to act as a leader (responding to events). Defaults to True

    CLI Example:

    .. code-block:: bash

        salt-run reactor.set_leader True
    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    master_key = salt.utils.master.get_master_key('root', __opts__)

    __jid_event__.fire_event({'id': __opts__['id'], 'value': value, 'key': master_key}, 'salt/reactors/manage/set_leader')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/leader/value')
    return res['result']
