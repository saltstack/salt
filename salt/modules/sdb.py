# -*- coding: utf-8 -*-
"""
Module for Manipulating Data via the Salt DB API
================================================
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.sdb

__func_alias__ = {
    "set_": "set",
}


def get(uri):
    """
    Get a value from a db, using a uri in the form of sdb://<profile>/<key>. If
    the uri provided does not start with sdb://, then it will be returned as-is.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.get sdb://mymemcached/foo
    """
    return salt.utils.sdb.sdb_get(uri, __opts__, __utils__)


def set_(uri, value):
    """
    Set a value in a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully set, return ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.set sdb://mymemcached/foo bar
    """
    return salt.utils.sdb.sdb_set(uri, value, __opts__, __utils__)


def delete(uri):
    """
    Delete a value from a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully deleted, return ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.delete sdb://mymemcached/foo
    """
    return salt.utils.sdb.sdb_delete(uri, __opts__, __utils__)


def get_or_set_hash(
    uri, length=8, chars="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
):
    """
    Perform a one-time generation of a hash and write it to sdb.
    If that value has already been set return the value instead.

    This is useful for generating passwords or keys that are specific to
    multiple minions that need to be stored somewhere centrally.

    State Example:

    .. code-block:: yaml

        some_mysql_user:
          mysql_user:
            - present
            - host: localhost
            - password: '{{ salt['sdb.get_or_set_hash']('some_mysql_user_pass') }}'

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.get_or_set_hash 'SECRET_KEY' 50

    .. warning::

        This function could return strings which may contain characters which are reserved
        as directives by the YAML parser, such as strings beginning with ``%``. To avoid
        issues when using the output of this function in an SLS file containing YAML+Jinja,
        surround the call with single quotes.
    """
    return salt.utils.sdb.sdb_get_or_set_hash(uri, __opts__, length, chars, __utils__)
