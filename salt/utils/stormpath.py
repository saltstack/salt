# -*- coding: utf-8 -*-
'''
Support for Stormpath

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import, print_function
import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def query(action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None,
           opts=None):
    '''
    Make a web call to Stormpath

    .. versionadded:: 2015.8.0
    '''
    if opts is None:
        opts = {}

    apiid = opts.get('stormpath', {}).get('apiid', None)
    apikey = opts.get('stormpath', {}).get('apikey', None)
    path = 'https://api.stormpath.com/v1/'

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('Stormpath URL: {0}'.format(path))

    if not isinstance(args, dict):
        args = {}

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        username=apiid,
        password=apikey,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        opts=opts,
    )
    log.debug(
        'Stormpath Response Status Code: {0}'.format(
            result['status']
        )
    )

    return [result['status'], result.get('dict', {})]
