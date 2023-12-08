"""
Read Pillar data from a mongodb collection

:depends: pymongo (for salt-master)

This module will load a node-specific pillar dictionary from a mongo
collection. It uses the node's id for lookups and can load either the whole
document, or just a specific field from that
document as the pillar dictionary.

Salt Master Mongo Configuration
===============================

The module shares the same base mongo connection variables as
:py:mod:`salt.returners.mongo_future_return`. These variables go in your master
config file.

.. code-block:: yaml

    mongo.db: <database name>
    mongo.host: <server ip address>
    mongo.user: <MongoDB username>
    mongo.password: <MongoDB user password>
    mongo.port: 27017

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

More information on URI format can be found in
https://docs.mongodb.com/manual/reference/connection-string/

Configuring the Mongo ext_pillar
================================

The Mongo ext_pillar takes advantage of the fact that the Salt Master
configuration file is yaml. It uses a sub-dictionary of values to adjust
specific features of the pillar. This is the explicit single-line dictionary
notation for yaml. One may be able to get the easier-to-read multi-line dict to
work correctly with some experimentation.

.. code-block:: yaml

  ext_pillar:
    - mongo: {collection: vm, id_field: name, re_pattern: \\.example\\.com, fields: [customer_id, software, apache_vhosts]}

In the example above, we've decided to use the ``vm`` collection in the
database to store the data. Minion ids are stored in the ``name`` field on
documents in that collection. And, since minion ids are FQDNs in most cases,
we'll need to trim the domain name in order to find the minion by hostname in
the collection. When we find a minion, return only the ``customer_id``,
``software``, and ``apache_vhosts`` fields, as that will contain the data we
want for a given node. They will be available directly inside the ``pillar``
dict in your SLS templates.


Module Documentation
====================
"""

import logging
import re

import salt.exceptions

try:
    import pymongo

    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


def __virtual__():
    if not HAS_PYMONGO:
        return False
    return "mongo"


# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(
    minion_id,
    pillar,  # pylint: disable=W0613
    collection="pillar",
    id_field="_id",
    re_pattern=None,
    re_replace="",
    fields=None,
):
    """
    Connect to a mongo database and read per-node pillar information.

    Parameters:
        * `collection`: The mongodb collection to read data from. Defaults to
          ``'pillar'``.
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
        * `fields`: The specific fields in the document to use for the pillar
          data. If ``None``, will use the entire document. If using the
          entire document, the ``_id`` field will be converted to string. Be
          careful with other fields in the document as they must be string
          serializable. Defaults to ``None``.
    """

    uri = __opts__.get("mongo.uri")
    host = __opts__.get("mongo.host")
    port = __opts__.get("mongo.port")
    user = __opts__.get("mongo.user")
    password = __opts__.get("mongo.password")
    db = __opts__.get("mongo.db")

    if uri:
        if uri and host:
            raise salt.exceptions.SaltConfigurationError(
                "Mongo ext_pillar expects either uri or host configuration. Both were"
                " provided"
            )
        pymongo.uri_parser.parse_uri(uri)
        conn = pymongo.MongoClient(uri)
        log.info("connecting to %s for mongo ext_pillar", uri)
        mdb = conn.get_database()

    else:
        log.info("connecting to %s:%s for mongo ext_pillar", host, port)
        conn = pymongo.MongoClient(
            host=host, port=port, username=user, password=password
        )

        log.debug("using database '%s'", db)
        mdb = conn[db]

    # Do the regex string replacement on the minion id
    if re_pattern:
        minion_id = re.sub(re_pattern, re_replace, minion_id)

    log.info(
        "ext_pillar.mongo: looking up pillar def for {'%s': '%s'} in mongo",
        id_field,
        minion_id,
    )

    result = mdb[collection].find_one({id_field: minion_id}, projection=fields)
    if result:
        if fields:
            log.debug("ext_pillar.mongo: found document, returning fields '%s'", fields)
        else:
            log.debug("ext_pillar.mongo: found document, returning whole doc")
        if "_id" in result:
            # Converting _id to a string
            # will avoid the most common serialization error cases, but DBRefs
            # and whatnot will still cause problems.
            result["_id"] = str(result["_id"])
        return result
    else:
        # If we can't find the minion the database it's not necessarily an
        # error.
        log.debug("ext_pillar.mongo: no document found in collection %s", collection)
        return {}
