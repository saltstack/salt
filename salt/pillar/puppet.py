# -*- coding: utf-8 -*-
'''
Execute an unmodified puppet_node_classifier and read the output as YAML. The YAML data is then directly overlaid onto the minion's Pillar data.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import Python libs
import logging

# Import Salt libs
import salt.utils.yaml

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               command):
    '''
    Execute an unmodified puppet_node_classifier and read the output as YAML
    '''
    try:
        data = salt.utils.yaml.safe_load(__salt__['cmd.run']('{0} {1}'.format(command, minion_id)))
        return data['parameters']
    except Exception:
        log.critical('YAML data from %s failed to parse', command)
        return {}
