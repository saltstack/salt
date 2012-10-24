'''
YAML Outputter
'''

# Third Party libs
import yaml


def __virtual__():
    return 'yaml'

def output(data):
    '''
    Print out YAML
    '''
    print(yaml.dump(data))
