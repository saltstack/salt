"""
Manage Apache Modules

.. versionadded:: 2014.7.0

Enable and disable apache modules.

.. code-block:: yaml

    Enable cgi module:
      apache_module.enabled:
        - name: cgi

    Disable cgi module:
      apache_module.disabled:
        - name: cgi
"""


def __virtual__():
    """
    Only load if a2enmod is available.
    """
    if "apache.a2enmod" in __salt__:
        return "apache_module"
    return (False, "apache module could not be loaded")


def enabled(name):
    """
    Ensure an Apache module is enabled.

    .. versionadded:: 2016.3.0

    name
        Name of the Apache module
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_mod_enabled"](name)
    if not is_enabled:
        if __opts__["test"]:
            msg = f"Apache module {name} is set to be enabled."
            ret["comment"] = msg
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
            ret["result"] = None
            return ret
        status = __salt__["apache.a2enmod"](name)["Status"]
        if isinstance(status, str) and "enabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to enable {name} Apache module"
            if isinstance(status, str):
                ret["comment"] = ret["comment"] + f" ({status})"
            return ret
    else:
        ret["comment"] = f"{name} already enabled."
    return ret


def disabled(name):
    """
    Ensure an Apache module is disabled.

    .. versionadded:: 2016.3.0

    name
        Name of the Apache module
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_mod_enabled"](name)
    if is_enabled:
        if __opts__["test"]:
            msg = f"Apache module {name} is set to be disabled."
            ret["comment"] = msg
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
            ret["result"] = None
            return ret
        status = __salt__["apache.a2dismod"](name)["Status"]
        if isinstance(status, str) and "disabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to disable {name} Apache module"
            if isinstance(status, str):
                ret["comment"] = ret["comment"] + f" ({status})"
            return ret
    else:
        ret["comment"] = f"{name} already disabled."
    return ret
