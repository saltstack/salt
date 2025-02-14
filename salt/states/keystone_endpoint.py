"""
Management of OpenStack Keystone Endpoints
==========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create endpoint:
      keystone_endpoint.present:
        - name: public
        - url: https://example.org:9292
        - region: RegionOne
        - service_name: glance

    destroy endpoint:
      keystone_endpoint.absent:
        - name: public
        - url: https://example.org:9292
        - region: RegionOne
        - service_name: glance

    create multiple endpoints:
      keystone_endpoint.absent:
        - names:
            - public
            - admin
            - internal
        - url: https://example.org:9292
        - region: RegionOne
        - service_name: glance
"""

__virtualname__ = "keystone_endpoint"


def __virtual__():
    if "keystoneng.endpoint_get" in __salt__:
        return __virtualname__
    return (
        False,
        "The keystoneng execution module failed to load: shade python module is not"
        " available",
    )


def _common(ret, name, service_name, kwargs):
    """
    Returns: tuple whose first element is a bool indicating success or failure
             and the second element is either a ret dict for salt or an object
    """
    if "interface" not in kwargs and "public_url" not in kwargs:
        kwargs["interface"] = name
    service = __salt__["keystoneng.service_get"](name_or_id=service_name)

    if not service:
        ret["comment"] = "Cannot find service"
        ret["result"] = False
        return (False, ret)

    filters = kwargs.copy()
    filters.pop("enabled", None)
    filters.pop("url", None)
    filters["service_id"] = service.id
    kwargs["service_name_or_id"] = service.id
    endpoints = __salt__["keystoneng.endpoint_search"](filters=filters)

    if len(endpoints) > 1:
        ret["comment"] = "Multiple endpoints match criteria"
        ret["result"] = False
        return ret
    endpoint = endpoints[0] if endpoints else None
    return (True, endpoint)


def present(name, service_name, auth=None, **kwargs):
    """
    Ensure an endpoint exists and is up-to-date

    name
        Interface name

    url
        URL of the endpoint

    service_name
        Service name or ID

    region
        The region name to assign the endpoint

    enabled
        Boolean to control if endpoint is enabled
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["keystoneng.setup_clouds"](auth)

    success, val = _, endpoint = _common(ret, name, service_name, kwargs)
    if not success:
        return val

    if not endpoint:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Endpoint will be created."
            return ret

        # NOTE(SamYaple): Endpoints are returned as a list which can contain
        # several items depending on the options passed
        endpoints = __salt__["keystoneng.endpoint_create"](**kwargs)
        if len(endpoints) == 1:
            ret["changes"] = endpoints[0]
        else:
            for i, endpoint in enumerate(endpoints):
                ret["changes"][i] = endpoint
        ret["comment"] = "Created endpoint"
        return ret

    changes = __salt__["keystoneng.compare_changes"](endpoint, **kwargs)
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Endpoint will be updated."
            return ret

        kwargs["endpoint_id"] = endpoint.id
        __salt__["keystoneng.endpoint_update"](**kwargs)
        ret["changes"].update(changes)
        ret["comment"] = "Updated endpoint"

    return ret


def absent(name, service_name, auth=None, **kwargs):
    """
    Ensure an endpoint does not exists

    name
        Interface name

    url
        URL of the endpoint

    service_name
        Service name or ID

    region
        The region name to assign the endpoint
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    __salt__["keystoneng.setup_clouds"](auth)

    success, val = _, endpoint = _common(ret, name, service_name, kwargs)
    if not success:
        return val

    if endpoint:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": endpoint.id}
            ret["comment"] = "Endpoint will be deleted."
            return ret

        __salt__["keystoneng.endpoint_delete"](id=endpoint.id)
        ret["changes"]["id"] = endpoint.id
        ret["comment"] = "Deleted endpoint"

    return ret
