# -*- coding: utf-8 -*-
'''
Module for making calls to the Salt API

.. versionadded:: Fluorine

:configuration:
    The api configuration can be set in the minion / proxy minion config files,
    or via pillars.

    For example:

    .. code-block:: yaml

        salt_api:
          username: luke
          password: fakepassword
          url: https://salt-master:8443
'''
from __future__ import absolute_import

# Import python lib
import json
import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'salt_api'

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    return True

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def runner(fun, async=False, arg=[], eauth='pam', timeout=None, **kwargs):
    '''
    Execute a runner function via the Salt API

    CLI Example:

    .. code-block:: bash

        salt '*' salt_api.runner test.arg test.arg arg="[arg1, arg2]" kwarg1=true kwarg2=false
    '''
    if async is True:
        client = 'runner_async'
    else:
        client = 'runner'

    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    config = __salt__['config.get']('salt_api')
    data = {'eauth': eauth,
            'username': config['username'],
            'password': config['password'],
            'client': client,
            'fun': fun,
            'arg': arg,
            'timeout': timeout,
            'kwarg': kwargs}

    return salt.utils.http.query('{}/run'.format(config['url']),
                                 method='POST',
                                 data=json.dumps(data),
                                 header_dict=headers,
                                 decode=True,
                                 status=True)
