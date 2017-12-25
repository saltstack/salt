# -*- coding: utf-8 -*-
'''
    salt.serializers.yaml
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements YAML serializer.

    Underneath, it is based on pyyaml and use the safe dumper and loader.
    It also use C bindings if they are available.
'''

from __future__ import absolute_import, print_function, unicode_literals
import datetime

import yaml
from yaml.constructor import ConstructorError
from yaml.scanner import ScannerError

from salt.serializers import DeserializationError, SerializationError
from salt.ext import six
from salt.utils.odict import OrderedDict

__all__ = ['deserialize', 'serialize', 'available']

available = True

# prefer C bindings over python when available
BaseLoader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
BaseDumper = getattr(yaml, 'CSafeDumper', yaml.SafeDumper)

ERROR_MAP = {
    ("found character '\\t' "
     "that cannot start any token"): 'Illegal tab character'
}


def deserialize(stream_or_string, **options):
    '''
    Deserialize any string of stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower yaml module.
    '''

    options.setdefault('Loader', Loader)
    try:
        return yaml.load(stream_or_string, **options)
    except ScannerError as error:
        err_type = ERROR_MAP.get(error.problem, 'Unknown yaml render error')
        line_num = error.problem_mark.line + 1
        raise DeserializationError(err_type,
                                   line_num,
                                   error.problem_mark.buffer)
    except ConstructorError as error:
        raise DeserializationError(error)
    except Exception as error:
        raise DeserializationError(error)


def serialize(obj, **options):
    '''
    Serialize Python data to YAML.

    :param obj: the data structure to serialize
    :param options: options given to lower yaml module.
    '''

    options.setdefault('Dumper', Dumper)
    try:
        response = yaml.dump(obj, **options)
        if response.endswith('\n...\n'):
            return response[:-5]
        if response.endswith('\n'):
            return response[:-1]
        return response
    except Exception as error:
        raise SerializationError(error)


class EncryptedString(str):

    yaml_tag = '!encrypted'

    @staticmethod
    def yaml_constructor(loader, tag, node):
        return EncryptedString(loader.construct_scalar(node))

    @staticmethod
    def yaml_dumper(dumper, data):
        return dumper.represent_scalar(EncryptedString.yaml_tag, data.__str__())


class Loader(BaseLoader):  # pylint: disable=W0232
    '''Overwrites Loader as not for pollute legacy Loader'''
    pass


Loader.add_multi_constructor(EncryptedString.yaml_tag, EncryptedString.yaml_constructor)
Loader.add_multi_constructor('tag:yaml.org,2002:null', Loader.construct_yaml_null)
Loader.add_multi_constructor('tag:yaml.org,2002:bool', Loader.construct_yaml_bool)
Loader.add_multi_constructor('tag:yaml.org,2002:int', Loader.construct_yaml_int)
Loader.add_multi_constructor('tag:yaml.org,2002:float', Loader.construct_yaml_float)
Loader.add_multi_constructor('tag:yaml.org,2002:binary', Loader.construct_yaml_binary)
Loader.add_multi_constructor('tag:yaml.org,2002:timestamp', Loader.construct_yaml_timestamp)
Loader.add_multi_constructor('tag:yaml.org,2002:omap', Loader.construct_yaml_omap)
Loader.add_multi_constructor('tag:yaml.org,2002:pairs', Loader.construct_yaml_pairs)
Loader.add_multi_constructor('tag:yaml.org,2002:set', Loader.construct_yaml_set)
Loader.add_multi_constructor('tag:yaml.org,2002:str', Loader.construct_yaml_str)
Loader.add_multi_constructor('tag:yaml.org,2002:seq', Loader.construct_yaml_seq)
Loader.add_multi_constructor('tag:yaml.org,2002:map', Loader.construct_yaml_map)
Loader.add_multi_constructor(None, Loader.construct_undefined)


class Dumper(BaseDumper):  # pylint: disable=W0232
    '''Overwrites Dumper as not for pollute legacy Dumper'''
    pass

Dumper.add_multi_representer(EncryptedString, EncryptedString.yaml_dumper)
Dumper.add_multi_representer(type(None), Dumper.represent_none)
Dumper.add_multi_representer(str, Dumper.represent_str)
if six.PY2:
    Dumper.add_multi_representer(six.text_type, Dumper.represent_unicode)
    Dumper.add_multi_representer(int, Dumper.represent_long)
Dumper.add_multi_representer(bool, Dumper.represent_bool)
Dumper.add_multi_representer(int, Dumper.represent_int)
Dumper.add_multi_representer(float, Dumper.represent_float)
Dumper.add_multi_representer(list, Dumper.represent_list)
Dumper.add_multi_representer(tuple, Dumper.represent_list)
Dumper.add_multi_representer(dict, Dumper.represent_dict)
Dumper.add_multi_representer(set, Dumper.represent_set)
Dumper.add_multi_representer(datetime.date, Dumper.represent_date)
Dumper.add_multi_representer(datetime.datetime, Dumper.represent_datetime)
Dumper.add_multi_representer(None, Dumper.represent_undefined)
Dumper.add_multi_representer(OrderedDict, Dumper.represent_dict)
