# -*- coding: utf-8 -*-
'''
Output data in YAML, this outputter defaults to printing in YAML block mode
for better readability.
'''

# Import third party libs
import yaml


def __virtual__():
    return 'yaml'


def output(data):
    '''
    Print out YAML using the block mode
    '''
    if 'output_indent' in __opts__:
        if __opts__['output_indent'] >= 0:
            return yaml.dump(
                data, default_flow_style=False,
                indent=__opts__['output_indent']
            )
        # Disable indentation
        return yaml.dump(data, default_flow_style=True, indent=0)
    return yaml.dump(data, default_flow_style=False)
