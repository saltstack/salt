# -*- coding: utf-8 -*-
'''
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.
'''
from __future__ import absolute_import
# Import Python libs
import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def query(url, output=True, **kwargs):
    '''
    Query a resource, and decode the return data

    CLI Example:

    .. code-block:: bash

        salt-run http.query http://somelink.com/
        salt-run http.query http://somelink.com/ method=POST \
            params='key1=val1&key2=val2'
        salt-run http.query http://somelink.com/ method=POST \
            data='<xml>somecontent</xml>'
    '''
    if output is not True:
        log.warn('Output option has been deprecated. Please use --quiet.')
    if 'node' not in kwargs:
        kwargs['node'] = 'master'

    ret = salt.utils.http.query(url=url, opts=__opts__, **kwargs)
    return ret
