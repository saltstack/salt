# -*- coding: utf-8 -*-
'''
Execute a command and read the output as JSON. The JSON data is then directly
overlaid onto the minion's pillar data
'''

# Import python libs
import logging
import json

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, command):
    '''
    Execute a command and read the output as JSON
    '''
    try:
        return json.loads(__salt__['cmd.run'](command))
    except Exception:
        log.critical(
                'JSON data from {0} failed to parse'.format(command)
                )
        return {}
