# -*- coding: utf-8 -*-
"""
A module that adds data to the Pillar structure retrieved by an http request


Configuring the HTTP_JSON ext_pillar
====================================

Set the following Salt config to setup Foreman as external pillar source:

.. code-block:: json

  ext_pillar:
    - http_json:
        url: http://example.com/api/minion_id
        ::TODO::
        username: username
        password: password

Module Documentation
====================
"""
from __future__ import absolute_import

# Import python libs
import logging


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               url=None):
    """
    Read pillar data from HTTP response.

    :param url String to make request
    :returns dict with pillar data to add
    :returns empty if error
    """
    # Set up logging
    log = logging.getLogger(__name__)

    data = __salt__['http.query'](url=url, decode=True, decode_type='json')

    if 'dict' in data:
        return data['dict']

    log.error('Error caught on query to' + url + '\nMore Info:\n')

    for k, v in data.iteritems():
        log.error(k + ' : ' + v)

    return {}
