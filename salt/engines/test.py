# -*- coding: utf-8 -*-
"""
A simple test engine, not intended for real use but as an example
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.event
import salt.utils.json

log = logging.getLogger(__name__)


def event_bus_context(opts):
    if opts["__role"] == "master":
        event_bus = salt.utils.event.get_master_event(
            opts, opts["sock_dir"], listen=True
        )
    else:
        event_bus = salt.utils.event.get_event(
            "minion",
            transport=opts["transport"],
            opts=opts,
            sock_dir=opts["sock_dir"],
            listen=True,
        )
        log.debug("test engine started")
    return event_bus


def start():
    """
    Listen to events and write them to a log file
    """
    with event_bus_context(__opts__) as event_bus:
        while True:
            event = event_bus.get_event()
            jevent = salt.utils.json.dumps(event)
            if event:
                log.debug(jevent)
