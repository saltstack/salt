# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
import logging
import warnings
from yaml.scanner import ScannerError
from yaml.constructor import ConstructorError

# Import salt libs
from salt.utils.yamlloader import SaltYamlSafeLoader, load
from salt.utils.odict import OrderedDict
from salt.exceptions import SaltRenderError
from salt._compat import string_types

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
        return SaltYamlSafeLoader(*args, dictclass=OrderedDict)
    return yaml_loader


def render(yaml_data, saltenv='base', sls='', argline='', **kws):
    '''
    Accepts YAML as a string or as a file object and runs it through the YAML
    parser.

    :rtype: A Python data structure
    '''
    if not isinstance(yaml_data, string_types):
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
                    '{warn} found in salt://{sls} environment={saltenv}'.format(
                        warn=item.message, sls=sls, saltenv=saltenv
                    )
                )
        if not data:
            data = {}
        else:
            if isinstance(__salt__, dict):
                if 'config.get' in __salt__:
                    if __salt__['config.get']('yaml_utf8', False):
                        data = _yaml_result_unicode_to_utf8(data)
            elif __opts__.get('yaml_utf8'):
                data = _yaml_result_unicode_to_utf8(data)
        log.debug('Results of YAML rendering: \n{0}'.format(data))
        return data


def _yaml_result_unicode_to_utf8(data):
    ''''
    Replace `unicode` strings by utf-8 `str` in final yaml result

    This is a recursive function
    '''
    if isinstance(data, OrderedDict):
        for key, elt in data.iteritems():
            if isinstance(elt, unicode):
                # Here be dragons
                data[key] = elt.encode('utf-8')
            elif isinstance(elt, OrderedDict):
                data[key] = _yaml_result_unicode_to_utf8(elt)
            elif isinstance(elt, list):
                for i in xrange(len(elt)):
                    elt[i] = _yaml_result_unicode_to_utf8(elt[i])
    elif isinstance(data, list):
        for i in xrange(len(data)):
            data[i] = _yaml_result_unicode_to_utf8(data[i])
    elif isinstance(data, unicode):
        # here also
        data = data.encode('utf-8')
    return data
