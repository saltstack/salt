'''
Output data in YAML, this outputter defaults to printing in YAML block mode
for better readability.
'''

# Third Party libs
import yaml


def __virtual__():
    return 'yaml'


def output(data):
    '''
    Print out YAML using the block mode
    '''
    return yaml.dump(data, default_flow_style=False)
