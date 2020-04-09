# -*- coding: utf-8 -*-
"""
State module for Cisco NSO Proxy minions

.. versionadded: 2016.11.0

For documentation on setting up the cisconso proxy minion look in the documentation
for :mod:`salt.proxy.cisconso <salt.proxy.cisconso>`.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.compat


def __virtual__():
    return "cisconso.set_data_value" in __salt__


def value_present(name, datastore, path, config):
    """
    Ensure a specific value exists at a given path

    :param name: The name for this rule
    :type  name: ``str``

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path to set the value at,
        a list of element names in order, / separated
    :type  path: ``list``, ``str`` OR ``tuple``

    :param config: The new value at the given path
    :type  config: ``dict``

    Examples:

    .. code-block:: yaml

        enable pap auth:
          cisconso.config_present:
            - name: enable_pap_auth
            - datastore: running
            - path: devices/device/ex0/config/sys/interfaces/serial/ppp0/authentication
            - config:
                authentication:
                    method: pap
                    "list-name": foobar

    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    existing = __salt__["cisconso.get_data"](datastore, path)

    if salt.utils.compat.cmp(existing, config):
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:
        ret["result"] = None
        ret["comment"] = "Config will be added"
        diff = _DictDiffer(existing, config)
        ret["changes"]["new"] = diff.added()
        ret["changes"]["removed"] = diff.removed()
        ret["changes"]["changed"] = diff.changed()

    else:
        __salt__["cisconso.set_data_value"](datastore, path, config)
        ret["result"] = True
        ret["comment"] = "Successfully added config"
        diff = _DictDiffer(existing, config)
        ret["changes"]["new"] = diff.added()
        ret["changes"]["removed"] = diff.removed()
        ret["changes"]["changed"] = diff.changed()

    return ret


class _DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = (
            set(current_dict.keys()),
            set(past_dict.keys()),
        )
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(
            o for o in self.intersect if self.past_dict[o] != self.current_dict[o]
        )

    def unchanged(self):
        return set(
            o for o in self.intersect if self.past_dict[o] == self.current_dict[o]
        )
