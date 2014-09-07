# -*- coding: utf-8 -*-
'''
Return pillars from ext_nodes if configured.  The 'parameters' hash becomes pillars for the minion.
'''

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import python libs
import logging

# Import third party libs
import yaml

# Set up logging
log = logging.getLogger(__name__)

def ext_pillar(minion_id, pillar, enabled):
    '''
    Return pillar data from ext_nodes
    '''
    try:
        if enabled is True and __opts__['master_tops'].has_key('ext_nodes'):
            command = __opts__['master_tops']['ext_nodes']
            return yaml.safe_load(__salt__['cmd.run']('{0} {1}'.format(command, minion_id)))['parameters']
        else:
            log.critical(
                'Cannot get ext_pillar data, no ext_nodes configured!'
                )
            return {}
    except Exception:
        log.critical(
                'YAML data from ext_nodes failed to parse'
                )
        return {}
