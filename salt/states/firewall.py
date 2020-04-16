# -*- coding: utf-8 -*-
"""
State to check firewall configurations

.. versionadded:: 2016.3.0
"""
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():

    """
    Load only if network is loaded
    """

    return "firewall" if "network.connect" in __salt__ else False


def check(name, port=None, **kwargs):

    """
    Checks if there is an open connection from the minion to the defined
    host on a specific port.

    name
      host name or ip address to test connection to

    port
      The port to test the connection on

    kwargs
      Additional parameters, parameters allowed are:
        proto (tcp or udp)
        family (ipv4 or ipv6)
        timeout

    .. code-block:: yaml

      testgoogle:
        firewall.check:
          - name: 'google.com'
          - port: 80
          - proto: 'tcp'

    """

    # set name to host as required by the module
    host = name

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if "test" not in kwargs:
        kwargs["test"] = __opts__.get("test", False)

    # check the connection
    if kwargs["test"]:
        ret["result"] = True
        ret["comment"] = "The connection will be tested"
    else:
        results = __salt__["network.connect"](host, port, **kwargs)
        ret["result"] = results["result"]
        ret["comment"] = results["comment"]

    return ret
