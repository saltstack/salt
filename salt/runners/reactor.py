# Import pytohn libs
from __future__ import absolute_import, print_function
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

    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__)

    __jid_event__.fire_event({}, 'salt/reactors/manage/list')

    results = sevent.get_event(wait=30, tag='salt/reactors/manage/list-results')
    reactors = results['reactors']
    return reactors


def add(event, reactors, saltenv='base', test=None):
    '''

    '''
    if isinstance(reactors, string_types):
        reactors = [reactors]

    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__)

    __jid_event__.fire_event({'event': event,
                              'reactors': reactors},
                             'salt/reactors/manage/add')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/add-complete')
    return res['result']


def delete(event, saltenv='base', test=None):
    '''

    '''
    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__)

    __jid_event__.fire_event({'event': event}, 'salt/reactors/manage/delete')

    res = sevent.get_event(wait=30, tag='salt/reactors/manage/delete-complete')
    return res['result']
