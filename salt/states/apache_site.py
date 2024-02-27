"""
Manage Apache Sites

.. versionadded:: 2016.3.0

Enable and disable apache sites.

.. code-block:: yaml

    Enable default site:
      apache_site.enabled:
        - name: default

    Disable default site:
      apache_site.disabled:
        - name: default
"""


def __virtual__():
    """
    Only load if a2ensite is available.
    """
    if "apache.a2ensite" in __salt__:
        return "apache_site"
    return (False, "apache module could not be loaded")


def enabled(name):
    """
    Ensure an Apache site is enabled.

    name
        Name of the Apache site
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_site_enabled"](name)
    if not is_enabled:
        if __opts__["test"]:
            msg = f"Apache site {name} is set to be enabled."
            ret["comment"] = msg
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
            ret["result"] = None
            return ret
        status = __salt__["apache.a2ensite"](name)["Status"]
        if isinstance(status, str) and "enabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to enable {name} Apache site"
            if isinstance(status, str):
                ret["comment"] = ret["comment"] + f" ({status})"
            return ret
    else:
        ret["comment"] = f"{name} already enabled."
    return ret


def disabled(name):
    """
    Ensure an Apache site is disabled.

    name
        Name of the Apache site
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_site_enabled"](name)
    if is_enabled:
        if __opts__["test"]:
            msg = f"Apache site {name} is set to be disabled."
            ret["comment"] = msg
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
            ret["result"] = None
            return ret
        status = __salt__["apache.a2dissite"](name)["Status"]
        if isinstance(status, str) and "disabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to disable {name} Apache site"
            if isinstance(status, str):
                ret["comment"] = ret["comment"] + f" ({status})"
            return ret
    else:
        ret["comment"] = f"{name} already disabled."
    return ret
