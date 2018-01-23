# -*- coding: utf-8 -*-
'''
    salt.serializers.yamlex
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    YAMLEX is a format that allows for things like sls files to be
    more intuitive.

    It's an extension of YAML that implements all the salt magic:
    - it implies omap for any dict like.
    - it implies that string like data are str, not unicode
    - ...

    For example, the file `states.sls` has this contents:

    .. code-block:: yaml

        foo:
          bar: 42
          baz: [1, 2, 3]

    The file can be parsed into Python like this

    .. code-block:: python

        from salt.serializers import yamlex

        with open('state.sls', 'r') as stream:
            obj = yamlex.deserialize(stream)

    Check that ``obj`` is an OrderedDict

    .. code-block:: python

        from salt.utils.odict import OrderedDict

        assert isinstance(obj, dict)
        assert isinstance(obj, OrderedDict)


    yamlex `__repr__` and `__str__` objects' methods render YAML understandable
    string. It means that they are template friendly.


    .. code-block:: python

        print '{0}'.format(obj)

    returns:

    ::

        {foo: {bar: 42, baz: [1, 2, 3]}}

    and they are still valid YAML:

    .. code-block:: python

        from salt.serializers import yaml
        yml_obj = yaml.deserialize(str(obj))
        assert yml_obj == obj

    yamlex implements also custom tags:

    !aggregate

         this tag allows structures aggregation.

        For example:


        .. code-block:: yaml

            placeholder: !aggregate foo
            placeholder: !aggregate bar
            placeholder: !aggregate baz

        is rendered as

        .. code-block:: yaml

            placeholder: [foo, bar, baz]

    !reset

         this tag flushes the computing value.

        .. code-block:: yaml

            placeholder: {!aggregate foo: {foo: 42}}
            placeholder: {!aggregate foo: {bar: null}}
            !reset placeholder: {!aggregate foo: {baz: inga}}

        is roughly equivalent to

        .. code-block:: yaml

            placeholder: {!aggregate foo: {baz: inga}}

    Document is defacto an aggregate mapping.
'''
# pylint: disable=invalid-name,no-member,missing-docstring,no-self-use
# pylint: disable=too-few-public-methods,too-many-public-methods

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import datetime
import logging


# Import Salt Libs
from salt.serializers import DeserializationError, SerializationError
from salt.utils.aggregation import aggregate, Map, Sequence
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
import yaml
from yaml.nodes import MappingNode
from yaml.constructor import ConstructorError
from yaml.scanner import ScannerError
from salt.ext import six

__all__ = ['deserialize', 'serialize', 'available']

log = logging.getLogger(__name__)

available = True

# prefer C bindings over python when available
# CSafeDumper causes test failures under python3
BaseLoader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
BaseDumper = yaml.SafeDumper if six.PY3 else getattr(yaml, 'CSafeDumper', yaml.SafeDumper)

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


class Loader(BaseLoader):  # pylint: disable=W0232
    '''
    Create a custom YAML loader that uses the custom constructor. This allows
    for the YAML loading defaults to be manipulated based on needs within salt
    to make things like sls file more intuitive.
    '''

    DEFAULT_SCALAR_TAG = 'tag:yaml.org,2002:str'
    DEFAULT_SEQUENCE_TAG = 'tag:yaml.org,2002:seq'
    DEFAULT_MAPPING_TAG = 'tag:yaml.org,2002:omap'

    def compose_document(self):
        node = BaseLoader.compose_document(self)
        node.tag = '!aggregate'
        return node

    def construct_yaml_omap(self, node):
        '''
        Build the SLSMap
        '''
        sls_map = SLSMap()
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None,
                None,
                'expected a mapping node, but found {0}'.format(node.id),
                node.start_mark)

        self.flatten_mapping(node)

        for key_node, value_node in node.value:

            # !reset instruction applies on document only.
            # It tells to reset previous decoded value for this present key.
            reset = key_node.tag == '!reset'

            # even if !aggregate tag apply only to values and not keys
            # it's a reason to act as a such nazi.
            if key_node.tag == '!aggregate':
                log.warning('!aggregate applies on values only, not on keys')
                value_node.tag = key_node.tag
                key_node.tag = self.resolve_sls_tag(key_node)[0]

            key = self.construct_object(key_node, deep=False)
            try:
                hash(key)
            except TypeError:
                err = ('While constructing a mapping {0} found unacceptable '
                       'key {1}').format(node.start_mark, key_node.start_mark)
                raise ConstructorError(err)
            value = self.construct_object(value_node, deep=False)
            if key in sls_map and not reset:
                value = merge_recursive(sls_map[key], value)
            sls_map[key] = value
        return sls_map

    def construct_sls_str(self, node):
        '''
        Build the SLSString.
        '''

        # Ensure obj is str, not py2 unicode or py3 bytes
        obj = self.construct_scalar(node)
        if six.PY2:
            obj = obj.encode('utf-8')
        return SLSString(obj)

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

    def construct_sls_aggregate(self, node):
        try:
            tag, deep = self.resolve_sls_tag(node)
        except:
            raise ConstructorError('unable to build reset')

        node = copy.copy(node)
        node.tag = tag
        obj = self.construct_object(node, deep)
        if obj is None:
            return AggregatedSequence()
        elif tag == self.DEFAULT_MAPPING_TAG:
            return AggregatedMap(obj)
        elif tag == self.DEFAULT_SEQUENCE_TAG:
            return AggregatedSequence(obj)
        return AggregatedSequence([obj])

    def construct_sls_reset(self, node):
        try:
            tag, deep = self.resolve_sls_tag(node)
        except:
            raise ConstructorError('unable to build reset')

        node = copy.copy(node)
        node.tag = tag

        return self.construct_object(node, deep)

    def resolve_sls_tag(self, node):
        if isinstance(node, yaml.nodes.ScalarNode):
            # search implicit tag
            tag = self.resolve(yaml.nodes.ScalarNode, node.value, [True, True])
            deep = False
        elif isinstance(node, yaml.nodes.SequenceNode):
            tag = self.DEFAULT_SEQUENCE_TAG
            deep = True
        elif isinstance(node, yaml.nodes.MappingNode):
            tag = self.DEFAULT_MAPPING_TAG
            deep = True
        else:
            raise ConstructorError('unable to resolve tag')
        return tag, deep


Loader.add_constructor('!aggregate', Loader.construct_sls_aggregate)  # custom type
Loader.add_constructor('!reset', Loader.construct_sls_reset)  # custom type
Loader.add_constructor('tag:yaml.org,2002:omap', Loader.construct_yaml_omap)  # our overwrite
Loader.add_constructor('tag:yaml.org,2002:str', Loader.construct_sls_str)  # our overwrite
Loader.add_constructor('tag:yaml.org,2002:int', Loader.construct_sls_int)  # our overwrite
Loader.add_multi_constructor('tag:yaml.org,2002:null', Loader.construct_yaml_null)
Loader.add_multi_constructor('tag:yaml.org,2002:bool', Loader.construct_yaml_bool)
Loader.add_multi_constructor('tag:yaml.org,2002:float', Loader.construct_yaml_float)
Loader.add_multi_constructor('tag:yaml.org,2002:binary', Loader.construct_yaml_binary)
Loader.add_multi_constructor('tag:yaml.org,2002:timestamp', Loader.construct_yaml_timestamp)
Loader.add_multi_constructor('tag:yaml.org,2002:pairs', Loader.construct_yaml_pairs)
Loader.add_multi_constructor('tag:yaml.org,2002:set', Loader.construct_yaml_set)
Loader.add_multi_constructor('tag:yaml.org,2002:seq', Loader.construct_yaml_seq)
Loader.add_multi_constructor('tag:yaml.org,2002:map', Loader.construct_yaml_map)
Loader.add_multi_constructor(None, Loader.construct_undefined)


class SLSMap(OrderedDict):
    '''
    Ensures that dict str() and repr() are YAML friendly.

    .. code-block:: python

        >>> mapping = OrderedDict([('a', 'b'), ('c', None)])
        >>> print mapping
        OrderedDict([('a', 'b'), ('c', None)])

        >>> sls_map = SLSMap(mapping)
        >>> print sls_map.__str__()
        {a: b, c: null}

    '''

    def __str__(self):
        return serialize(self, default_flow_style=True)

    def __repr__(self, _repr_running=None):
        return serialize(self, default_flow_style=True)


class SLSString(str):
    '''
    Ensures that str str() and repr() are YAML friendly.

    .. code-block:: python

        >>> scalar = str('foo')
        >>> print 'foo'
        foo

        >>> sls_scalar = SLSString(scalar)
        >>> print sls_scalar
        "foo"

    '''

    def __str__(self):
        return serialize(self, default_style='"')

    def __repr__(self):
        return serialize(self, default_style='"')


class AggregatedMap(SLSMap, Map):
    pass


class AggregatedSequence(Sequence):
    pass


class Dumper(BaseDumper):  # pylint: disable=W0232
    '''
    sls dumper.
    '''
    def represent_odict(self, data):
        return self.represent_mapping('tag:yaml.org,2002:map', list(data.items()))

Dumper.add_multi_representer(type(None), Dumper.represent_none)
if six.PY2:
    Dumper.add_multi_representer(six.binary_type, Dumper.represent_str)
    Dumper.add_multi_representer(six.text_type, Dumper.represent_unicode)
    Dumper.add_multi_representer(long, Dumper.represent_long)  # pylint: disable=incompatible-py3-code
else:
    Dumper.add_multi_representer(six.binary_type, Dumper.represent_binary)
    Dumper.add_multi_representer(six.text_type, Dumper.represent_str)
Dumper.add_multi_representer(bool, Dumper.represent_bool)
Dumper.add_multi_representer(int, Dumper.represent_int)
Dumper.add_multi_representer(float, Dumper.represent_float)
Dumper.add_multi_representer(list, Dumper.represent_list)
Dumper.add_multi_representer(tuple, Dumper.represent_list)
Dumper.add_multi_representer(dict, Dumper.represent_odict)  # make every dict like obj to be represented as a map
Dumper.add_multi_representer(set, Dumper.represent_set)
Dumper.add_multi_representer(datetime.date, Dumper.represent_date)
Dumper.add_multi_representer(datetime.datetime, Dumper.represent_datetime)
Dumper.add_multi_representer(None, Dumper.represent_undefined)


def merge_recursive(obj_a, obj_b, level=False):
    '''
    Merge obj_b into obj_a.
    '''
    return aggregate(obj_a, obj_b, level,
                     map_class=AggregatedMap,
                     sequence_class=AggregatedSequence)
