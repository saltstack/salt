# -*- coding: utf-8 -*-
'''
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils.http


def query(url, **kwargs):
    '''
    Query a resource, and decode the return data

    CLI Example:

    .. code-block:: bash

        salt '*' http.query http://somelink.com/
        salt '*' http.query http://somelink.com/ method=POST \
            params='key1=val1&key2=val2'
        salt '*' http.query http://somelink.com/ method=POST \
            data='<xml>somecontent</xml>'
    '''
    return salt.utils.http.query(url=url, opts=__opts__, **kwargs)
