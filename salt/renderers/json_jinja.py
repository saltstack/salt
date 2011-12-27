'''
Process json with the jinja2 templating engine

This renderer will take a json file with the jinja template and render it to a
high data format for salt states.
'''

import json
import os
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

    json_data = template.render(**passthrough)

    return json.loads(json_data)
