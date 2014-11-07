# -*- coding: utf-8 -*-
'''
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.
'''

# Import salt libs
import salt.output
import salt.utils.http


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
    if 'node' not in kwargs:
        kwargs['node'] = 'master'

    ret = salt.utils.http.query(url=url, opts=__opts__, **kwargs)
    if output:
        return salt.output.out_format(ret, '', __opts__)
    return ret
