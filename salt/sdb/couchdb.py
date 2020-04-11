# -*- coding: utf-8 -*-
"""
CouchDB sdb Module

:maintainer:    SaltStack
:maturity:      New
:depends:       python2-couchdb
:platform:      all

This allow interaction between Salt and a CouchDB [couchdb.apache.org]
database. It uses salt's `sdb` system to allow for inserts and retrevals
using the `sdb://` prefix in salt configuration files.

To use the couchbase sdb module, it must first be configured in the salt
master or minion config. The following arguments are required:

.. code-block:: yaml

    couchdb_sdb:
      driver: couchdb
      host: localhost
      port: 5984
      database: salt_sdb

One could then query the CouchDB instance via an `sdb://` URI such as the
following:

.. code-block:: yaml

    password: sdb://couchdb_sdb/mykey

To use this interface, you must track IDs on your own or have another source
to do the map-reduce logic necessary to calculate the ID you wish to fetch.

Additional contributions to build true map-reduce functionality into this module
would be welcome.
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libraries
import logging
from uuid import uuid4

# Import Salt libraries
from salt.utils.decorators import memoize

try:
    import couchdb

    HAS_COUCH = True
except ImportError:
    HAS_COUCH = False


log = logging.getLogger(__name__)

# 'set' is a reserved word
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Require the python2-couchdb libraries
    """
    return HAS_COUCH


@memoize
def _construct_uri(profile):
    """
    Examine configuration and return
    a uri for the couchdb server in the following format:

    .. code-block:: bash

        http://localhost:5984/
    """
    return "http://{host}:{port}".format(**profile)


def _get_conn(profile):
    """
    Get a connection to CouchDB
    """
    DEFAULT_BASE_URL = _construct_uri(profile) or "http://localhost:5984"

    server = couchdb.Server()
    if profile["database"] not in server:
        server.create(profile["database"])
    return server


def set_(key, value, profile=None):
    """
    Set a key/value pair in couchdb
    """
    db = _get_db(profile)
    return db.save({"_id": uuid4().hex, key: value})


def get(key, profile=None):
    """
    Get a value from couchdb by id
    """
    db = _get_db(profile)
    return db.get(key)


def _get_db(profile):
    """
    Wraps _get_conn() to return a db
    """
    server = _get_conn(profile)
    db = _get_db(profile)
    return db
