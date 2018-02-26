# -*- coding: utf-8 -*-
'''
Execute a command and read the output as YAMLEX. The YAMLEX data is then
directly overlaid onto the minion's Pillar data
'''

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
from salt.serializers.yamlex import deserialize

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               command):
    '''
    Execute a command and read the output as YAMLEX
    '''
    try:
        command = command.replace('%s', minion_id)
        return deserialize(__salt__['cmd.run']('{0}'.format(command)))
    except Exception:
        log.critical(
                'YAML data from {0} failed to parse'.format(command)
                )
        return {}
