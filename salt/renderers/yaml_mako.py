'''
Process yaml with the Mako templating engine

This renderer will take a yaml file within a mako template and render it to a
high data format for salt states.
'''

# Import Python Modules
import os

# Import Third Party libs
from mako.template import Template

from salt.utils.yaml import CustomLoader, load
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template):
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
            'Unknown render error in yaml_mako renderer'))
    yaml_data = tmp_data['data']

    with warnings.catch_warnings(record=True) as warn_list:
        data = load(yaml_data, Loader=CustomLoader)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn("{warn} found in {file_}".format(
                        warn=item.message, file_=template_file))
        return data
