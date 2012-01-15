'''
The default rendering engine, process yaml with the jinja2 templating engine

This renderer will take a yaml file with the jinja2 template and render it to a
high data format for salt states.
'''

# Import Python Modules
import os

# Import thirt party modules
import yaml
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except:
    pass

# Import Salt libs
from salt.utils.jinja import get_template

def render(template_file, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template_file):
        return {}

    passthrough = {}
    passthrough['salt'] = __salt__
    passthrough['grains'] = __grains__
    passthrough['env'] = env
    passthrough['sls'] = sls

    template = get_template(template_file, __opts__, env)

    yaml_data = template.render(**passthrough)

    return yaml.safe_load(yaml_data)
