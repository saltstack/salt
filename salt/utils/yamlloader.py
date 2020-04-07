# -*- coding: utf-8 -*-
"""
Custom YAML loading in Salt
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import warnings

import salt.utils.stringutils
import yaml  # pylint: disable=blacklisted-import
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, SequenceNode

try:
    yaml.Loader = yaml.CLoader
    yaml.Dumper = yaml.CDumper
    yaml.SafeLoader = yaml.CSafeLoader
    yaml.SafeDumper = yaml.CSafeDumper
except Exception:  # pylint: disable=broad-except
    pass


__all__ = ["SaltYamlSafeLoader", "load", "safe_load"]


class DuplicateKeyWarning(RuntimeWarning):
    """
    Warned when duplicate keys exist
    """


warnings.simplefilter("always", category=DuplicateKeyWarning)


# with code integrated from https://gist.github.com/844388
class SaltYamlSafeLoader(yaml.SafeLoader):
    """
    Create a custom YAML loader that uses the custom constructor. This allows
    for the YAML loading defaults to be manipulated based on needs within salt
    to make things like sls file more intuitive.
    """

    def __init__(self, stream, dictclass=dict):
        super(SaltYamlSafeLoader, self).__init__(stream)
        if dictclass is not dict:
            # then assume ordered dict and use it for both !map and !omap
            self.add_constructor("tag:yaml.org,2002:map", type(self).construct_yaml_map)
            self.add_constructor(
                "tag:yaml.org,2002:omap", type(self).construct_yaml_map
            )
        self.add_constructor("tag:yaml.org,2002:str", type(self).construct_yaml_str)
        self.add_constructor(
            "tag:yaml.org,2002:python/unicode", type(self).construct_unicode
        )
        self.add_constructor("tag:yaml.org,2002:timestamp", type(self).construct_scalar)
        self.dictclass = dictclass

    def construct_yaml_map(self, node):
        data = self.dictclass()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_unicode(self, node):
        return node.value

    def construct_mapping(self, node, deep=False):
        """
        Build the mapping for YAML
        """
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None,
                None,
                "expected a mapping node, but found {0}".format(node.id),
                node.start_mark,
            )

        self.flatten_mapping(node)

        context = "while constructing a mapping"
        mapping = self.dictclass()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError:
                raise ConstructorError(
                    context,
                    node.start_mark,
                    "found unacceptable key {0}".format(key_node.value),
                    key_node.start_mark,
                )
            value = self.construct_object(value_node, deep=deep)
            if key in mapping:
                raise ConstructorError(
                    context,
                    node.start_mark,
                    "found conflicting ID '{0}'".format(key),
                    key_node.start_mark,
                )
            mapping[key] = value
        return mapping

    def construct_scalar(self, node):
        """
        Verify integers and pass them in correctly is they are declared
        as octal
        """
        if node.tag == "tag:yaml.org,2002:int":
            if node.value == "0":
                pass
            elif node.value.startswith("0") and not node.value.startswith(("0b", "0x")):
                node.value = node.value.lstrip("0")
                # If value was all zeros, node.value would have been reduced to
                # an empty string. Change it to '0'.
                if node.value == "":
                    node.value = "0"
        return super(SaltYamlSafeLoader, self).construct_scalar(node)

    def construct_yaml_str(self, node):
        value = self.construct_scalar(node)
        return salt.utils.stringutils.to_unicode(value)

    def flatten_mapping(self, node):
        merge = []
        index = 0
        while index < len(node.value):
            key_node, value_node = node.value[index]

            if key_node.tag == "tag:yaml.org,2002:merge":
                del node.value[index]
                if isinstance(value_node, MappingNode):
                    self.flatten_mapping(value_node)
                    merge.extend(value_node.value)
                elif isinstance(value_node, SequenceNode):
                    submerge = []
                    for subnode in value_node.value:
                        if not isinstance(subnode, MappingNode):
                            raise ConstructorError(
                                "while constructing a mapping",
                                node.start_mark,
                                "expected a mapping for merging, but found {0}".format(
                                    subnode.id
                                ),
                                subnode.start_mark,
                            )
                        self.flatten_mapping(subnode)
                        submerge.append(subnode.value)
                    submerge.reverse()
                    for value in submerge:
                        merge.extend(value)
                else:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "expected a mapping or list of mappings for merging, but found {0}".format(
                            value_node.id
                        ),
                        value_node.start_mark,
                    )
            elif key_node.tag == "tag:yaml.org,2002:value":
                key_node.tag = "tag:yaml.org,2002:str"
                index += 1
            else:
                index += 1
        if merge:
            # Here we need to discard any duplicate entries based on key_node
            existing_nodes = [name_node.value for name_node, value_node in node.value]
            mergeable_items = [x for x in merge if x[0].value not in existing_nodes]

            node.value = mergeable_items + node.value


def load(stream, Loader=SaltYamlSafeLoader):
    return yaml.load(stream, Loader=Loader)


def safe_load(stream, Loader=SaltYamlSafeLoader):
    """
    .. versionadded:: 2018.3.0

    Helper function which automagically uses our custom loader.
    """
    return yaml.load(stream, Loader=Loader)
