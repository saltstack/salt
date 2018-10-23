# -*- coding: utf-8 -*-
'''
Execute a command and read the output as JSON. The JSON data is then directly overlaid onto the minion's Pillar data.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import Python libs
import logging

# Import Salt libs
import salt.utils.json

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               command):
    '''
    Execute a command and read the output as JSON
    '''
    try:
        command = command.replace('%s', minion_id)
        return salt.utils.json.loads(__salt__['cmd.run'](command))
    except Exception:
        log.critical('JSON data from %s failed to parse', command)
        return {}
