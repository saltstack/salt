'''
Pure python state renderer

The sls file should contain a function called ``run`` which returns high state
data
'''

# Import python libs
import os

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template, env='', sls=''):
    '''
    Render the python module's components
    '''
    if not os.path.isfile(template):
        return {}

    tmp_data = salt.utils.templates.py(
            template,
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

    return tmp_data['data']
