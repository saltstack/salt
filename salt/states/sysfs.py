"""
Configuration of the kernel using sysfs
=======================================

Control the kernel object attributes exported by sysfs

.. code-block:: yaml

  kernel/mm/transparent_hugepage/enabled
    sysfs.present:
      - value: never

.. versionadded:: 3006.0
"""

import re


def __virtual__():
    """
    This state is only available on Minions which support sysctl
    """
    if "sysfs.attr" in __salt__:
        return True
    return (False, "sysfs module could not be loaded")


def present(name, value, config=None):
    """
    Ensure that the named sysfs attribute is set with the defined value

    name
        The name of the sysfs attribute to edit

    value
        The sysfs value to apply

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    current = __salt__["sysfs.read"](name)
    if current is False:
        ret["result"] = False
        ret["comment"] = "SysFS attribute {} doesn't exist.".format(name)
    else:
        # if the return is a dict, the "name" is an object not an attribute
        if isinstance(current, dict):
            ret["result"] = False
            ret["comment"] = "{} is not a SysFS attribute.".format(name)
        else:
            # some attribute files lists all available options and the selected one between []
            if isinstance(current, str):
                current = re.sub(r"(.*\[|\].*)", "", current)
            if value == current:
                ret["result"] = True
                ret["comment"] = "SysFS attribute {} is already set.".format(name)
            else:
                ret["result"] = None

    if ret["result"] is None:
        if __opts__["test"]:
            ret["comment"] = "SysFS attribute {} set to be changed.".format(name)
        else:
            update = __salt__["sysfs.write"](name, value)
            if not update:
                ret["result"] = False
                ret["comment"] = "Failed to set {} to {}".format(name, value)
            else:
                ret["result"] = True
                ret["changes"] = {name: value}
                ret["comment"] = "Updated SysFS attribute {} to {}".format(name, value)

    return ret
