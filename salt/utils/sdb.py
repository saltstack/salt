# -*- coding: utf-8 -*-
'''
Basic functions for accessing the SDB interface

For configuration options, see the docs for specific sdb
modules.
'''
from __future__ import absolute_import

# Import python libs
import random

# Import salt libs
import salt.loader
from salt.ext.six import string_types
from salt.ext.six.moves import range


def sdb_get(uri, opts, utils=None):
    '''
    Get a value from a db, using a uri in the form of ``sdb://<profile>/<key>``. If
    the uri provided does not start with ``sdb://``, then it will be returned as-is.
    '''
    if not isinstance(uri, string_types) or not uri.startswith('sdb://'):
        return uri

    if utils is None:
        utils = {}

    sdlen = len('sdb://')
    indx = uri.find('/', sdlen)

    if (indx == -1) or len(uri[(indx+1):]) == 0:
        return uri

    profile = opts.get(uri[sdlen:indx], {})
    if not profile:
        profile = opts.get('pillar', {}).get(uri[sdlen:indx], {})
    if 'driver' not in profile:
        return uri

    fun = '{0}.get'.format(profile['driver'])
    query = uri[indx+1:]

    loaded_db = salt.loader.sdb(opts, fun, utils=utils)
    return loaded_db[fun](query, profile=profile)


def sdb_set(uri, value, opts, utils=None):
    '''
    Set a value in a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully set, return ``False``.
    '''
    if not isinstance(uri, string_types) or not uri.startswith('sdb://'):
        return False

    if utils is None:
        utils = {}

    sdlen = len('sdb://')
    indx = uri.find('/', sdlen)

    if (indx == -1) or len(uri[(indx+1):]) == 0:
        return False

    profile = opts.get(uri[sdlen:indx], {})
    if not profile:
        profile = opts.get('pillar', {}).get(uri[sdlen:indx], {})
    if 'driver' not in profile:
        return False

    fun = '{0}.set'.format(profile['driver'])
    query = uri[indx+1:]

    loaded_db = salt.loader.sdb(opts, fun, utils=utils)
    return loaded_db[fun](query, value, profile=profile)


def sdb_delete(uri, opts, utils=None):
    '''
    Delete a value from a db, using a uri in the form of ``sdb://<profile>/<key>``. If
    the uri provided does not start with ``sdb://`` or the value is not successfully
    deleted, return ``False``.
    '''
    if not isinstance(uri, string_types) or not uri.startswith('sdb://'):
        return False

    if utils is None:
        utils = {}

    sdlen = len('sdb://')
    indx = uri.find('/', sdlen)

    if (indx == -1) or len(uri[(indx+1):]) == 0:
        return False

    profile = opts.get(uri[sdlen:indx], {})
    if not profile:
        profile = opts.get('pillar', {}).get(uri[sdlen:indx], {})
    if 'driver' not in profile:
        return False

    fun = '{0}.delete'.format(profile['driver'])
    query = uri[indx+1:]

    loaded_db = salt.loader.sdb(opts, fun, utils=utils)
    return loaded_db[fun](query, profile=profile)


def sdb_get_or_set_hash(uri,
                        opts,
                        length=8,
                        chars='abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)',
                        utils=None):
    '''
    Check if value exists in sdb.  If it does, return, otherwise generate a
    random string and store it.  This can be used for storing secrets in a
    centralized place.
    '''
    if not isinstance(uri, string_types) or not uri.startswith('sdb://'):
        return False

    if utils is None:
        utils = {}

    ret = sdb_get(uri, opts, utils=utils)

    if ret is None:
        val = ''.join([random.SystemRandom().choice(chars) for _ in range(length)])
        sdb_set(uri, val, opts, utils)

    return ret or val
