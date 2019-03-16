# -*- coding: utf-8 -*-
'''
A module to pull data from Cobbler via its API into the Pillar dictionary


Configuring the Cobbler ext_pillar
==================================

The same cobbler.* parameters are used for both the Cobbler tops and Cobbler pillar
modules.

.. code-block:: yaml

  ext_pillar:
  - cobbler:
      key: cobbler # Nest results within this key. By default, values are not nested.
      only: [parameters] # Add only these keys to pillar.

  cobbler.url: https://example.com/cobbler_api #default is http://localhost/cobbler_api
  cobbler.user: username # default is no username
  cobbler.password: password # default is no password


Module Documentation
====================
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import salt.ext.six.moves.xmlrpc_client  # pylint: disable=E0611


__opts__ = {'cobbler.url': 'http://localhost/cobbler_api',
            'cobbler.user': None,
            'cobbler.password': None
           }


# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               key=None,
               only=()):
    '''
    Read pillar data from Cobbler via its API.
    '''
    url = __opts__['cobbler.url']
    user = __opts__['cobbler.user']
    password = __opts__['cobbler.password']

    log.info("Querying cobbler at %r for information for %r", url, minion_id)
    try:
        server = salt.ext.six.moves.xmlrpc_client.Server(url, allow_none=True)
        if user:
            server.login(user, password)
        result = server.get_blended_data(None, minion_id)
    except Exception:
        log.exception(
            'Could not connect to cobbler.'
        )
        return {}

    if only:
        result = dict((k, result[k]) for k in only if k in result)

    if key:
        result = {key: result}
    return result
