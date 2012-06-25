'''
The default rendering engine, process yaml with the jinja2 templating engine

This renderer will take a yaml file with the jinja2 template and render it to a
high data format for salt states.
'''

# Import Python Modules
import os
import logging
import warnings

# Import Salt libs
from salt.utils.yaml import CustomLoader, load
from salt.exceptions import SaltRenderError
import salt.utils.templates

log = logging.getLogger(__name__)


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
    yaml_data = tmp_data['data']
    with warnings.catch_warnings(record=True) as warn_list:
        data = load(yaml_data, Loader=CustomLoader)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn("{warn} found in {file_}".format(
                        warn=item.message, file_=template_file))
        return data
