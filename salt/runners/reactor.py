# -*- coding: utf-8 -*-
'''
A convenience system to manage reactors
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
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

    __jid_event__.fire_event({}, 'salt/reactors/manage/list')

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

    __jid_event__.fire_event({'event': event,
                              'reactors': reactors},
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

    __jid_event__.fire_event({'event': event}, 'salt/reactors/manage/delete')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/delete-complete')
    return res['result']
