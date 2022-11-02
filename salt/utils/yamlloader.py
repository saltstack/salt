"""
Custom YAML loading in Salt
"""


import collections

import yaml  # pylint: disable=blacklisted-import
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, SequenceNode

import salt.utils._yaml_common as _yaml_common
import salt.utils.stringutils
from salt.utils.decorators import classproperty

# prefer C bindings over python when available
BaseLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


__all__ = ["SaltYamlSafeLoader", "load", "safe_load"]


class _InheritedConstructorsMixin(
    _yaml_common.InheritMapMixin,
    inherit_map_attrs={
        # The ChainMap used for yaml_constructors is not saved directly to
        # cls.yaml_constructors because _yaml_common.VersionedSubclassesMixin is
        # used to automatically switch between versioned variants of the
        # ChainMap, and we still need access to the unversioned ChainMap (for
        # add_constructor(), and for subclasses to chain off of).
        "_ctors": "yaml_constructors",
        # Same goes for _mctors.
        "_mctors": "yaml_multi_constructors",
    },
):
    @classproperty
    def yaml_constructors(cls):  # pylint: disable=no-self-argument
        return cls._ctors

    @classproperty
    def yaml_multi_constructors(cls):  # pylint: disable=no-self-argument
        return cls._mctors

    @classmethod
    def add_constructor(cls, tag, constructor):
        cls._ctors[tag] = constructor

    @classmethod
    def add_multi_constructor(cls, tag_prefix, multi_constructor):
        cls._mctors[tag_prefix] = multi_constructor


class _VersionedConstructorsMixin(
    _yaml_common.VersionedSubclassesMixin,
    versioned_properties=(
        "yaml_constructors",
        "yaml_implicit_resolvers",
        "yaml_multi_constructors",
    ),
):
    pass


# with code integrated from https://gist.github.com/844388
class SaltYamlSafeLoader(
    _VersionedConstructorsMixin,
    _InheritedConstructorsMixin,
    BaseLoader,
):
    """
    Create a custom YAML loader that uses the custom constructor. This allows
    for the YAML loading defaults to be manipulated based on needs within salt
    to make things like sls file more intuitive.
    """

    @classmethod
    def remove_implicit_resolver(cls, tag):
        """Remove a previously registered implicit resolver for a tag."""
        cls.yaml_implicit_resolvers = {
            first_char: [r for r in resolver_list if r[0] != tag]
            for first_char, resolver_list in cls.yaml_implicit_resolvers.items()
        }

    def __init__(self, stream, dictclass=dict):
        super().__init__(stream)
        self.dictclass = dictclass

    def construct_yaml_map(self, node):
        if self.dictclass is dict:
            return (yield from super().construct_yaml_map(node))
        data = self.dictclass()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_yaml_omap_3006(self, node):
        if self.dictclass is dict:
            return (yield from super().construct_yaml_omap(node))
        return (yield from self.construct_yaml_map(node))

    def construct_yaml_omap(self, node):
        # BaseLoader.construct_yaml_omap() returns a list of (key, value)
        # tuples, which doesn't match the semantics of the `!!omap` YAML type.
        # Convert the list of tuples to an OrderedDict.
        d = collections.OrderedDict()
        yield d
        (entries,) = super().construct_yaml_omap(node)
        # All of the following lines could be replaced with `d.update(entries)`,
        # but we want to detect and reject any duplicate keys in `entries`.
        if hasattr(entries, "keys"):
            entries = ((k, entries[k]) for k in entries.keys())
        for k, v in entries:
            if k in d:
                raise ConstructorError(
                    f"while constructing an ordered map",
                    node.start_mark,
                    f"duplicate key encountered: {k!r}",
                    # TODO: Can we get the location of the duplicate key?
                    node.start_mark,
                )
            d[k] = v

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
                "expected a mapping node, but found {}".format(node.id),
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
                    "found unacceptable key {}".format(key_node.value),
                    key_node.start_mark,
                )
            value = self.construct_object(value_node, deep=deep)
            if key in mapping:
                raise ConstructorError(
                    context,
                    node.start_mark,
                    "found conflicting ID '{}'".format(key),
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
        return super().construct_scalar(node)

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
                                "expected a mapping for merging, but found {}".format(
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
                        "expected a mapping or list of mappings for merging, but"
                        " found {}".format(value_node.id),
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


# The add_constructor() method is a class method, not an instance method, so
# custom constructors should be registered at class creation time, not instance
# creation time.
SaltYamlSafeLoader.add_constructor(
    "tag:yaml.org,2002:map", SaltYamlSafeLoader.construct_yaml_map
)
SaltYamlSafeLoader.add_constructor(
    "tag:yaml.org,2002:omap", SaltYamlSafeLoader.construct_yaml_omap
)
SaltYamlSafeLoader.V3006.add_constructor(
    "tag:yaml.org,2002:omap", SaltYamlSafeLoader.construct_yaml_omap_3006
)
SaltYamlSafeLoader.add_constructor(
    "tag:yaml.org,2002:python/unicode", SaltYamlSafeLoader.construct_unicode
)
SaltYamlSafeLoader.add_constructor(
    "tag:yaml.org,2002:str", SaltYamlSafeLoader.construct_yaml_str
)
SaltYamlSafeLoader.V3006.add_constructor(
    "tag:yaml.org,2002:timestamp", SaltYamlSafeLoader.construct_scalar
)

# Require users to explicitly provide the `!!timestamp` tag if a datetime object
# is desired.
SaltYamlSafeLoader.V3007.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


def load(stream, Loader=SaltYamlSafeLoader):
    return yaml.load(stream, Loader=Loader)


def safe_load(stream, Loader=SaltYamlSafeLoader):
    """
    .. versionadded:: 2018.3.0

    Helper function which automagically uses our custom loader.
    """
    return yaml.load(stream, Loader=Loader)
