'''
Process json with the Mako templating engine

This renderer will take a json file with the Mako template and render it to a
high data format for salt states.
'''
# Import python libs
import json
import os

# Import salt modules
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template_file, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template_file):
        return {}

    tmp_data = salt.utils.templates.mako(
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
            'Unknown render error in json_mako renderer'))

    # Ensure that we're not passing lines with a shebang in the JSON.
    to_return = []
    for line in tmp_data['data'].split('\n'):
        if line and "#!" not in line:
            to_return.append(line)
    to_return = '\n'.join(to_return)

    return json.loads(to_return)
