# -*- coding: utf-8 -*-
'''
Use CouchDB as a Pillar source

:depends: requests (for salt-master)

This module will load a node-specific pillar dictionnary from a couchdb
document. It uses the node's id for lookups and will load the full
document as the pillar dictionnary except _id and rev fields.

This module support Cookie and Basic authentication. No authentication
mode is also supported.

Configuring the CouchDB ext_pillar
==================================

.. code-block:: yaml

    ext_pillar:
        - couchdb:
            url: https://couchdb_url.com
            database: salt

The following parameters are optional an determine whether or not
the module will attempt to login before making a call to retrieve
data.

.. code-block:: yaml

    auth_type: 'Basic|Cookie'
    username: ''
    password: ''

Module Documentation
====================
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Set up logging
log = logging.getLogger(__name__)

# Import third party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def __virtual__():
    return HAS_REQUESTS


def ext_pillar(minion_id,
                pillar,
                url,
                database,
                auth_type=None,
                username=None,
                password=None):
    '''
    Query CouchDB API for minion data
    '''
    url = url.rstrip('/')
    headers = {}
    ret = {}

    if username and password:
        if auth_type == 'Cookie':
            log.debug('Getting cookie for authentication')
            headers = _get_cookie_header(url, username, password)
        elif auth_type == 'Basic':
            log.debug('Using basic auth for authentication')
            headers = _get_basic_auth_header(username, password)
        else:
            log.error('Unknow auth_type %s', auth_type)
            return ret
    else:
        log.debug('No username or password supplied so not authenticating')

    # get document from couchdb
    data_string = '{0}/{1}/{2}'.format(url, database, minion_id)
    log.debug('Retrieving document for minion "%s" inside database: %s',
            url, database)
    document_response = requests.get(url=data_string,
                                    headers=headers)
    if document_response.status_code != 200:
        log.error('API query failed for "%s" to retrieve document, status code: %d',
                minion_id, document_response.status_code)
        log.error(document_response.json())
        return ret
    else:
        document = document_response.json()
        del document['_id']
        del document['_rev']
        ret = document
        return ret


def _get_cookie_header(url, username, password):
    '''
    Retrieve a token for cookie authentication using a requeset to /_session
    and return result as a Cookie header. We need to send an Authorization header
    with base64 encoded credentials and a username / password payalod.
    '''
    log.debug('Connecting to %s for couchdb ext_pillar as %s to retrieve a token',
            url, username)
    connection_url = '{0}/_session'.format(url)
    headers = _get_basic_auth_header(username, password)
    login_response = requests.post(url=connection_url,
                                    headers=headers,
                                    data={'name': username, 'password': password})
    if login_response.status_code != 200:
        log.error('API query failed for login, status code: %d',
                login_response.status_code)
        return {}
    # retrieve token from response
    token = login_response.headers['Set-Cookie'].split(';')[0]
    header = {'Cookie': token}

    return header


def _get_basic_auth_header(username, password):
    '''
    Encode username and password for basic authentication and return as an
    Authorization header
    '''
    log.debug('Encoding username and password for basic authentication')
    credentials = '{0}:{1}'.format(username, password).encode('base64')[:-1]
    auth_basic = 'Basic {0}'.format(credentials)
    header = {'Authorization': auth_basic}

    return header
