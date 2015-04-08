# -*- coding: utf-8 -*-
'''
Basic functions for accessing the SDB interface

For configuration options, see the docs for specific sdb
modules.
'''
from __future__ import absolute_import
import salt.loader
from salt.ext.six import string_types


def sdb_get(uri, opts):
    '''
    Get a value from a db, using a uri in the form of ``sdb://<profile>/<key>``. If
    the uri provided does not start with ``sdb://``, then it will be returned as-is.
    '''
    if not isinstance(uri, string_types):
        return uri

    if not uri.startswith('sdb://'):
        return uri

    comps = uri.replace('sdb://', '').split('/')

    if len(comps) < 2:
        return uri

    profile = opts.get(comps[0], {})
    if 'driver' not in profile:
        return uri

    fun = '{0}.get'.format(profile['driver'])
    query = comps[1]

    loaded_db = salt.loader.sdb(opts, fun)
    return loaded_db[fun](query, profile=profile)


def sdb_set(uri, value, opts):
    '''
    Set a value in a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully set, return ``False``.
    '''
    if not isinstance(uri, string_types):
        return uri

    if not uri.startswith('sdb://'):
        return False

    comps = uri.replace('sdb://', '').split('/')

    if len(comps) < 2:
        return False

    profile = opts.get(comps[0], {})
    if 'driver' not in profile:
        return False

    fun = '{0}.set'.format(profile['driver'])
    query = comps[1]

    loaded_db = salt.loader.sdb(opts, fun)
    return loaded_db[fun](query, value, profile=profile)
