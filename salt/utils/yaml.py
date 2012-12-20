# Import python libs
from __future__ import absolute_import
import warnings

# Import third party libs
import yaml
from yaml.nodes import MappingNode
from yaml.constructor import ConstructorError
try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
except Exception:
    pass

load = yaml.load


class DuplicateKeyWarning(RuntimeWarning):
    '''
    Warned when duplicate keys exist
    '''

warnings.simplefilter('always', category=DuplicateKeyWarning)

# with code integrated form https://gist.github.com/844388
class CustomLoader(yaml.SafeLoader):
    '''
    Create a custom yaml loader that uses the custom constructor. This allows
    for the yaml loading defaults to be manipulated based on needs within salt
    to make things like sls file more intuitive.
    '''
    def __init__(self, stream, dictclass=dict):
        yaml.SafeLoader.__init__(self, stream)
        if dictclass is not dict:
            # then assume ordred dict and use it for both !map and !omap
            self.add_constructor(u'tag:yaml.org,2002:map', type(self).construct_yaml_map)
            self.add_constructor(u'tag:yaml.org,2002:omap', type(self).construct_yaml_map)
        self.dictclass = dictclass

    def construct_yaml_map(self, node):
        data = self.dictclass()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        '''
        Build the mapping for yaml
        '''
        if not isinstance(node, MappingNode):
            raise ConstructorError(None, None,
                    'expected a mapping node, but found {0}'.format(node.id),
                    node.start_mark)

        self.flatten_mapping(node)

        mapping = self.dictclass()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError:
                err = ('While constructing a mapping {0} found unacceptable '
                       'key {1}').format(node.start_mark, key_node.start_mark)
                raise ConstructorError(err)
            value = self.construct_object(value_node, deep=deep)
            if key in mapping:
                warnings.warn(
                    'Duplicate Key: "{0}"'.format(key), DuplicateKeyWarning)
            mapping[key] = value
        return mapping

    def construct_scalar(self, node):
        '''
        Verify integers and pass them in correctly is they are declared
        as octal
        '''
        if node.tag == 'tag:yaml.org,2002:int':
            if node.value == '0':
                pass
            elif node.value.startswith('0') \
                    and not node.value.startswith(('0b', '0x')):
                node.value = node.value.lstrip('0')
        return yaml.constructor.SafeConstructor.construct_scalar(self, node)

