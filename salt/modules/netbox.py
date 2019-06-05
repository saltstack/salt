# -*- coding: utf-8 -*-
'''
NetBox
======

Module to query NetBox

:codeauthor: Zach Moody <zmoody@do.co>
:maturity:   new
:depends:    pynetbox

The following config should be in the minion config file. In order to
work with ``secrets`` you should provide a token and path to your
private key file:

.. code-block:: yaml

  netbox:
    url: <NETBOX_URL>
    token: <NETBOX_USERNAME_API_TOKEN (OPTIONAL)>
    keyfile: </PATH/TO/NETBOX/KEY (OPTIONAL)>

.. versionadded:: 2018.3.0
'''

from __future__ import absolute_import, print_function, unicode_literals
import logging

from salt.exceptions import CommandExecutionError
from salt.utils.args import clean_kwargs

log = logging.getLogger(__name__)

try:
    import pynetbox
    HAS_PYNETBOX = True
except ImportError:
    HAS_PYNETBOX = False

AUTH_ENDPOINTS = (
    'secrets',
)


def __virtual__():
    '''
    pynetbox must be installed.
    '''
    if not HAS_PYNETBOX:
        return (
            False,
            'The netbox execution module cannot be loaded: '
            'pynetbox library is not installed.'
        )
    else:
        return True


def _config():
    config = __salt__['config.get']('netbox')
    if not config:
        raise CommandExecutionError(
            'NetBox execution module configuration could not be found'
        )
    return config


def _nb_obj(auth_required=False):
    pynb_kwargs = {}
    if auth_required:
        pynb_kwargs['token'] = _config().get('token')
        pynb_kwargs['private_key_file'] = _config().get('keyfile')
    return pynetbox.api(_config().get('url'), **pynb_kwargs)


def _strip_url_field(input_dict):
    if 'url' in input_dict.keys():
        del input_dict['url']
    for k, v in input_dict.items():
        if isinstance(v, dict):
            _strip_url_field(v)
    return input_dict


def filter(app, endpoint, **kwargs):
    '''
    Get a list of items from NetBox.

    .. code-block:: bash

        salt myminion netbox.filter dcim devices status=1 role=router
    '''
    ret = []
    nb = _nb_obj(auth_required=True if app in AUTH_ENDPOINTS else False)
    nb_query = getattr(getattr(nb, app), endpoint).filter(
        **clean_kwargs(**kwargs)
    )
    if nb_query:
        ret = [_strip_url_field(dict(i)) for i in nb_query]
    return sorted(ret)


def get(app, endpoint, id=None, **kwargs):
    '''
    Get a single item from NetBox.

    To get an item based on ID.

    .. code-block:: bash

        salt myminion netbox.get dcim devices id=123

    Or using named arguments that correspond with accepted filters on
    the NetBox endpoint.

    .. code-block:: bash

        salt myminion netbox.get dcim devices name=my-router
    '''
    nb = _nb_obj(auth_required=True if app in AUTH_ENDPOINTS else False)
    if id:
        return dict(getattr(getattr(nb, app), endpoint).get(id))
    else:
        return dict(
            getattr(getattr(nb, app), endpoint).get(**clean_kwargs(**kwargs))
        )
