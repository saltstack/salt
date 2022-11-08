"""
State module to manage Elasticsearch indices

.. versionadded:: 2015.8.0
.. deprecated:: 2017.7.0
   Use elasticsearch state instead
"""


import logging

log = logging.getLogger(__name__)


def absent(name):
    """
    Ensure that the named index is absent.

    name
        Name of the index to remove
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        index = __salt__["elasticsearch.index_get"](index=name)
        if index and name in index:
            if __opts__["test"]:
                ret["comment"] = "Index {} will be removed".format(name)
                ret["changes"]["old"] = index[name]
                ret["result"] = None
            else:
                ret["result"] = __salt__["elasticsearch.index_delete"](index=name)
                if ret["result"]:
                    ret["comment"] = "Successfully removed index {}".format(name)
                    ret["changes"]["old"] = index[name]
                else:
                    ret[
                        "comment"
                    ] = "Failed to remove index {} for unknown reasons".format(name)
        else:
            ret["comment"] = "Index {} is already absent".format(name)
    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(err)

    return ret


def present(name, definition=None):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2017.3.0
        Marked ``definition`` as optional.

    Ensure that the named index is present.

    name
        Name of the index to add

    definition
        Optional dict for creation parameters as per https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html

    **Example:**

    .. code-block:: yaml

        # Default settings
        mytestindex:
          elasticsearch_index.present

        # Extra settings
        mytestindex2:
          elasticsearch_index.present:
            - definition:
                settings:
                  index:
                    number_of_shards: 10
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        index_exists = __salt__["elasticsearch.index_exists"](index=name)
        if not index_exists:
            if __opts__["test"]:
                ret["comment"] = "Index {} does not exist and will be created".format(
                    name
                )
                ret["changes"] = {"new": definition}
                ret["result"] = None
            else:
                output = __salt__["elasticsearch.index_create"](
                    index=name, body=definition
                )
                if output:
                    ret["comment"] = "Successfully created index {}".format(name)
                    ret["changes"] = {
                        "new": __salt__["elasticsearch.index_get"](index=name)[name]
                    }
                else:
                    ret["result"] = False
                    ret["comment"] = "Cannot create index {}, {}".format(name, output)
        else:
            ret["comment"] = "Index {} is already present".format(name)
    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(err)

    return ret
