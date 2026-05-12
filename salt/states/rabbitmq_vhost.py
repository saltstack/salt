"""
Manage RabbitMQ Virtual Hosts
=============================

Example:

.. code-block:: yaml

    virtual_host:
      rabbitmq_vhost.present:
        - user: rabbit_user
        - conf: .*
        - write: .*
        - read: .*
"""

import logging

import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if RabbitMQ is installed.
    """
    if salt.utils.path.which("rabbitmqctl"):
        return True
    return (False, "Command not found: rabbitmqctl")


def present(name):
    """
    Ensure the RabbitMQ VHost exists.

    name
        VHost name

    user
        Initial user permission to set on the VHost, if present

        .. deprecated:: 2015.8.0
    owner
        Initial owner permission to set on the VHost, if present

        .. deprecated:: 2015.8.0
    conf
        Initial conf string to apply to the VHost and user. Defaults to .*

        .. deprecated:: 2015.8.0
    write
        Initial write permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: 2015.8.0
    read
        Initial read permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: 2015.8.0
    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    vhost_exists = __salt__["rabbitmq.vhost_exists"](name)

    if vhost_exists:
        ret["comment"] = f"Virtual Host '{name}' already exists."
        return ret

    if not __opts__["test"]:
        result = __salt__["rabbitmq.add_vhost"](name)
        if "Error" in result:
            ret["result"] = False
            ret["comment"] = result["Error"]
            return ret
        elif "Added" in result:
            ret["comment"] = result["Added"]

    # If we've reached this far before returning, we have changes.
    ret["changes"] = {"old": "", "new": name}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Virtual Host '{name}' will be created."

    return ret


def absent(name):
    """
    Ensure the RabbitMQ Virtual Host is absent

    name
        Name of the Virtual Host to remove
    runas
        User to run the command

        .. deprecated:: 2015.8.0
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    vhost_exists = __salt__["rabbitmq.vhost_exists"](name)

    if not vhost_exists:
        ret["comment"] = f"Virtual Host '{name}' is not present."
        return ret

    if not __opts__["test"]:
        result = __salt__["rabbitmq.delete_vhost"](name)
        if "Error" in result:
            ret["result"] = False
            ret["comment"] = result["Error"]
            return ret
        elif "Deleted" in result:
            ret["comment"] = result["Deleted"]

    # If we've reached this far before returning, we have changes.
    ret["changes"] = {"new": "", "old": name}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Virtual Host '{name}' will be removed."

    return ret
