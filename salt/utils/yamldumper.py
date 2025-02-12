"""
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

"""

# pylint: disable=W0232
#         class has no __init__ method


import collections

import yaml  # pylint: disable=blacklisted-import

import salt.utils.context
from salt.utils.odict import OrderedDict

try:
    from yaml import CDumper as Dumper
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    from yaml import Dumper, SafeDumper


__all__ = [
    "OrderedDumper",
    "SafeOrderedDumper",
    "IndentedSafeOrderedDumper",
    "get_dumper",
    "dump",
    "safe_dump",
]


class OrderedDumper(Dumper):
    """
    A YAML dumper that represents python OrderedDict as simple YAML map.
    """


class SafeOrderedDumper(SafeDumper):
    """
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    """


class IndentedSafeOrderedDumper(SafeOrderedDumper):
    """Like ``SafeOrderedDumper``, except it indents lists for readability."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(list(data.items()))


def represent_undefined(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "NULL")


# OrderedDumper does not inherit from SafeOrderedDumper, so any applicable
# representers added to SafeOrderedDumper must also be explicitly added to
# OrderedDumper.
for D in (SafeOrderedDumper, OrderedDumper):
    # This default registration matches types that don't match any other
    # registration, overriding PyYAML's default behavior of raising an
    # exception.  This representer instead produces null nodes.
    #
    # TODO: Why does this registration exist?  Isn't it better to raise an
    # exception for unsupported types?
    D.add_representer(None, represent_undefined)
    D.add_representer(OrderedDict, represent_ordereddict)
    D.add_representer(
        collections.defaultdict, yaml.representer.SafeRepresenter.represent_dict
    )
    D.add_representer(
        salt.utils.context.NamespacedDictWrapper,
        yaml.representer.SafeRepresenter.represent_dict,
    )
del D


def get_dumper(dumper_name):
    return {
        "OrderedDumper": OrderedDumper,
        "SafeOrderedDumper": SafeOrderedDumper,
        "IndentedSafeOrderedDumper": IndentedSafeOrderedDumper,
    }.get(dumper_name)


def dump(data, stream=None, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Helper that wraps yaml.dump and ensures that we encode unicode strings
    unless explicitly told not to.
    """
    kwargs.setdefault("allow_unicode", True)
    kwargs.setdefault("default_flow_style", None)
    return yaml.dump(data, stream, **kwargs)


def safe_dump(data, stream=None, **kwargs):
    """
    Use a custom dumper to ensure that defaultdict and OrderedDict are
    represented properly. Ensure that unicode strings are encoded unless
    explicitly told not to.
    """
    return dump(data, stream, Dumper=SafeOrderedDumper, **kwargs)
