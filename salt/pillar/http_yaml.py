# -*- coding: utf-8 -*-
'''
A module that adds data to the Pillar structure retrieved by an http request


Configuring the HTTP_YAML ext_pillar
====================================

Set the following Salt config to setup an http endpoint as the external pillar source:

.. code-block:: yaml

  ext_pillar:
    - http_yaml:
        url: http://example.com/api/minion_id
        ::TODO::
        username: username
        password: password

Module Documentation
====================
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt libs
import salt.ext.six as six


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               url):
    """
    Read pillar data from HTTP response.

    :param url String to make request
    :returns dict with pillar data to add
    :returns empty if error
    """
    # Set up logging
    log = logging.getLogger(__name__)

    data = __salt__['http.query'](url=url, decode=True, decode_type='yaml')

    if 'dict' in data:
        return data['dict']

    log.error('Error caught on query to' + url + '\nMore Info:\n')

    for k, v in six.iteritems(data):
        log.error(k + ' : ' + v)

    return {}
