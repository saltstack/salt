"""
Management of Gentoo Overlays using layman
==========================================

A state module to manage Gentoo package overlays via layman

.. code-block:: yaml

    sunrise:
        layman.present
"""


def __virtual__():
    """
    Only load if the layman module is available in __salt__
    """
    if "layman.add" in __salt__:
        return "layman"
    return (False, "layman module could not be loaded")


def present(name):
    """
    Verify that the overlay is present

    name
        The name of the overlay to add
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    # Overlay already present
    if name in __salt__["layman.list_local"]():
        ret["comment"] = f"Overlay {name} already present"
    elif __opts__["test"]:
        ret["comment"] = f"Overlay {name} is set to be added"
        ret["result"] = None
        return ret
    else:
        # Does the overlay exist?
        if name not in __salt__["layman.list_all"]():
            ret["comment"] = f"Overlay {name} not found"
            ret["result"] = False
        else:
            # Attempt to add the overlay
            changes = __salt__["layman.add"](name)

            # The overlay failed to add
            if len(changes) < 1:
                ret["comment"] = f"Overlay {name} failed to add"
                ret["result"] = False
            # Success
            else:
                ret["changes"]["added"] = changes
                ret["comment"] = f"Overlay {name} added."

    return ret


def absent(name):
    """
    Verify that the overlay is absent

    name
        The name of the overlay to delete
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    # Overlay is already absent
    if name not in __salt__["layman.list_local"]():
        ret["comment"] = f"Overlay {name} already absent"
    elif __opts__["test"]:
        ret["comment"] = f"Overlay {name} is set to be deleted"
        ret["result"] = None
        return ret
    else:
        # Attempt to delete the overlay
        changes = __salt__["layman.delete"](name)

        # The overlay failed to delete
        if len(changes) < 1:
            ret["comment"] = f"Overlay {name} failed to delete"
            ret["result"] = False
        # Success
        else:
            ret["changes"]["deleted"] = changes
            ret["comment"] = f"Overlay {name} deleted."

    return ret
