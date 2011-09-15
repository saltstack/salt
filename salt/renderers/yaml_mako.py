'''
yaml_mako, this renderer will take a yaml file
within a mako template and render it to a high data format for salt states.
'''

# Import python libs
import os

# Import Third Party libs
import yaml
from mako.template import Template

def render(template):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template):
        return {}
    passthrough = {}
    passthrough['salt'] = __salt__
    passthrough['grains'] = __grains__
    template = Template(open(template, 'r').read())
    yaml_data = template.render(**passthrough)
    return yaml.load(yaml_data)

