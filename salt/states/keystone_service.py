# -*- coding: utf-8 -*-
"""
Management of OpenStack Keystone Services
=========================================

.. versionadded:: 2018.3.0

:depends: shade
:configuration: see :py:mod:`salt.modules.keystoneng` for setup instructions

Example States

.. code-block:: yaml

    create service:
      keystone_service.present:
        - name: glance
        - type: image

    delete service:
      keystone_service.absent:
        - name: glance

    create service with optional params:
      keystone_service.present:
        - name: glance
        - type: image
        - enabled: False
        - description: 'OpenStack Image'
"""

from __future__ import absolute_import, print_function, unicode_literals

__virtualname__ = "keystone_service"


def __virtual__():
    if "keystoneng.service_get" in __salt__:
        return __virtualname__
    return (
        False,
        "The keystoneng execution module failed to load: shade python module is not available",
    )


def present(name, auth=None, **kwargs):
    """
    Ensure an service exists and is up-to-date

    name
        Name of the group

    type
        Service type

    enabled
        Boolean to control if service is enabled

    description
        An arbitrary description of the service
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    __salt__["keystoneng.setup_clouds"](auth)

    service = __salt__["keystoneng.service_get"](name=name)

    if service is None:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = kwargs
            ret["comment"] = "Service will be created."
            return ret

        kwargs["name"] = name
        service = __salt__["keystoneng.service_create"](**kwargs)
        ret["changes"] = service
        ret["comment"] = "Created service"
        return ret

    changes = __salt__["keystoneng.compare_changes"](service, **kwargs)
    if changes:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = changes
            ret["comment"] = "Service will be updated."
            return ret

        kwargs["name"] = service
        __salt__["keystoneng.service_update"](**kwargs)
        ret["changes"].update(changes)
        ret["comment"] = "Updated service"

    return ret


def absent(name, auth=None):
    """
    Ensure service does not exist

    name
        Name of the service
    """

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    __salt__["keystoneng.setup_clouds"](auth)

    service = __salt__["keystoneng.service_get"](name=name)

    if service:
        if __opts__["test"] is True:
            ret["result"] = None
            ret["changes"] = {"id": service.id}
            ret["comment"] = "Service will be deleted."
            return ret

        __salt__["keystoneng.service_delete"](name=service)
        ret["changes"]["id"] = service.id
        ret["comment"] = "Deleted service"

    return ret
