"""
Management of POSIX Quotas
==========================

The quota can be managed for the system:

.. code-block:: yaml

    /:
      quota.mode:
        mode: off
        quotatype: user
"""


def __virtual__():
    """
    Only load if the quota module is available in __salt__
    """
    if "quota.report" in __salt__:
        return "quota"
    return (False, "quota module could not be loaded")


def mode(name, mode, quotatype):
    """
    Set the quota for the system

    name
        The filesystem to set the quota mode on

    mode
        Whether the quota system is on or off

    quotatype
        Must be ``user`` or ``group``
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    fun = "off"
    if mode is True:
        fun = "on"
    if __salt__["quota.get_mode"](name)[name][quotatype] == fun:
        ret["result"] = True
        ret["comment"] = "Quota for {} already set to {}".format(name, fun)
        return ret
    if __opts__["test"]:
        ret["comment"] = "Quota for {} needs to be set to {}".format(name, fun)
        return ret
    if __salt__["quota.{}".format(fun)](name):
        ret["changes"] = {"quota": name}
        ret["result"] = True
        ret["comment"] = "Set quota for {} to {}".format(name, fun)
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to set quota for {} to {}".format(name, fun)
        return ret
