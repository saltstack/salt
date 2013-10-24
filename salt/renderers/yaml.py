# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
import logging
import warnings

# Import salt libs
from salt.utils.yamlloader import CustomLoader, load
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)


def get_yaml_loader(argline):
    '''
    Return the ordered dict yaml loader
    '''
    def yaml_loader(*args):
        return CustomLoader(*args, dictclass=OrderedDict)
    return yaml_loader


def render(yaml_data, env='', sls='', argline='', **kws):
    '''
    Accepts YAML as a string or as a file object and runs it through the YAML
    parser.

    :rtype: A Python data structure
    '''
    if not isinstance(yaml_data, basestring):
        yaml_data = yaml_data.read()
    with warnings.catch_warnings(record=True) as warn_list:
        data = load(yaml_data, Loader=get_yaml_loader(argline))
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn(
                    '{warn} found in salt://{sls} environment={env}'.format(
                    warn=item.message, sls=sls, env=env))
        if not data:
            data = {}
        log.debug('Results of YAML rendering: \n{0}'.format(data))
        return data
