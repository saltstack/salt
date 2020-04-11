# -*- coding: utf-8 -*-
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
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
from salt.ext import six


def __virtual__():
    """
    Only load if a2ensite is available.
    """
    return "apache_site" if "apache.a2ensite" in __salt__ else False


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
            msg = "Apache site {0} is set to be enabled.".format(name)
            ret["comment"] = msg
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
            ret["result"] = None
            return ret
        status = __salt__["apache.a2ensite"](name)["Status"]
        if isinstance(status, six.string_types) and "enabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = None
            ret["changes"]["new"] = name
        else:
            ret["result"] = False
            ret["comment"] = "Failed to enable {0} Apache site".format(name)
            if isinstance(status, six.string_types):
                ret["comment"] = ret["comment"] + " ({0})".format(status)
            return ret
    else:
        ret["comment"] = "{0} already enabled.".format(name)
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
            msg = "Apache site {0} is set to be disabled.".format(name)
            ret["comment"] = msg
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
            ret["result"] = None
            return ret
        status = __salt__["apache.a2dissite"](name)["Status"]
        if isinstance(status, six.string_types) and "disabled" in status:
            ret["result"] = True
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = "Failed to disable {0} Apache site".format(name)
            if isinstance(status, six.string_types):
                ret["comment"] = ret["comment"] + " ({0})".format(status)
            return ret
    else:
        ret["comment"] = "{0} already disabled.".format(name)
    return ret
