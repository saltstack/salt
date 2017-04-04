# -*- coding: utf-8 -*-
'''
Cache data in filesystem.

.. versionadded:: 2016.11.0

The ``localfs`` Minion cache module is the default cache module and does not
require any configuration.

Expiration values can be set in the relevant config file (``/etc/salt/master`` for
the master, ``/etc/salt/cloud`` for Salt Cloud, etc).
'''
from __future__ import absolute_import
import logging
import os
import os.path
import shutil
import tempfile

from salt.exceptions import SaltCacheError
import salt.utils
import salt.utils.atomicfile

log = logging.getLogger(__name__)

__func_alias__ = {'list': 'ls'}


def __cachedir(kwargs=None):
    if kwargs and 'cachedir' in kwargs:
        return kwargs['cachedir']
    return __opts__.get('cachedir', salt.syspaths.CACHE_DIR)


def init_kwargs(kwargs):
    return {'cachedir': __cachedir(kwargs)}


def get_storage_id(kwargs):
    return ('localfs', __cachedir(kwargs))


def store(bank, key, data, cachedir):
    '''
    Store information in a file.
    '''
    base = os.path.join(cachedir, os.path.normpath(bank))
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except OSError as exc:
            raise SaltCacheError(
                'The cache directory, {0}, does not exist and could not be '
                'created: {1}'.format(base, exc)
            )

    outfile = os.path.join(base, '{0}.p'.format(key))
    tmpfh, tmpfname = tempfile.mkstemp(dir=base)
    os.close(tmpfh)
    try:
        with salt.utils.fopen(tmpfname, 'w+b') as fh_:
            fh_.write(__context__['serial'].dumps(data))
        # On Windows, os.rename will fail if the destination file exists.
        salt.utils.atomicfile.atomic_rename(tmpfname, outfile)
    except IOError as exc:
        raise SaltCacheError(
            'There was an error writing the cache file, {0}: {1}'.format(
                base, exc
            )
        )


def fetch(bank, key, cachedir):
    '''
    Fetch information from a file.
    '''
    inkey = False
    key_file = os.path.join(cachedir, os.path.normpath(bank), '{0}.p'.format(key))
    if not os.path.isfile(key_file):
        # The bank includes the full filename, and the key is inside the file
        key_file = os.path.join(cachedir, os.path.normpath(bank) + '.p')
        inkey = True

    if not os.path.isfile(key_file):
        log.debug('Cache file "%s" does not exist', key_file)
        return {}
    try:
        with salt.utils.fopen(key_file, 'rb') as fh_:
            if inkey:
                return __context__['serial'].load(fh_)[key]
            else:
                return __context__['serial'].load(fh_)
    except IOError as exc:
        raise SaltCacheError(
            'There was an error reading the cache file "{0}": {1}'.format(
                key_file, exc
            )
        )


def updated(bank, key, cachedir):
    '''
    Return the epoch of the mtime for this cache file
    '''
    key_file = os.path.join(cachedir, os.path.normpath(bank), '{0}.p'.format(key))
    if not os.path.isfile(key_file):
        log.warning('Cache file "%s" does not exist', key_file)
        return None
    try:
        return int(os.path.getmtime(key_file))
    except IOError as exc:
        raise SaltCacheError(
            'There was an error reading the mtime for "{0}": {1}'.format(
                key_file, exc
            )
        )


def flush(bank, key=None, cachedir=None):
    '''
    Remove the key from the cache bank with all the key content.
    '''
    if cachedir is None:
        cachedir = __cachedir()

    try:
        if key is None:
            target = os.path.join(cachedir, os.path.normpath(bank))
            if not os.path.isdir(target):
                return False
            shutil.rmtree(target)
        else:
            target = os.path.join(cachedir, os.path.normpath(bank), '{0}.p'.format(key))
            if not os.path.isfile(target):
                return False
            os.remove(target)
    except OSError as exc:
        raise SaltCacheError(
            'There was an error removing "{0}": {1}'.format(
                target, exc
            )
        )
    return True


def ls(bank, cachedir):
    '''
    Return an iterable object containing all entries stored in the specified bank.
    '''
    base = os.path.join(cachedir, os.path.normpath(bank))
    if not os.path.isdir(base):
        return []
    try:
        items = os.listdir(base)
    except OSError as exc:
        raise SaltCacheError(
            'There was an error accessing directory "{0}": {1}'.format(
                base, exc
            )
        )
    ret = []
    for item in items:
        if item.endswith('.p'):
            ret.append(item.rstrip(item[-2:]))
        else:
            ret.append(item)
    return ret


def contains(bank, key, cachedir):
    '''
    Checks if the specified bank contains the specified key.
    '''
    if key is None:
        base = os.path.join(cachedir, os.path.normpath(bank))
        return os.path.isdir(base)
    else:
        keyfile = os.path.join(cachedir, os.path.normpath(bank), '{0}.p'.format(key))
        return os.path.isfile(keyfile)
