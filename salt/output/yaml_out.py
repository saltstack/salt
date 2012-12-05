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
    if 'output_indent' in __opts__ and __opts__['output_indent'] >= 0:
        return yaml.dump(
            data, default_flow_style=False, indent=__opts__['output_indent']
        )
    elif 'output_indent' in __opts__ and __opts__['output_indent'] < 0:
        # Disable indentation
        return yaml.dump(data, default_flow_style=True, indent=0)
    return yaml.dump(data, default_flow_style=False)
