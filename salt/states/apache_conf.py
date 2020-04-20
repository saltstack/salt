# -*- coding: utf-8 -*-
"""
Manage Apache Confs

.. versionadded:: 2016.3.0

Enable and disable apache confs.

.. code-block:: yaml

    Enable security conf:
      apache_conf.enabled:
        - name: security

    Disable security conf:
      apache_conf.disabled:
        - name: security
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.path
from salt.ext import six


def __virtual__():
    """
    Only load if a2enconf is available.
    """
    if "apache.a2enconf" in __salt__ and salt.utils.path.which("a2enconf"):
        return "apache_conf"
    return (False, "apache module could not be loaded")


def enabled(name):
    """
    Ensure an Apache conf is enabled.

    name
        Name of the Apache conf
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_conf_enabled"](name)
    if not is_enabled:
        if __opts__["test"]:
            msg = "Apache conf {0} is set to be enabled.".format(name)
            ret["comment"] = msg
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
            ret["result"] = None
            return ret
        status = __salt__["apache.a2enconf"](name)["Status"]
        if isinstance(status, six.string_types) and "enabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
        else:
            ret["result"] = False
            ret["comment"] = "Failed to enable {0} Apache conf".format(name)
            if isinstance(status, six.string_types):
                ret["comment"] = ret["comment"] + " ({0})".format(status)
            return ret
    else:
        ret["comment"] = "{0} already enabled.".format(name)
    return ret


def disabled(name):
    """
    Ensure an Apache conf is disabled.

    name
        Name of the Apache conf
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    is_enabled = __salt__["apache.check_conf_enabled"](name)
    if is_enabled:
        if __opts__["test"]:
            msg = "Apache conf {0} is set to be disabled.".format(name)
            ret["comment"] = msg
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
            ret["result"] = None
            return ret
        status = __salt__["apache.a2disconf"](name)["Status"]
        if isinstance(status, six.string_types) and "disabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = "Failed to disable {0} Apache conf".format(name)
            if isinstance(status, six.string_types):
                ret["comment"] = ret["comment"] + " ({0})".format(status)
            return ret
    else:
        ret["comment"] = "{0} already disabled.".format(name)
    return ret
