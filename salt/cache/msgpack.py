# -*- coding: utf-8 -*-
'''
Cache data using msgpack

.. versionadded:: carbon

Expirations can be set in the relevant config file (``/etc/salt/master`` for
the master, ``/etc/salt/cloud`` for Salt Cloud, etc).
'''
from __future__ import absolute_import
import os
import os.path
import logging
import msgpack
import salt.utils
import salt.syspaths
from salt.exceptions import SaltCacheError

log = logging.getLogger(__name__)


def store(bank, key, data):
    '''
    Store information in a msgpack file.

    bank
        The name of the directory, inside the configured cache directory,
        which will hold the data. If slashes are included in the name, then
        they refer to a nested directory structure (meaning, directories will
        be created to accomodate the name).

    key
        The name of the file which will hold the data. This filename will have
        ``.p`` appended to it.

    data
        The data which will be stored in the msgpack file. This data can be
        anything which can be serialized by msgpack.
    '''
    base = os.path.join(salt.syspaths.CACHE_DIR, bank)
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except OSError as exc:
            raise SaltCacheError(
                'The cache directory, {0}, does not exist and could not be '
                'created: {1}'.format(base, exc)
            )

    outfile = os.path.join(base, '{0}.p'.format(key))
    try:
        with salt.utils.fopen(outfile, 'wb') as fh_:
            fh_.write(msgpack.packb(data))
        return True
    except IOError as exc:
        raise SaltCacheError(
            'There was an error writing the cache file, {0}: {1}'.format(
                base, exc
            )
        )


def fetch(bank, key):
    '''
    Fetch information from a msgpack file.

    bank
        The name of the directory, inside the configured cache directory,
        which will hold the data. If slashes are included in the name, then
        they refer to a nested directory structure.

    key
        The name of the file which holds the data. This filename will have
        ``.p`` appended to it.
    '''
    base = os.path.join(salt.syspaths.CACHE_DIR, bank)
    if not os.path.isdir(base):
        log.debug('Cache directory %s does not exist', base)
        return None

    outfile = os.path.join(base, '{0}.p'.format(key))
    try:
        with salt.utils.fopen(outfile, 'rb') as fh_:
            return msgpack.unpack(fh_)
    except IOError as exc:
        log.warn(
            'There was an error reading the cache file, {0}: {1}'.format(
                base, exc
            )
        )
        return None


def updated(bank, key):
    '''
    Return the epoch of the mtime for this cache file
    '''
    base = os.path.join(salt.syspaths.CACHE_DIR, bank)
    if not os.path.isdir(base):
        log.warn('Cache directory %s does not exist', base)
        return None

    outfile = os.path.join(base, '{0}.p'.format(key))
    try:
        return int(os.path.getmtime(base))
    except IOError as exc:
        log.warn(
            'There was an error reading the mtime for, {0}: {1}'.format(
                base, exc
            )
        )
        return None
