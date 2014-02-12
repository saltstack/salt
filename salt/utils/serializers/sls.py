# -*- coding: utf-8 -*-
'''
    salt.utils.serializers.sls
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    SLS is a format that allows to make things like sls file more intuitive.

    It's an extension of YAML that implements all the salt magic.
    For example it implies omap for any dict like.

    For example, the file `states.sls` has this contents:

    .. code-block:: yaml

        foo:
          bar: 42
          baz: [1, 2, 3]

    The file can be parsed into Python like this

    .. code-block:: python

        from salt.utils.serializers import sls

        with open('state.sls', 'r') as stream:
            obj = sls.deserialize(stream)

    Check that ``obj`` is an OrderedDict

    .. code-block:: python

        from salt.utils.odict import OrderedDict

        assert isinstance(obj, dict)
        assert isinstance(obj, OrderedDict)


    Silas `__repr__` and `__str__` objects' methods render YAML understandable
    string. It means that they are template friendly.


    .. code-block:: python

        print '{0}'.format(obj)

    returns:

    ::

        {foo: {bar: 42, baz: [1, 2, 3]}}

    and they are still valid YAML:

    .. code-block:: python

        from salt.utils.serializers import yaml
        yml_obj = yaml.deserialize(str(obj))
        assert yml_obj == obj
'''

from __future__ import absolute_import
import logging

import yaml
from yaml.nodes import MappingNode
from yaml.constructor import ConstructorError
from yaml.scanner import ScannerError

from salt._compat import string_types
from salt.utils.serializers import DeserializationError, SerializationError
from salt.utils.odict import OrderedDict

__all__ = ['deserialize', 'serialize', 'available']

log = logging.getLogger(__name__)

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

    options.setdefault('Loader', SLSLoader)
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

    options.setdefault('Dumper', SLSDumper)
    try:
        response = yaml.dump(obj, **options)
        if response.endswith('\n...\n'):
            return response[:-5]
        if response.endswith('\n'):
            return response[:-1]
        return response
    except Exception as error:
        raise SerializationError(error)


def ignore(key, old, new):
    return new


def warning(key, old, new):
    log.warn('Conflicting ID "{0}"'.format(key))
    return new


def error(key, old, new):  # pylint: disable=W0611
    raise ConstructorError('Conflicting ID "{0}"'.format(key))


class SLSLoader(Loader):
    '''
    Create a custom YAML loader that uses the custom constructor. This allows
    for the YAML loading defaults to be manipulated based on needs within salt
    to make things like sls file more intuitive.
    '''

    # who should we resolve conflicting ids?
    conflict_resolver = None

    def __init__(self, stream, conflict_resolver=None):
        Loader.__init__(self, stream)
        self.conflict_resolver = conflict_resolver or ignore

    def construct_sls_map(self, node):
        '''
        Build the SLSMap
        '''
        sls_map = SLSMap()
        yield sls_map

        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None,
                None,
                'expected a mapping node, but found {0}'.format(node.id),
                node.start_mark)

        self.flatten_mapping(node)

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=False)
            try:
                hash(key)
            except TypeError:
                err = ('While constructing a mapping {0} found unacceptable '
                       'key {1}').format(node.start_mark, key_node.start_mark)
                raise ConstructorError(err)
            value = self.construct_object(value_node, deep=False)
            if key in sls_map:
                self.conflict_resolver(key, sls_map[key], value)
            sls_map[key] = value

    def construct_sls_int(self, node):
        '''
        Verify integers and pass them in correctly is they are declared
        as octal
        '''
        if node.value == '0':
            pass
        elif node.value.startswith('0') \
                and not node.value.startswith(('0b', '0x')):
            node.value = node.value.lstrip('0')
            # If value was all zeros, node.value would have been reduced to
            # an empty string. Change it to '0'.
            if node.value == '':
                node.value = '0'
        return int(node.value)

SLSLoader.add_constructor('tag:yaml.org,2002:map', SLSLoader.construct_sls_map)  # NOQA
SLSLoader.add_constructor('tag:yaml.org,2002:omap', SLSLoader.construct_sls_map)  # NOQA
SLSLoader.add_constructor('tag:yaml.org,2002:int', SLSLoader.construct_sls_int)


class SLSMap(OrderedDict):
    '''
    Ensures that dict str() and repr() are YAML friendly.

    .. code-block:: python

        mapping = OrderedDict([('a', 'b'), ('c', None)])
        print mapping
        # OrderedDict([('a', 'b'), ('c', None)])

        sls_map = SLSMap(mapping)
        print sls_map
        # {'a': 'b', 'c': None}

    '''

    def __str__(self):
        output = []
        for key, value in self.items():
            if isinstance(value, string_types):
                # keeps quotes around strings
                output.append('{0!r}: {1!r}'.format(key, value))
            else:
                # let default output
                output.append('{0!r}: {1!s}'.format(key, value))
        return '{' + ', '.join(output) + '}'

    def __repr__(self):  # pylint: disable=W0221
        output = []
        for key, value in self.items():
            output.append('{0!r}: {1!r}'.format(key, value))
        return '{' + ', '.join(output) + '}'


class SLSDumper(Dumper):  # pylint: disable=W0232
    def represent_odict(self, data):
        return self.represent_dict(data.items())
        return self.represent_mapping('tag:yaml.org,2002:map', data.items())

# make every dict like obj to be represented as a map
SLSDumper.add_multi_representer(dict, SLSDumper.represent_odict)
