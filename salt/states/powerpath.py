"""
Powerpath configuration support
===============================

Allows configuration of EMC Powerpath.  Currently
only addition/deletion of licenses is supported.

.. code-block:: yaml

    key:
      powerpath.license_present: []
"""


def license_present(name):
    """
    Ensures that the specified PowerPath license key is present
    on the host.

    name
        The license key to ensure is present
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if not __salt__["powerpath.has_powerpath"]():
        ret["result"] = False
        ret["comment"] = "PowerPath is not installed."
        return ret

    licenses = [l["key"] for l in __salt__["powerpath.list_licenses"]()]

    if name in licenses:
        ret["result"] = True
        ret["comment"] = "License key {} already present".format(name)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "License key {} is set to be added".format(name)
        return ret

    data = __salt__["powerpath.add_license"](name)
    if data["result"]:
        ret["changes"] = {name: "added"}
        ret["result"] = True
        ret["comment"] = data["output"]
        return ret
    else:
        ret["result"] = False
        ret["comment"] = data["output"]
        return ret


def license_absent(name):
    """
    Ensures that the specified PowerPath license key is absent
    on the host.

    name
        The license key to ensure is absent
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if not __salt__["powerpath.has_powerpath"]():
        ret["result"] = False
        ret["comment"] = "PowerPath is not installed."
        return ret

    licenses = [l["key"] for l in __salt__["powerpath.list_licenses"]()]

    if name not in licenses:
        ret["result"] = True
        ret["comment"] = "License key {} not present".format(name)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "License key {} is set to be removed".format(name)
        return ret

    data = __salt__["powerpath.remove_license"](name)
    if data["result"]:
        ret["changes"] = {name: "removed"}
        ret["result"] = True
        ret["comment"] = data["output"]
        return ret
    else:
        ret["result"] = False
        ret["comment"] = data["output"]
        return ret
