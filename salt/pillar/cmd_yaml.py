# -*- coding: utf-8 -*-
'''
Execute a command and read the output as YAML. The YAML data is then directly overlaid onto the minion's Pillar data
'''

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import python libs
import logging

# Import third party libs
import yaml

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, command):
    '''
    Execute a command and read the output as YAML
    '''
    try:
        return yaml.safe_load(__salt__['cmd.run']('{0}'.format(command)))
    except Exception:
        log.critical(
                'YAML data from {0} failed to parse'.format(command)
                )
        return {}
