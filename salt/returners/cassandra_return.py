# -*- coding: utf-8 -*-
"""
Return data to a Cassandra ColumnFamily

Here's an example Keyspace / ColumnFamily setup that works with this
returner::

    create keyspace salt;
    use salt;
    create column family returns
      with key_validation_class='UTF8Type'
      and comparator='UTF8Type'
      and default_validation_class='UTF8Type';

Required python modules: pycassa

  To use the cassandra returner, append '--return cassandra' to the salt command. ex:

    salt '*' test.ping --return cassandra
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.jid

# Import third party libs
from salt.ext import six

try:
    import pycassa  # pylint: disable=import-error

    HAS_PYCASSA = True
except ImportError:
    HAS_PYCASSA = False

log = logging.getLogger(__name__)

__opts__ = {
    "cassandra.servers": ["localhost:9160"],
    "cassandra.keyspace": "salt",
    "cassandra.column_family": "returns",
    "cassandra.consistency_level": "ONE",
}

# Define the module's virtual name
__virtualname__ = "cassandra"


def __virtual__():
    if not HAS_PYCASSA:
        return False, "Could not import cassandra returner; pycassa is not installed."
    return __virtualname__


def returner(ret):
    """
    Return data to a Cassandra ColumnFamily
    """

    consistency_level = getattr(
        pycassa.ConsistencyLevel, __opts__["cassandra.consistency_level"]
    )

    pool = pycassa.ConnectionPool(
        __opts__["cassandra.keyspace"], __opts__["cassandra.servers"]
    )
    ccf = pycassa.ColumnFamily(
        pool,
        __opts__["cassandra.column_family"],
        write_consistency_level=consistency_level,
    )

    columns = {"fun": ret["fun"], "id": ret["id"]}
    if isinstance(ret["return"], dict):
        for key, value in six.iteritems(ret["return"]):
            columns["return.{0}".format(key)] = six.text_type(value)
    else:
        columns["return"] = six.text_type(ret["return"])

    log.debug(columns)
    ccf.insert(ret["jid"], columns)


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    """
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
