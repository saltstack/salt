# -*- coding: utf-8 -*-
"""
This module allows SPM to use sqlite3 as the backend for SPM's package database.

.. versionadded:: 2015.8.0
"""

from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import os
import sqlite3
from sqlite3 import OperationalError

from salt.ext.six.moves import zip

# Get logging started
log = logging.getLogger(__name__)


def init():
    """
    Get an sqlite3 connection, and initialize the package database if necessary
    """
    if not os.path.exists(__opts__["spm_cache_dir"]):
        log.debug("Creating SPM cache directory at %s", __opts__["spm_db"])
        os.makedirs(__opts__["spm_cache_dir"])

    if not os.path.exists(__opts__["spm_db"]):
        log.debug("Creating new package database at %s", __opts__["spm_db"])

    sqlite3.enable_callback_tracebacks(True)
    conn = sqlite3.connect(__opts__["spm_db"], isolation_level=None)

    try:
        conn.execute("SELECT count(*) FROM packages")
    except OperationalError:
        conn.execute(
            """CREATE TABLE packages (
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
        )"""
        )

    try:
        conn.execute("SELECT count(*) FROM files")
    except OperationalError:
        conn.execute(
            """CREATE TABLE files (
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
        )"""
        )

    return conn


def info(package, conn=None):
    """
    List info for a package
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    fields = (
        "package",
        "version",
        "release",
        "installed",
        "os",
        "os_family",
        "dependencies",
        "os_dependencies",
        "os_family_dependencies",
        "summary",
        "description",
    )
    data = conn.execute(
        "SELECT {0} FROM packages WHERE package=?".format(",".join(fields)), (package,)
    )
    row = data.fetchone()
    if close:
        conn.close()
    if not row:
        return None

    formula_def = dict(list(zip(fields, row)))
    formula_def["name"] = formula_def["package"]

    return formula_def


def list_packages(conn=None):
    """
    List files for an installed package
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    ret = []
    data = conn.execute("SELECT package FROM packages")
    for pkg in data.fetchall():
        ret.append(pkg)

    if close:
        conn.close()
    return ret


def list_files(package, conn=None):
    """
    List files for an installed package
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    data = conn.execute("SELECT package FROM packages WHERE package=?", (package,))
    if not data.fetchone():
        if close:
            conn.close()
        return None

    ret = []
    data = conn.execute("SELECT path, sum FROM files WHERE package=?", (package,))
    for file_ in data.fetchall():
        ret.append(file_)
    if close:
        conn.close()

    return ret


def register_pkg(name, formula_def, conn=None):
    """
    Register a package in the package database
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    conn.execute(
        "INSERT INTO packages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            formula_def["version"],
            formula_def["release"],
            datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            formula_def.get("os", None),
            formula_def.get("os_family", None),
            formula_def.get("dependencies", None),
            formula_def.get("os_dependencies", None),
            formula_def.get("os_family_dependencies", None),
            formula_def["summary"],
            formula_def["description"],
        ),
    )
    if close:
        conn.close()


def register_file(name, member, path, digest="", conn=None):
    """
    Register a file in the package database
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    conn.execute(
        "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            "{0}/{1}".format(path, member.path),
            member.size,
            member.mode,
            digest,
            member.devmajor,
            member.devminor,
            member.linkname,
            member.linkpath,
            member.uname,
            member.gname,
            member.mtime,
        ),
    )
    if close:
        conn.close()


def unregister_pkg(name, conn=None):
    """
    Unregister a package from the package database
    """
    if conn is None:
        conn = init()

    conn.execute("DELETE FROM packages WHERE package=?", (name,))


def unregister_file(path, pkg=None, conn=None):  # pylint: disable=W0612
    """
    Unregister a file from the package database
    """
    close = False
    if conn is None:
        close = True
        conn = init()

    conn.execute("DELETE FROM files WHERE path=?", (path,))
    if close:
        conn.close()


def db_exists(db_):
    """
    Check to see whether the file already exists
    """
    return os.path.exists(db_)
