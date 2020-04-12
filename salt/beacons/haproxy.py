# -*- coding: utf-8 -*-
"""
Watch current connections of haproxy server backends.
Fire an event when over a specified threshold.

.. versionadded:: 2016.11.0
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging

from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtualname__ = "haproxy"


def __virtual__():
    """
    Only load the module if haproxyctl module is installed
    """
    if "haproxy.get_sessions" in __salt__:
        return __virtualname__
    else:
        log.debug("Not loading haproxy beacon")
        return False


def validate(config):
    """
    Validate the beacon configuration
    """
    if not isinstance(config, list):
        return False, ("Configuration for haproxy beacon must be a list.")
    else:
        _config = {}
        list(map(_config.update, config))

        if "backends" not in _config:
            return False, ("Configuration for haproxy beacon requires backends.")
        else:
            if not isinstance(_config["backends"], dict):
                return False, ("Backends for haproxy beacon must be a dictionary.")
            else:
                for backend in _config["backends"]:
                    log.debug("_config %s", _config["backends"][backend])
                    if "servers" not in _config["backends"][backend]:
                        return (
                            False,
                            ("Backends for haproxy beacon require servers."),
                        )
                    else:
                        _servers = _config["backends"][backend]["servers"]
                        if not isinstance(_servers, list):
                            return (
                                False,
                                ("Servers for haproxy beacon must be a list."),
                            )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Check if current number of sessions of a server for a specific haproxy backend
    is over a defined threshold.

    .. code-block:: yaml

        beacons:
          haproxy:
            - backends:
                www-backend:
                    threshold: 45
                    servers:
                      - web1
                      - web2
            - interval: 120
    """
    ret = []

    _config = {}
    list(map(_config.update, config))

    for backend in _config.get("backends", ()):
        backend_config = _config["backends"][backend]
        threshold = backend_config["threshold"]
        for server in backend_config["servers"]:
            scur = __salt__["haproxy.get_sessions"](server, backend)
            if scur:
                if int(scur) > int(threshold):
                    _server = {
                        "server": server,
                        "scur": scur,
                        "threshold": threshold,
                    }
                    log.debug(
                        "Emit because %s > %s" " for %s in %s",
                        scur,
                        threshold,
                        server,
                        backend,
                    )
                    ret.append(_server)
    return ret
