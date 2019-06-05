# -*- coding: utf-8 -*-
'''
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.

.. versionadded:: 2015.5.0
'''
from __future__ import absolute_import, print_function, unicode_literals
# Import Python libs
import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def query(url, output=True, **kwargs):
    '''
    Query a resource, and decode the return data

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run http.query http://somelink.com/
        salt-run http.query http://somelink.com/ method=POST \
            params='key1=val1&key2=val2'
        salt-run http.query http://somelink.com/ method=POST \
            data='<xml>somecontent</xml>'
    '''
    if output is not True:
        log.warning('Output option has been deprecated. Please use --quiet.')
    if 'node' not in kwargs:
        kwargs['node'] = 'master'
    opts = __opts__.copy()
    if 'opts' in kwargs:
        opts.update(kwargs['opts'])
        del kwargs['opts']

    ret = salt.utils.http.query(url=url, opts=opts, **kwargs)
    return ret


def update_ca_bundle(target=None, source=None, merge_files=None):
    '''
    Update the local CA bundle file from a URL

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run http.update_ca_bundle
        salt-run http.update_ca_bundle target=/path/to/cacerts.pem
        salt-run http.update_ca_bundle source=https://example.com/cacerts.pem

    If the ``target`` is not specified, it will be pulled from the ``ca_cert``
    configuration variable available to the master. If it cannot be found there,
    it will be placed at ``<<FILE_ROOTS>>/cacerts.pem``.

    If the ``source`` is not specified, it will be pulled from the
    ``ca_cert_url`` configuration variable available to the master. If it cannot
    be found, it will be downloaded from the cURL website, using an http (not
    https) URL. USING THE DEFAULT URL SHOULD BE AVOIDED!

    ``merge_files`` may also be specified, which includes a string or list of
    strings representing a file or files to be appended to the end of the CA
    bundle, once it is downloaded.

    CLI Example:

    .. code-block:: bash

        salt-run http.update_ca_bundle merge_files=/path/to/mycert.pem
    '''
    return salt.utils.http.update_ca_bundle(
        target, source, __opts__, merge_files
    )
