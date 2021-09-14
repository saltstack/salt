"""
Module for manageing PagerDuty resource

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.  The default configuration profile name is 'pagerduty.'

    For example:

    .. code-block:: yaml

        pagerduty:
            pagerduty.api_key: F3Rbyjbve43rfFWf2214
            pagerduty.subdomain: mysubdomain


For PagerDuty API details, see https://developer.pagerduty.com/documentation/rest

"""

import requests
import salt.utils.json


def __virtual__():
    """
    No dependencies outside of what Salt itself requires
    """
    return True


def get_users(profile="pagerduty", subdomain=None, api_key=None):
    """
    List users belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.get_users
    """

    return _list_items(
        "users",
        "id",
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )


def get_services(profile="pagerduty", subdomain=None, api_key=None):
    """
    List services belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.get_services
    """

    return _list_items(
        "services",
        "id",
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )


def get_schedules(profile="pagerduty", subdomain=None, api_key=None):
    """
    List schedules belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.get_schedules
    """

    return _list_items(
        "schedules",
        "id",
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )


def get_escalation_policies(profile="pagerduty", subdomain=None, api_key=None):
    """
    List escalation_policies belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.get_escalation_policies
    """

    return _list_items(
        "escalation_policies",
        "id",
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )


def _list_items(action, key, profile=None, subdomain=None, api_key=None):
    """
    List items belonging to an API call.

    This method should be in utils.pagerduty.
    """
    items = _query(profile=profile, subdomain=subdomain, api_key=api_key, action=action)
    ret = {}
    for item in items[action]:
        ret[item[key]] = item
    return ret


def _query(
    method="GET",
    profile=None,
    url=None,
    path="api/v1",
    action=None,
    api_key=None,
    service=None,
    params=None,
    data=None,
    subdomain=None,
    verify_ssl=True,
):
    """
    Query the PagerDuty API.

    This method should be in utils.pagerduty.

    """

    if profile:
        creds = __salt__["config.option"](profile)
    else:
        creds = {
            "pagerduty.api_key": api_key,
            "pagerduty.subdomain": subdomain,
        }

    if url is None:
        url = "https://{}.pagerduty.com/{}/{}".format(
            creds["pagerduty.subdomain"], path, action
        )

    if params is None:
        params = {}

    if data is None:
        data = {}

    headers = {"Authorization": "Token token={}".format(creds["pagerduty.api_key"])}

    if method != "GET":
        headers["Content-type"] = "application/json"

    result = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        data=salt.utils.json.dumps(data),
        verify=verify_ssl,
    )

    if result.text is None or result.text == "":
        return None
    result_json = result.json()
    # if this query supports pagination, loop and fetch all results, merge them together
    if "total" in result_json and "offset" in result_json and "limit" in result_json:
        offset = result_json["offset"]
        limit = result_json["limit"]
        total = result_json["total"]
        while offset + limit < total:
            offset = offset + limit
            limit = 100
            data["offset"] = offset
            data["limit"] = limit
            next_page_results = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,  # Already serialized above, don't do it again
                verify=verify_ssl,
            ).json()
            offset = next_page_results["offset"]
            limit = next_page_results["limit"]
            # merge results
            for k, v in result_json.items():
                if isinstance(v, list):
                    result_json[k] += next_page_results[k]
    return result_json


def _get_resource_id(resource):
    """
    helper method to find the resource id, since PD API doesn't always return it in the same way
    """
    if "id" in resource:
        return resource["id"]
    if "schedule" in resource:
        return resource["schedule"]["id"]
    return None


def get_resource(
    resource_name,
    key,
    identifier_fields,
    profile="pagerduty",
    subdomain=None,
    api_key=None,
):
    """
    Get any single pagerduty resource by key.

    We allow flexible lookup by any of a list of identifier_fields.
    So, for example, you can look up users by email address or name by calling:

            get_resource('users', key, ['name', 'email'], ...)

    This method is mainly used to translate state sls into pagerduty id's for dependent objects.
    For example, a pagerduty escalation policy contains one or more schedules, which must be passed
    by their pagerduty id.  We look up the schedules by name (using this method), and then translate
    the names into id's.

    This method is implemented by getting all objects of the resource type (cached into __context__),
    then brute force searching through the list and trying to match any of the identifier_fields.
    The __context__ cache is purged after any create, update or delete to the resource.
    """
    # cache the expensive 'get all resources' calls into __context__ so that we do them once per salt run
    if "pagerduty_util.resource_cache" not in __context__:
        __context__["pagerduty_util.resource_cache"] = {}
    if resource_name not in __context__["pagerduty_util.resource_cache"]:
        if resource_name == "services":
            action = resource_name + "?include[]=escalation_policy"
        else:
            action = resource_name
        __context__["pagerduty_util.resource_cache"][resource_name] = _query(
            action=action, profile=profile, subdomain=subdomain, api_key=api_key
        )[resource_name]
    for resource in __context__["pagerduty_util.resource_cache"][resource_name]:
        for field in identifier_fields:
            if resource[field] == key:
                # PagerDuty's /schedules endpoint returns less data than /schedules/:id.
                # so, now that we found the schedule, we need to get all the data for it.
                if resource_name == "schedules":
                    full_resource_info = _query(
                        action="{}/{}".format(resource_name, resource["id"]),
                        profile=profile,
                        subdomain=subdomain,
                        api_key=api_key,
                    )
                    return full_resource_info
                return resource
    return None


def create_or_update_resource(
    resource_name,
    identifier_fields,
    data,
    diff=None,
    profile="pagerduty",
    subdomain=None,
    api_key=None,
):
    """
    create or update any pagerduty resource
    Helper method for present().

    Determining if two resources are the same is different for different PD resource, so this method accepts a diff function.
    The diff function will be invoked as diff(state_information, object_returned_from_pagerduty), and
    should return a dict of data to pass to the PagerDuty update API method, or None if no update
    is to be performed.  If no diff method is provided, the default behavor is to scan the keys in the state_information,
    comparing the matching values in the object_returned_from_pagerduty, and update any values that differ.

    examples:
        create_or_update_resource("user", ["id","name","email"])
        create_or_update_resource("escalation_policies", ["id","name"], diff=my_diff_function)

    """
    # try to locate the resource by any of the identifier_fields that are specified in data
    resource = None
    for field in identifier_fields:
        if field in data:
            resource = get_resource(
                resource_name,
                data[field],
                identifier_fields,
                profile,
                subdomain,
                api_key,
            )
            if resource is not None:
                break

    if resource is None:
        if __opts__["test"]:
            return "would create"
        # flush the resource_cache, because we're modifying a resource
        del __context__["pagerduty_util.resource_cache"][resource_name]
        # create
        return _query(
            method="POST",
            action=resource_name,
            data=data,
            profile=profile,
            subdomain=subdomain,
            api_key=api_key,
        )
    else:
        # update
        data_to_update = {}
        # if differencing function is provided, use it
        if diff:
            data_to_update = diff(data, resource)
        # else default to naive key-value walk of the dicts
        else:
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                resource_value = resource.get(k, None)
                if resource_value is not None and resource_value != v:
                    data_to_update[k] = v
        if len(data_to_update) > 0:
            if __opts__["test"]:
                return "would update"
            # flush the resource_cache, because we're modifying a resource
            del __context__["pagerduty_util.resource_cache"][resource_name]
            resource_id = _get_resource_id(resource)
            return _query(
                method="PUT",
                action="{}/{}".format(resource_name, resource_id),
                data=data_to_update,
                profile=profile,
                subdomain=subdomain,
                api_key=api_key,
            )
        else:
            return True


def delete_resource(
    resource_name,
    key,
    identifier_fields,
    profile="pagerduty",
    subdomain=None,
    api_key=None,
):
    """
    delete any pagerduty resource

    Helper method for absent()

    example:
            delete_resource("users", key, ["id","name","email"]) # delete by id or name or email

    """
    resource = get_resource(
        resource_name, key, identifier_fields, profile, subdomain, api_key
    )
    if resource:
        if __opts__["test"]:
            return "would delete"
        # flush the resource_cache, because we're modifying a resource
        del __context__["pagerduty_util.resource_cache"][resource_name]
        resource_id = _get_resource_id(resource)
        return _query(
            method="DELETE",
            action="{}/{}".format(resource_name, resource_id),
            profile=profile,
            subdomain=subdomain,
            api_key=api_key,
        )
    else:
        return True


def resource_present(
    resource,
    identifier_fields,
    diff=None,
    profile="pagerduty",
    subdomain=None,
    api_key=None,
    **kwargs
):
    """
    Generic resource.present state method.   Pagerduty state modules should be a thin wrapper over this method,
    with a custom diff function.

    This method calls create_or_update_resource() and formats the result as a salt state return value.

    example:
            resource_present("users", ["id","name","email"])
    """

    ret = {"name": kwargs["name"], "changes": {}, "result": None, "comment": ""}
    result = create_or_update_resource(
        resource,
        identifier_fields,
        kwargs,
        diff=diff,
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )
    if result is True:
        pass
    elif result is None:
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = result
    elif "error" in result:
        ret["result"] = False
        ret["comment"] = result
    else:
        ret["result"] = True
        ret["comment"] = result
    return ret


def resource_absent(
    resource,
    identifier_fields,
    profile="pagerduty",
    subdomain=None,
    api_key=None,
    **kwargs
):
    """
    Generic resource.absent state method.   Pagerduty state modules should be a thin wrapper over this method,
    with a custom diff function.

    This method calls delete_resource() and formats the result as a salt state return value.

    example:
            resource_absent("users", ["id","name","email"])
    """
    ret = {"name": kwargs["name"], "changes": {}, "result": None, "comment": ""}
    for k, v in kwargs.items():
        if k not in identifier_fields:
            continue
        result = delete_resource(
            resource,
            v,
            identifier_fields,
            profile=profile,
            subdomain=subdomain,
            api_key=api_key,
        )
        if result is None:
            ret["result"] = True
            ret["comment"] = "{} deleted".format(v)
            return ret
        elif result is True:
            continue
        elif __opts__["test"]:
            ret["comment"] = result
            return ret
        elif "error" in result:
            ret["result"] = False
            ret["comment"] = result
            return ret
    return ret
