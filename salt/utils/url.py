# -*- coding: utf-8 -*-
'''
URL utils
'''

# Import python libs
from __future__ import absolute_import
import re
import sys

# Import salt libs
from salt.ext.six.moves.urllib.parse import urlparse, urlunparse  # pylint: disable=import-error,no-name-in-module
import salt.utils
from salt.utils.locales import sdecode


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
            'Carbon',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Carbon.'
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
    path = sdecode(path)

    query = u'saltenv={0}'.format(saltenv) if saltenv else ''
    url = sdecode(urlunparse(('file', '', path, '', query, '')))
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


def add_http_basic_auth(url,
                        user=None,
                        password=None,
                        https_only=False):
    '''
    Return a string with http basic auth incorporated into it
    '''
    if user is None and password is None:
        return url
    else:
        urltuple = urlparse(url)
        if https_only and urltuple.scheme != 'https':
            raise ValueError('Basic Auth only supported for HTTPS')
        if password is None:
            netloc = '{0}@{1}'.format(
                user,
                urltuple.netloc
            )
            urltuple = urltuple._replace(netloc=netloc)
            return urlunparse(urltuple)
        else:
            netloc = '{0}:{1}@{2}'.format(
                user,
                password,
                urltuple.netloc
            )
            urltuple = urltuple._replace(netloc=netloc)
            return urlunparse(urltuple)


def redact_http_basic_auth(output):
    '''
    Remove HTTP user and password
    '''
    # We can't use re.compile because re.compile(someregex).sub() doesn't
    # support flags even in Python 2.7.
    url_re = '(https?)://.*@'
    redacted = r'\1://<redacted>@'
    if sys.version_info >= (2, 7):
        # re.sub() supports flags as of 2.7, use this to do a case-insensitive
        # match.
        return re.sub(url_re, redacted, output, flags=re.IGNORECASE)
    else:
        # We're on python 2.6, test if a lowercased version of the output
        # string matches the regex...
        if re.search(url_re, output.lower()):
            # ... and if it does, perform the regex substitution.
            return re.sub(url_re, redacted, output.lower())
    # No match, just return the original string
    return output
