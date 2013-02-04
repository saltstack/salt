'''
Execute a command and read the output as YAML. The YAML data is then directly
overlaid onto the minion's pillar data
'''

# Import python libs
import logging

# Import third party libs
import yaml

# Set up logging
log = logging.getLogger(__name__)


def ext_pillar(pillar, command):
    '''
    Execute a command and read the output as YAML
    '''
    try:
        return yaml.safe_load(__salt__['cmd.run']('{0} {1}'.format(command, __opts__['id'])))
    except Exception:
        log.critical(
                'YAML data from {0} failed to parse'.format(command)
                )
        return {}
