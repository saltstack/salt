'''
The default rendering engine, process yaml with the jinja2 templating engine

This renderer will take a yaml file with the jinja2 template and render it to a
high data format for salt states.
'''

import os

# Import Third Party libs
from jinja2 import Template
import yaml


def render(template, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template):
        return {}

    passthrough = {}
    passthrough['salt'] = __salt__
    passthrough['grains'] = __grains__
    passthrough['env'] = env
    passthrough['sls'] = sls

    template = Template(open(template, 'r').read())
    yaml_data = template.render(**passthrough)

    return yaml.safe_load(yaml_data)
