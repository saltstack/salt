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
from salt.utils.jinja import get_template

from salt.renderers.utils import CustomLoader, load

log = logging.getLogger(__name__)

def render(template_file, env='', sls=''):
    '''
    Render the data passing the functions and grains into the rendering system
    '''
    if not os.path.isfile(template_file):
        return {}

    passthrough = {}
    passthrough['salt'] = __salt__
    passthrough['grains'] = __grains__
    passthrough['pillar'] = __pillar__
    passthrough['env'] = env
    passthrough['sls'] = sls

    template = get_template(template_file, __opts__, env)

    yaml_data = template.render(**passthrough)
    with warnings.catch_warnings(record=True) as warn_list:
        data = load(yaml_data, Loader=CustomLoader)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn("{warn} found in {file_}".format(
                        warn=item.message, file_=template_file))
        return data
