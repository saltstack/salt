# -*- coding: utf-8 -*-
'''
This module allows SPM to use sqlite3 as the backend for SPM's package database.

.. versionadded:: 2015.8.0
'''

from __future__ import absolute_import
import os.path
import logging
import sqlite3
import datetime
from sqlite3 import OperationalError
from salt.ext.six.moves import zip

# Get logging started
log = logging.getLogger(__name__)


def init():
    '''
    Get an sqlite3 connection, and initialize the package database if necessary
    '''
    if not os.path.exists(__opts__[u'spm_cache_dir']):
        log.debug(
            u'Creating SPM cache directory at %s', __opts__[u'spm_db'])
        os.makedirs(__opts__[u'spm_cache_dir'])

    if not os.path.exists(__opts__[u'spm_db']):
        log.debug(
            u'Creating new package database at %s', __opts__[u'spm_db'])

    sqlite3.enable_callback_tracebacks(True)
    conn = sqlite3.connect(__opts__[u'spm_db'], isolation_level=None)

    try:
        conn.execute(u'SELECT count(*) FROM packages')
    except OperationalError:
        conn.execute(u'''CREATE TABLE packages (
            package text,
            version text,
            release text,
            installed text,
            os text,
            os_family text,
            dependencies text,
            os_dependencies text,
            os_family_dependencies text,
            summary text,
            description text
        )u''')

    try:
        conn.execute(u'SELECT count(*) FROM files')
    except OperationalError:
        conn.execute(u'''CREATE TABLE files (
            package text,
            path text,
            size real,
            mode text,
            sum text,
            major text,
            minor text,
            linkname text,
            linkpath text,
            uname text,
            gname text,
            mtime text
        )u''')

    return conn


def info(package, conn=None):
    '''
    List info for a package
    '''
    if conn is None:
        conn = init()

    fields = (
        u'package',
        u'version',
        u'release',
        u'installed',
        u'os',
        u'os_family',
        u'dependencies',
        u'os_dependencies',
        u'os_family_dependencies',
        u'summary',
        u'description',
    )
    data = conn.execute(
        u'SELECT {0} FROM packages WHERE package=?'.format(u','.join(fields)),
        (package, )
    )
    row = data.fetchone()
    if not row:
        return None

    formula_def = dict(list(zip(fields, row)))
    formula_def[u'name'] = formula_def[u'package']

    return formula_def


def list_packages(conn=None):
    '''
    List files for an installed package
    '''
    if conn is None:
        conn = init()

    ret = []
    data = conn.execute(u'SELECT package FROM packages')
    for pkg in data.fetchall():
        ret.append(pkg)

    return ret


def list_files(package, conn=None):
    '''
    List files for an installed package
    '''
    if conn is None:
        conn = init()

    data = conn.execute(u'SELECT package FROM packages WHERE package=?', (package, ))
    if not data.fetchone():
        return None

    ret = []
    data = conn.execute(u'SELECT path, sum FROM files WHERE package=?', (package, ))
    for file_ in data.fetchall():
        ret.append(file_)

    return ret


def register_pkg(name, formula_def, conn=None):
    '''
    Register a package in the package database
    '''
    if conn is None:
        conn = init()

    conn.execute(u'INSERT INTO packages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
        name,
        formula_def[u'version'],
        formula_def[u'release'],
        datetime.datetime.utcnow().strftime(u'%a, %d %b %Y %H:%M:%S GMT'),
        formula_def.get(u'os', None),
        formula_def.get(u'os_family', None),
        formula_def.get(u'dependencies', None),
        formula_def.get(u'os_dependencies', None),
        formula_def.get(u'os_family_dependencies', None),
        formula_def[u'summary'],
        formula_def[u'description'],
    ))


def register_file(name, member, path, digest=u'', conn=None):
    '''
    Register a file in the package database
    '''
    if conn is None:
        conn = init()

    conn.execute(u'INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
        name,
        u'{0}/{1}'.format(path, member.path),
        member.size,
        member.mode,
        digest,
        member.devmajor,
        member.devminor,
        member.linkname,
        member.linkpath,
        member.uname,
        member.gname,
        member.mtime
    ))


def unregister_pkg(name, conn=None):
    '''
    Unregister a package from the package database
    '''
    if conn is None:
        conn = init()

    conn.execute(u'DELETE FROM packages WHERE package=?', (name, ))


def unregister_file(path, pkg=None, conn=None):  # pylint: disable=W0612
    '''
    Unregister a file from the package database
    '''
    if conn is None:
        conn = init()

    conn.execute(u'DELETE FROM files WHERE path=?', (path, ))


def db_exists(db_):
    '''
    Check to see whether the file already exists
    '''
    return os.path.exists(db_)
