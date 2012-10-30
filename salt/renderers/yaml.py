from __future__ import absolute_import

# Import Python Modules
import logging
import warnings

# Import Salt libs
from salt.utils.yaml import CustomLoader, load


log = logging.getLogger(__name__)

def render(yaml_data, env='', sls='', **kws):
    if not isinstance(yaml_data, basestring):
        yaml_data = yaml_data.read()
    with warnings.catch_warnings(record=True) as warn_list:
        data = load(yaml_data, Loader=CustomLoader)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn(
                    "{warn} found in salt://{sls} environment={env}".format(
                    warn=item.message, sls=sls, env=env))
        return data
