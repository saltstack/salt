# -*- coding: utf-8 -*-
'''
Execute a command and read the output as JSON. The JSON data is then directly overlaid onto the minion's Pillar data.
'''

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import python libs
import logging
import json

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               command):
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
