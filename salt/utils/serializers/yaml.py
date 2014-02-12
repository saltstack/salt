# -*- coding: utf-8 -*-
'''
    salt.utils.serializers.yaml
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements YAML serializer.

    Underneath, it is based on pyyaml and use the safe dumper and loader.
    It also use C bindings if they are available.
'''

from __future__ import absolute_import

import yaml
from yaml.constructor import ConstructorError
from yaml.scanner import ScannerError

from salt.utils.serializers import DeserializationError, SerializationError

__all__ = ['deserialize', 'serialize', 'available']

available = True

# prefer C bindings over python when available
Loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
Dumper = getattr(yaml, 'CSafeDumper', yaml.SafeDumper)

ERROR_MAP = {
    ("found character '\\t' "
     "that cannot start any token"): 'Illegal tab character'
}


def deserialize(stream_or_string, **options):
    """
    Deserialize any string of stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower yaml module.
    """

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
    """
    Serialize Python data to YAML.

    :param obj: the datastructure to serialize
    :param options: options given to lower yaml module.
    """

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
