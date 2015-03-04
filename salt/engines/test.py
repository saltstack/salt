# -*- coding: utf-8 -*-
'''
A simple test engine, not intended for real use but as an example
'''
# Import salt libs
import salt.utils.event

# Import python libs
import json
import logging

log = logging.getLogger(__name__)


def start():
    '''
    Listen to events and write them to a log file
    '''
    event_bus = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir'])
    while True:
        event = event_bus.get_event()
        jevent = json.dumps(event)
        if event:
            log.debug(jevent)
