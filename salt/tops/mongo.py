"""
Read tops data from a MongoDB collection

:depends: pymongo (for salt-master)

This module will load tops data from a MongoDB collection. It uses the node's id
for lookups.

Salt Master MongoDB Configuration
===============================

The module shares the same base MongoDB connection variables as
:py:mod:`salt.returners.mongo_return`. These variables go in your master
config file.

   * ``mongo.authdb`` - The mongo database to authenticate to. Defaults to ``'salt'``.
   * ``mongo.db`` - The mongo database to connect to. Defaults to ``'salt'``.
   * ``mongo.host`` - The mongo host to connect to. Supports replica sets by
     specifying all hosts in the set, comma-delimited. Defaults to ``'salt'``.
   * ``mongo.port`` - The port that the mongo database is running on. Defaults
     to ``27017``.
   * ``mongo.user`` - The username for connecting to mongo. Only required if
     you are using mongo authentication. Defaults to ``''``.
   * ``mongo.password`` - The password for connecting to mongo. Only required
     if you are using mongo authentication. Defaults to ``''``.
   * ``mongo.ssl`` - Whether to connect via TLS. Defaults to ``False``.

Or single URI:

.. code-block:: yaml

    mongo.uri: URI

where uri is in the format:

.. code-block:: text

    mongodb://[username:password@]host1[:port1][,host2[:port2],...[,hostN[:portN]]][/[database][?options]]

Example:

.. code-block:: text

    mongodb://db1.example.net:27017/mydatabase
    mongodb://db1.example.net:27017,db2.example.net:2500/?replicaSet=test
    mongodb://db1.example.net:27017,db2.example.net:2500/?replicaSet=test&connectTimeoutMS=300000

If URI is provided, the other settings are simply ignored.
More information on URI format can be found in
https://docs.mongodb.com/manual/reference/connection-string/


Configuring the MongoDB Tops Subsystem
====================================

.. code-block:: yaml

  master_tops:
    mongo:
      collection: tops
      id_field: _id
      re_replace: ""
      re_pattern: \\.example\\.com
      states_field: states
      environment_field: environment


Module Documentation
====================
"""

import logging
import re

try:
    import pymongo

    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


__opts__ = {
    "mongo.authdb": "salt",
    "mongo.db": "salt",
    "mongo.host": "salt",
    "mongo.password": "",
    "mongo.port": 27017,
    "mongo.ssl": False,
    "mongo.user": "",
}


def __virtual__():
    if not HAS_PYMONGO:
        return False
    return "mongo"


# Set up logging
log = logging.getLogger(__name__)


def top(**kwargs):
    """
    Connect to a mongo database and read per-node tops data.

    Parameters:
        * `collection`: The MongoDB collection to read data from. Defaults to
          ``'tops'``.
        * `id_field`: The field in the collection that represents an individual
          minion id. Defaults to ``'_id'``.
        * `re_pattern`: If your naming convention in the collection is shorter
          than the minion id, you can use this to trim the name.
          `re_pattern` will be used to match the name, and `re_replace` will
          be used to replace it. Backrefs are supported as they are in the
          Python standard library. If ``None``, no mangling of the name will
          be performed - the collection will be searched with the entire
          minion id. Defaults to ``None``.
        * `re_replace`: Use as the replacement value in node ids matched with
          `re_pattern`. Defaults to ''. Feel free to use backreferences here.
        * `states_field`: The name of the field providing a list of states.
        * `environment_field`: The name of the field providing the environment.
          Defaults to ``environment``.
    """
    host = __opts__["mongo.host"]
    port = __opts__["mongo.port"]
    ssl = __opts__.get("mongo.ssl") or False

    uri = __opts__.get("mongo.uri")
    host = __opts__.get("mongo.host")
    port = __opts__.get("mongo.port") or 27017
    user = __opts__.get("mongo.user")
    password = __opts__.get("mongo.password")

    db = __opts__.get("mongo.db")
    authdb = __opts__.get("mongo.authdb") or db

    collection = __opts__["master_tops"]["mongo"].get("collection", "tops")
    id_field = __opts__["master_tops"]["mongo"].get("id_field", "_id")
    re_pattern = __opts__["master_tops"]["mongo"].get("re_pattern", "")
    re_replace = __opts__["master_tops"]["mongo"].get("re_replace", "")
    states_field = __opts__["master_tops"]["mongo"].get("states_field", "states")
    environment_field = __opts__["master_tops"]["mongo"].get(
        "environment_field", "environment"
    )

    if not uri:
        # Construct URI from other settings
        uri = 'mongodb://'
        if user and password:
            uri += '%s:%s@' % (user, password)
        uri += '%s:%s/%s?authSource=%s&authMechanism=SCRAM-SHA-256' % (host, port, db, authdb)
        if ssl:
            uri += '&tls=true'
        
    pymongo.uri_parser.parse_uri(uri)
    conn = pymongo.MongoClient(uri)
    log.info("connecting to %s for mongo ext_tops", uri)
    mdb = conn.get_database()

    # Do the regex string replacement on the minion id
    minion_id = kwargs["opts"]["id"]
    if re_pattern:
        minion_id = re.sub(re_pattern, re_replace, minion_id)

    log.info(
        "ext_tops.mongo: looking up tops def for {'%s': '%s'} in mongo",
        id_field,
        minion_id,
    )

    result = mdb[collection].find_one(
        {id_field: minion_id}, projection=[states_field, environment_field]
    )
    if result and states_field in result:
        if environment_field in result:
            environment = result[environment_field]
        else:
            environment = "base"
        log.debug("ext_tops.mongo: found document, returning states")
        return {environment: result[states_field]}
    else:
        # If we can't find the minion the database it's not necessarily an
        # error.
        log.debug("ext_tops.mongo: no document found in collection %s", collection)
        return {}
