# -*- coding: utf-8 -*-
'''
URL utils
'''

# Import python libs
from __future__ import absolute_import
import re

# Import salt libs
from salt.ext.six.moves.urllib.parse import urlparse, urlunparse  # pylint: disable=import-error,no-name-in-module
import salt.utils


def parse(url):
    '''
    Parse a salt:// URL; return the path and a possible saltenv query.
    '''
    if not url.startswith('salt://'):
        return url, None

    # urlparse will split on valid filename chars such as '?' and '&'
    resource = url.split('salt://', 1)[-1]

    if '?env=' in resource:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        path, saltenv = resource.split('?env=', 1)
    elif '?saltenv=' in resource:
        path, saltenv = resource.split('?saltenv=', 1)
    else:
        path, saltenv = resource, None

    if salt.utils.is_windows():
        path = salt.utils.sanitize_win_path_string(path)

    return path, saltenv


def create(path, saltenv=None):
    '''
    join `path` and `saltenv` into a 'salt://' URL.
    '''
    if salt.utils.is_windows():
        path = salt.utils.sanitize_win_path_string(path)

    query = u'saltenv={0}'.format(saltenv) if saltenv else ''
    url = urlunparse(('file', '', path, '', query, ''))
    return u'salt://{0}'.format(url[len('file:///'):])


def is_escaped(url):
    '''
    test whether `url` is escaped with `|`
    '''
    if salt.utils.is_windows():
        return False

    scheme = urlparse(url).scheme
    if not scheme:
        return url.startswith('|')
    elif scheme == 'salt':
        path, saltenv = parse(url)
        return path.startswith('|')
    else:
        return False


def escape(url):
    '''
    add escape character `|` to `url`
    '''
    if salt.utils.is_windows():
        return url

    scheme = urlparse(url).scheme
    if not scheme:
        if url.startswith('|'):
            return url
        else:
            return u'|{0}'.format(url)
    elif scheme == 'salt':
        path, saltenv = parse(url)
        if path.startswith('|'):
            return create(path, saltenv)
        else:
            return create(u'|{0}'.format(path), saltenv)
    else:
        return url


def unescape(url):
    '''
    remove escape character `|` from `url`
    '''
    if salt.utils.is_windows():
        return url

    scheme = urlparse(url).scheme
    if not scheme:
        return url.lstrip('|')
    elif scheme == 'salt':
        path, saltenv = parse(url)
        return create(path.lstrip('|'), saltenv)
    else:
        return url


def add_env(url, saltenv):
    '''
    append `saltenv` to `url` as a query parameter to a 'salt://' url
    '''
    if not url.startswith('salt://'):
        return url

    path, senv = parse(url)
    return create(path, saltenv)


def split_env(url):
    '''
    remove the saltenv query parameter from a 'salt://' url
    '''
    if not url.startswith('salt://'):
        return url, None

    path, senv = parse(url)
    return create(path), senv


def validate(url, protos):
    '''
    Return true if the passed URL scheme is in the list of accepted protos
    '''
    if urlparse(url).scheme in protos:
        return True
    return False


def strip_proto(url):
    '''
    Return a copy of the string with the protocol designation stripped, if one
    was present.
    '''
    return re.sub('^[^:/]+://', '', url)
