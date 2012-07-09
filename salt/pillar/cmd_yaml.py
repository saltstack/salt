'''
Execute a command and read the output as YAML. The YAML data is then directly
overlaid onto the minion's pillar data
'''

# Import third party libs
import yaml


def ext_pillar(command):
    '''
    Execute a command and read the output as YAML
    '''
    return yaml.safe_load(__salt__['cmd.run'](command))
