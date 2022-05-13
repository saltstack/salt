"""
State module to manage Elasticsearch index templates

.. versionadded:: 2015.8.0
.. deprecated:: 2017.7.0
   Use elasticsearch state instead
"""


import logging

log = logging.getLogger(__name__)


def absent(name):
    """
    Ensure that the named index template is absent.

    name
        Name of the index to remove
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        index_template = __salt__["elasticsearch.index_template_get"](name=name)
        if index_template and name in index_template:
            if __opts__["test"]:
                ret["comment"] = "Index template {} will be removed".format(name)
                ret["changes"]["old"] = index_template[name]
                ret["result"] = None
            else:
                ret["result"] = __salt__["elasticsearch.index_template_delete"](
                    name=name
                )
                if ret["result"]:
                    ret["comment"] = "Successfully removed index template {}".format(
                        name
                    )
                    ret["changes"]["old"] = index_template[name]
                else:
                    ret[
                        "comment"
                    ] = "Failed to remove index template {} for unknown reasons".format(
                        name
                    )
        else:
            ret["comment"] = "Index template {} is already absent".format(name)
    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(err)

    return ret


def present(name, definition):
    """
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2017.3.0
        Marked ``definition`` as required.

    Ensure that the named index templat eis present.

    name
        Name of the index to add

    definition
        Required dict for creation parameters as per https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html

    **Example:**

    .. code-block:: yaml

        mytestindex2_template:
          elasticsearch_index_template.present:
            - definition:
                template: logstash-*
                order: 1
                settings:
                  number_of_shards: 1
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    try:
        index_template_exists = __salt__["elasticsearch.index_template_exists"](
            name=name
        )
        if not index_template_exists:
            if __opts__["test"]:
                ret[
                    "comment"
                ] = "Index template {} does not exist and will be created".format(name)
                ret["changes"] = {"new": definition}
                ret["result"] = None
            else:
                output = __salt__["elasticsearch.index_template_create"](
                    name=name, body=definition
                )
                if output:
                    ret["comment"] = "Successfully created index template {}".format(
                        name
                    )
                    ret["changes"] = {
                        "new": __salt__["elasticsearch.index_template_get"](name=name)[
                            name
                        ]
                    }
                else:
                    ret["result"] = False
                    ret["comment"] = "Cannot create index template {}, {}".format(
                        name, output
                    )
        else:
            ret["comment"] = "Index template {} is already present".format(name)
    except Exception as err:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(err)

    return ret
