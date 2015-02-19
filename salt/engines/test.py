'''
A simple test engine, not intended for real use but as an example
'''
# Import salt libs
import salt.utils.event

# Import python libs
import os
import json


def start():
    '''
    Listen to events and write them to a log file
    '''
    event_bus = salt.utils.event.get_master_event(__opts__)
    fp_ = os.path.join(__opts__['cachedir'], 'engine_test_elog')
    while True:
        event = event_bus.get_event()
        if event:
            fp_.write(json.dump(event))
    fp_.close()
