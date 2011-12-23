'''
The default rendering engine, process yaml with the jinja2 templating engine

This renderer will take a yaml file with the jinja2 template and render it to a
high data format for salt states.
'''

import os

# Import Third Party libs
from jinja2 import Template, FileSystemLoader
import yaml
from jinja2.environment import Environment


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

    file_cache = '/files/%s/' % env
    if file_cache in template_file:
        cache_dir, file_rel = template_file.split(file_cache, 1)
        loader = FileSystemLoader(cache_dir + file_cache)
        jinja_env = Environment(loader=loader)
        template = jinja_env.get_template(file_rel)
    else:
        template = Template(open(template_file, 'r').read())

    yaml_data = template.render(**passthrough)

    return yaml.safe_load(yaml_data)
