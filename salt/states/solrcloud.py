"""
States for solrcloud alias and collection configuration

.. versionadded:: 2017.7.0

"""

import salt.utils.json


def alias(name, collections, **kwargs):
    """
    Create alias and enforce collection list.

    Use the solrcloud module to get alias members and set them.

    You can pass additional arguments that will be forwarded to http.query

    name
        The collection name
    collections
        list of collections to include in the alias
    """
    ret = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "",
    }

    if __salt__["solrcloud.alias_exists"](name, **kwargs):
        alias_content = __salt__["solrcloud.alias_get_collections"](name, **kwargs)
        diff = set(alias_content).difference(set(collections))

        if len(diff) == 0:
            ret["result"] = True
            ret["comment"] = "Alias is in desired state"
            return ret

        if __opts__["test"]:
            ret["comment"] = f'The alias "{name}" will be updated.'
            ret["result"] = None
        else:
            __salt__["solrcloud.alias_set_collections"](name, collections, **kwargs)
            ret["comment"] = f'The alias "{name}" has been updated.'
            ret["result"] = True

        ret["changes"] = {
            "old": ",".join(alias_content),
            "new": ",".join(collections),
        }

    else:
        if __opts__["test"]:
            ret["comment"] = f'The alias "{name}" will be created.'
            ret["result"] = None
        else:
            __salt__["solrcloud.alias_set_collections"](name, collections, **kwargs)
            ret["comment"] = f'The alias "{name}" has been created.'
            ret["result"] = True

        ret["changes"] = {
            "old": None,
            "new": ",".join(collections),
        }

    return ret


def collection(name, options=None, **kwargs):
    """
    Create collection and enforce options.

    Use the solrcloud module to get collection parameters.

    You can pass additional arguments that will be forwarded to http.query

    name
        The collection name
    options : {}
        options to ensure
    """
    ret = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "",
    }

    if options is None:
        options = {}

    if __salt__["solrcloud.collection_exists"](name, **kwargs):

        diff = {}

        current_options = __salt__["solrcloud.collection_get_options"](name, **kwargs)

        # Filter options that can be updated
        updatable_options = [
            "maxShardsPerNode",
            "replicationFactor",
            "autoAddReplicas",
            "collection.configName",
            "rule",
            "snitch",
        ]

        options = [k for k in options.items() if k in updatable_options]

        for key, value in options:
            if key not in current_options or current_options[key] != value:
                diff[key] = value

        if len(diff) == 0:
            ret["result"] = True
            ret["comment"] = "Collection options are in desired state"
            return ret

        else:

            if __opts__["test"]:
                ret["comment"] = f'Collection options "{name}" will be changed.'
                ret["result"] = None
            else:
                __salt__["solrcloud.collection_set_options"](name, diff, **kwargs)
                ret["comment"] = 'Parameters were updated for collection "{}".'.format(
                    name
                )
                ret["result"] = True

            ret["changes"] = {
                "old": salt.utils.json.dumps(
                    current_options, sort_keys=True, indent=4, separators=(",", ": ")
                ),
                "new": salt.utils.json.dumps(
                    options, sort_keys=True, indent=4, separators=(",", ": ")
                ),
            }
            return ret

    else:

        new_changes = salt.utils.json.dumps(
            options, sort_keys=True, indent=4, separators=(",", ": ")
        )
        if __opts__["test"]:
            ret["comment"] = f'The collection "{name}" will be created.'
            ret["result"] = None
        else:
            __salt__["solrcloud.collection_create"](name, options, **kwargs)
            ret["comment"] = f'The collection "{name}" has been created.'
            ret["result"] = True

        ret["changes"] = {
            "old": None,
            "new": "options=" + new_changes,
        }

    return ret
