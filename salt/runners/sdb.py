# coding: utf-8
'''
Runner for setting and querying data via the sdb API on the master
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils.sdb


__func_alias__ = {
    'set_': 'set',
}


def get(uri):
    '''
    Get a value from a db, using a uri in the form of sdb://<profile>/<key>. If
    the uri provided does not start with sdb://, then it will be returned as-is.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.get sdb://mymemcached/foo
    '''
    return salt.utils.sdb.sdb_get(uri, __opts__)


def set_(uri, value):
    '''
    Set a value in a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully set, return ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.set sdb://mymemcached/foo bar
    '''
    return salt.utils.sdb.sdb_set(uri, value, __opts__)


def delete(uri):
    '''
    Delete a value from a db, using a uri in the form of ``sdb://<profile>/<key>``.
    If the uri provided does not start with ``sdb://`` or the value is not
    successfully deleted, return ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' sdb.delete sdb://mymemcached/foo
    '''
    return salt.utils.sdb.sdb_delete(uri, __opts__)
