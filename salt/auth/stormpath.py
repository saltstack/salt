# -*- coding: utf-8 -*-
'''
Provide authentication using Stormpath.

This driver requires some extra configuration beyond that which Stormpath
normally requires.

.. code-block:: yaml

    stormpath:
      apiid: 1234567890
      apikey: 1234567890/ABCDEF
      # Can use an application ID
      application: 6789012345
      # Or can use a directory ID
      directory: 3456789012
      # But not both

.. versionadded:: 2015.8.0
'''

from __future__ import absolute_import
import json
import base64
import urllib
import salt.utils.http
import logging

log = logging.getLogger(__name__)


def auth(username, password):
    '''
    Authenticate using a Stormpath directory or application
    '''
    apiid = __opts__.get('stormpath', {}).get('apiid', None)
    apikey = __opts__.get('stormpath', {}).get('apikey', None)
    application = __opts__.get('stormpath', {}).get('application', None)
    path = 'https://api.stormpath.com/v1'

    if application is not None:
        path = '{0}/applications/{1}/loginAttempts'.format(path, application)
    else:
        return False

    username = urllib.quote(username)
    data = {
        'type': 'basic',
        'value': base64.b64encode('{0}:{1}'.format(username, password))
    }
    log.debug('{0}:{1}'.format(username, password))
    log.debug(path)
    log.debug(data)
    log.debug(json.dumps(data))

    result = salt.utils.http.query(
        path,
        method='POST',
        username=apiid,
        password=apikey,
        data=json.dumps(data),
        header_dict={'Content-type': 'application/json;charset=UTF-8'},
        decode=False,
        status=True,
        opts=__opts__,
    )
    log.debug(result)
    if result.get('status', 403) == 200:
        return True

    return False
