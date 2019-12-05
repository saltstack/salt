# -*- coding: utf-8 -*-
'''
Module for making various web calls. Primarily designed for webhooks and the
like, but also useful for basic http testing.

.. versionadded:: 2015.5.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import time

try:
    import urllib.request
    HAS_URLLIB_REQUEST = True
except ImportError:
    HAS_URLLIB_REQUEST = False

# Import Salt libs
import salt.utils.http
import salt.utils.path
import salt.utils.hashutils


def query(url, **kwargs):
    '''
    Query a resource, and decode the return data

    Passes through all the parameters described in the
    :py:func:`utils.http.query function <salt.utils.http.query>`:

    .. autofunction:: salt.utils.http.query

    CLI Example:

    .. code-block:: bash

        salt '*' http.query http://somelink.com/
        salt '*' http.query http://somelink.com/ method=POST \
            params='key1=val1&key2=val2'
        salt '*' http.query http://somelink.com/ method=POST \
            data='<xml>somecontent</xml>'
    '''
    opts = __opts__.copy()
    if 'opts' in kwargs:
        opts.update(kwargs['opts'])
        del kwargs['opts']

    return salt.utils.http.query(url=url, opts=opts, **kwargs)


def wait_for_successful_query(url, wait_for=300, **kwargs):
    '''
    Query a resource until a successful response, and decode the return data

    CLI Example:

    .. code-block:: bash

        salt '*' http.wait_for_successful_query http://somelink.com/ wait_for=160
    '''

    starttime = time.time()

    while True:
        caught_exception = None
        result = None
        try:
            result = query(url=url, **kwargs)
            if not result.get('Error') and not result.get('error'):
                return result
        except Exception as exc:
            caught_exception = exc

        if time.time() > starttime + wait_for:
            if not result and caught_exception:
                # workaround pylint bug https://www.logilab.org/ticket/3207
                raise caught_exception  # pylint: disable=E0702

            return result


def update_ca_bundle(target=None, source=None, merge_files=None):
    '''
    Update the local CA bundle file from a URL

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' http.update_ca_bundle
        salt '*' http.update_ca_bundle target=/path/to/cacerts.pem
        salt '*' http.update_ca_bundle source=https://example.com/cacerts.pem

    If the ``target`` is not specified, it will be pulled from the ``ca_cert``
    configuration variable available to the minion. If it cannot be found there,
    it will be placed at ``<<FILE_ROOTS>>/cacerts.pem``.

    If the ``source`` is not specified, it will be pulled from the
    ``ca_cert_url`` configuration variable available to the minion. If it cannot
    be found, it will be downloaded from the cURL website, using an http (not
    https) URL. USING THE DEFAULT URL SHOULD BE AVOIDED!

    ``merge_files`` may also be specified, which includes a string or list of
    strings representing a file or files to be appended to the end of the CA
    bundle, once it is downloaded.

    CLI Example:

    .. code-block:: bash

        salt '*' http.update_ca_bundle merge_files=/path/to/mycert.pem
    '''
    if target is None:
        target = __salt__['config.get']('ca_bundle', None)

    if source is None:
        source = __salt__['config.get']('ca_bundle_url', None)

    return salt.utils.http.update_ca_bundle(
        target, source, __opts__, merge_files
    )


def download(target, source, hash=False, hash_type='sha256'):
    '''
    Download http file to the host file system.

    target
        Absolute path to target file.

    source
        The http source.

    hash: False
        If set to False, the hash of the downloaded file is not verified, else, the hash of the file.

    hash_type: 'sha256'
        The type of the hash.

    CLI Example:

    .. code-block:: bash

        salt '*' http.download /tmp/file.tar.gz http://host/file-123.tar.gz

    '''
    ret = {'Error': "Unable to load the 'urllib.request' library."}
    if HAS_URLLIB_REQUEST:
        if not salt.utils.path.is_absolute(target):
            ret = {'Error': "target: '{}' have to be an absolute path.".format(target)}
        elif salt.utils.path.is_dir(target):
            ret = {'Error': "target: '{}' have to be a file path.".format(target)}
        else:
            if salt.utils.path.is_file(target):
                tar_hash = salt.utils.hashutils.get_hash(target, hash_type)
            else:
                tar_hash = salt.utils.hashutils.random_hash(hash_type=hash_type)

            tmp_file = salt.utils.path.random_tmp_file()
            with urllib.request.urlopen(source) as response:
                __salt__['file.write'](tmp_file, response.read())
            tmp_hash = salt.utils.hashutils.get_hash(tmp_file, hash_type)

            if hash and tmp_hash != hash:
                ret = {'Error': {"Hash not equals": {'wanted': hash, 'present': tmp_hash}}}
            elif tar_hash == tmp_hash:
                ret = {'Success': "{} is already present.".format(target)}
            else:
                __salt__['file.rename'](tmp_file, target)
                ret = {'Success': "{} is present.".format(target), 'Changes': target}

            __salt__['file.remove'](tmp_file)

    return ret
