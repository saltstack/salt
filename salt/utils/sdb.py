# -*- coding: utf-8 -*-
'''
Basic functions for accessing the SDB interface
'''
import salt.loader
from salt._compat import string_types


def sdb_get(uri, opts):
    '''
    Get a value from a db, using a uri in the form of sdb://<profile>/<key>. If
    the uri provided does not start with sdb://, then it will be returned as-is.
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
    Get a value from a db, using a uri in the form of sdb://<profile>/<key>. If
    the uri provided does not start with sdb://, then it will be returned as-is.
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
