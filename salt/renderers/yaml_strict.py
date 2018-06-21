# -*- coding: utf-8 -*-
'''
Strict YAML Renderer for Salt

For YAML usage information see :ref:`Understanding YAML <yaml>`.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import re
import logging
import warnings
import yaml
from yaml.scanner import ScannerError
from yaml.parser import ParserError
from yaml.constructor import ConstructorError

# Import salt libs
import salt.utils.stringutils
import salt.utils.url
from salt.utils.odict import OrderedDict
from salt.exceptions import SaltRenderError
from salt.ext import six
from salt.ext.six import string_types

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

log = logging.getLogger(__name__)

_ERROR_MAP = {
    ("found character '\\t' that cannot "
     "start any token"): 'Illegal tab character'
}


class CSafeLoader(Loader):
    def __init__(self, stream, dictclass=dict):
        super(CSafeLoader, self).__init__(stream)
        if dictclass is not dict:
            # then assume ordered dict and use it for both !map and !omap
            self.add_constructor(
                'tag:yaml.org,2002:map',
                type(self).construct_yaml_map)
            self.add_constructor(
                'tag:yaml.org,2002:omap',
                type(self).construct_yaml_map)
        self.add_constructor(
            'tag:yaml.org,2002:str',
            type(self).construct_yaml_str)
        self.add_constructor(
            'tag:yaml.org,2002:python/unicode',
            type(self).construct_unicode)
        self.add_constructor(
            'tag:yaml.org,2002:timestamp',
            type(self).construct_scalar)
        self.dictclass = dictclass

    def construct_unicode(self, node):
        return node.value

    def construct_yaml_str(self, node):
        value = self.construct_scalar(node)
        return salt.utils.stringutils.to_unicode(value)

    def construct_yaml_map(self, node):
        data = self.dictclass()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_scalar(self, node):
        '''
        Verify integers and pass them in correctly is they are declared
        as octal
        '''
        if node.tag == 'tag:yaml.org,2002:int':
            if node.value == '0':
                pass
            elif node.value.startswith('0') and not node.value.startswith(('0b', '0x')):
                node.value = node.value.lstrip('0')
                # If value was all zeros, node.value would have been reduced to
                # an empty string. Change it to '0'.
                if node.value == '':
                    node.value = '0'
        elif node.tag == 'tag:yaml.org,2002:str':
            # If any string comes in as a quoted unicode literal, eval it into
            # the proper unicode string type.
            if re.match(r'^u([\'"]).+\1$', node.value, flags=re.IGNORECASE):
                node.value = eval(node.value, {}, {})  # pylint: disable=W0123
        return super(CSafeLoader, self).construct_scalar(node)


def get_yaml_loader(argline):
    '''
    Return the ordered dict yaml loader
    '''
    def yaml_loader(*args):
        return CSafeLoader(*args, dictclass=OrderedDict)
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
            data = yaml.load(yaml_data, Loader=get_yaml_loader(argline))
        except ScannerError as exc:
            err_type = _ERROR_MAP.get(exc.problem, exc.problem)
            line_num = exc.problem_mark.line + 1
            raise SaltRenderError(err_type, line_num, exc.problem_mark.buffer)
        except (ParserError, ConstructorError) as exc:
            raise SaltRenderError(exc)
        if len(warn_list) > 0:
            for item in warn_list:
                log.warning(
                    '%s found in %s saltenv=%s',
                    item.message, salt.utils.url.create(sls), saltenv
                )
        if not data:
            data = {}
        log.debug('Results of YAML rendering: \n%s', data)

        def _validate_data(data):
            '''
            PyYAML will for some reason allow improper YAML to be formed into
            an unhashable dict (that is, one with a dict as a key). This
            function will recursively go through and check the keys to make
            sure they're not dicts.
            '''
            if isinstance(data, dict):
                for key, value in six.iteritems(data):
                    if isinstance(key, dict):
                        raise SaltRenderError(
                            'Invalid YAML, possible double curly-brace')
                    _validate_data(value)
            elif isinstance(data, list):
                for item in data:
                    _validate_data(item)

        _validate_data(data)
        return data
