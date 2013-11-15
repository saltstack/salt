# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
import logging
import warnings
from yaml.scanner import ScannerError
from yaml.constructor import ConstructorError

# Import salt libs
from salt.utils.yamlloader import CustomLoader, load
from salt.utils.odict import OrderedDict
from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)

_ERROR_MAP = {
    ("found character '\\t' that cannot "
     "start any token"): 'Illegal tab character'
}


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
        try:
            data = load(yaml_data, Loader=get_yaml_loader(argline))
        except ScannerError as exc:
            err_type = _ERROR_MAP.get(exc.problem, 'Unknown yaml render error')
            line_num = exc.problem_mark.line + 1
            raise SaltRenderError(err_type, line_num, exc.problem_mark.buffer)
        except ConstructorError as exc:
            raise SaltRenderError(exc)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warn(
                    '{warn} found in salt://{sls} environment={env}'.format(
                        warn=item.message, sls=sls, env=env
                    )
                )
        if not data:
            data = {}
        log.debug('Results of YAML rendering: \n{0}'.format(data))
        return data
