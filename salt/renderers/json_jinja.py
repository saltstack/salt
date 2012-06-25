'''
Process json with the jinja2 templating engine

This renderer will take a json file with the jinja template and render it to a
high data format for salt states.
'''

# Import python libs
import json
import os

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template_file, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template_file):
        return {}

    tmp_data = salt.utils.templates.jinja(
            template_file,
            True,
            salt=__salt__,
            grains=__grains__,
            opts=__opts__,
            pillar=__pillar__,
            env=env,
            sls=sls)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in yaml_jinja renderer'))
    return json.loads(tmp_data['data'])
