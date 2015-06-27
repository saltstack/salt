# -*- coding: utf-8 -*-
'''
A runner module to collect and display the inline documentation from the
various module types
'''
from __future__ import absolute_import
# Import Python libs
import itertools

# Import salt libs
import salt.client
import salt.runner
import salt.wheel
import salt.ext.six as six
from salt.exceptions import SaltClientError


def __virtual__():
    '''
    Always load
    '''
    return True


def runner():
    '''
    Return all inline documentation for runner modules

    CLI Example:

    .. code-block:: bash

        salt-run doc.runner
    '''
    client = salt.runner.RunnerClient(__opts__)
    ret = client.get_docs()
    return ret


def wheel():
    '''
    Return all inline documentation for wheel modules

    CLI Example:

    .. code-block:: bash

        salt-run doc.wheel
    '''
    client = salt.wheel.Wheel(__opts__)
    ret = client.get_docs()
    return ret


def execution():
    '''
    Collect all the sys.doc output from each minion and return the aggregate

    CLI Example:

    .. code-block:: bash

        salt-run doc.execution
    '''
    client = salt.client.get_local_client(__opts__['conf_file'])

    docs = {}
    try:
        for ret in client.cmd_iter('*', 'sys.doc', timeout=__opts__['timeout']):
            for v in six.itervalues(ret):
                docs.update(v)
    except SaltClientError as exc:
        print exc
        return []

    i = itertools.chain.from_iterable([six.iteritems(docs['ret'])])
    ret = dict(list(i))

    return ret


# Still need to modify some of the backend for auth checks to make this work
def __list_functions(user=None):
    '''
    List all of the functions, optionally pass in a user to evaluate
    permissions on
    '''
    client = salt.client.get_local_client(__opts__['conf_file'])
    funcs = {}
    try:
        gener = client.cmd_iter(
                '*',
                'sys.list_functions',
                timeout=__opts__['timeout'])
    except SaltClientError as client_error:
        print client_error
        return funcs

    for ret in gener:
        funcs.update(ret)
    if not user:
        __jid_event__.fire_event({'message': funcs}, 'progress')
        return funcs
    for _, val in __opts__['external_auth'].items():
        if user in val:
            pass
