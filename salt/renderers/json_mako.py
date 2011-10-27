'''
The default rendering engine, yaml_jinja, this renderer will take a yaml file
with the jinja template and render it to a high data format for salt states.
'''

# Import python libs
import os
import json

# Import Third Party libs
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
    passthrough['env'] = env
    passthrough['sls'] = sls
    template = Template(open(template, 'r').read())
    json_data = template.render(**passthrough)
    return json.loads(json_data)

