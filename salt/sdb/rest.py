# -*- coding: utf-8 -*-
'''
Generic REST API SDB Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2015.8.0

This module allows access to a REST interface using an ``sdb://`` URI.

Like all REST modules, the REST module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    my-rest-api:
      driver: rest
      urls:
        url: https://api.github.com/
      keys:
        url: https://api.github.com/users/{{user}}/keys
        requests_lib: True

The ``driver`` refers to the REST module, and must be set to ``rest`` in order
to use this driver. Each of the other items inside this block refers to a
separate set of HTTP items, including a URL and any options associated with it.
The options used here should match the options available in
``salt.utils.http.query()``.

In order to call the ``urls`` item in the example, the following reference can
be made inside a configuration file:

.. code-block:: yaml

    github_urls: sdb://my-rest-api/urls

Key/Value pairs may also be used with this driver, and merged into the URL using
the configured renderer (``jinja``, by default). For instance, in order to use
the ``keys`` item in the example, the following reference can be made:

.. code-block:: yaml

    github_urls: sdb://my-rest-api/keys?user=myuser

This will cause the following URL to actually be called:

.. code-block:: yaml

    https://api.github.com/users/myuser/keys

Key/Value pairs will NOT be passed through as GET data. If GET data needs to be
sent to the URL, then it should be configured in the SDB configuration block.
For instance:

.. code-block:: yaml

    another-rest-api:
      driver: rest
      user_data:
        url: https://api.example.com/users/
        params:
          user: myuser
'''

# import python libs
from __future__ import absolute_import
import logging

import salt.loader
import salt.utils.http as http
from salt.template import compile_template

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def set_(key, value, service=None, profile=None):  # pylint: disable=W0613
    '''
    Set a key/value pair in the REST interface
    '''
    return query(key, value, service, profile)


def get(key, service=None, profile=None):  # pylint: disable=W0613
    '''
    Get a value from the REST interface
    '''
    return query(key, None, service, profile)


def query(key, value=None, service=None, profile=None):  # pylint: disable=W0613
    '''
    Get a value from the REST interface
    '''
    comps = key.split('?')
    key = comps[0]
    key_vars = {}
    for pair in comps[1].split('&'):
        pair_key, pair_val = pair.split('=')
        key_vars[pair_key] = pair_val

    renderer = __opts__.get('renderer', 'yaml_jinja')
    rend = salt.loader.render(__opts__, {})
    blacklist = __opts__.get('renderer_blacklist')
    whitelist = __opts__.get('renderer_whitelist')
    url = compile_template(
        ':string:',
        rend,
        renderer,
        blacklist,
        whitelist,
        input_data=profile[key]['url'],
        **key_vars
    )

    result = http.query(
        url,
        decode=True,
        **key_vars
    )

    return result['dict']
