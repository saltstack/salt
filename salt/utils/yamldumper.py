"""
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

"""

# pylint: disable=W0232
#         class has no __init__ method


import collections
from collections import OrderedDict

import yaml  # pylint: disable=blacklisted-import

import salt.utils.context
from salt.utils.datastructures import HashableOrderedDict
from salt.utils.optsdict import DictProxy, ListProxy, OptsDict

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


class IndentMixin(Dumper):
    """
    Mixin that improves YAML dumped list readability
    by indenting them by two spaces,
    instead of being flush with the key they are under.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


class OrderedDumper(Dumper):
    """
    A YAML dumper that represents python OrderedDict as simple YAML map.
    """


class SafeOrderedDumper(SafeDumper):
    """
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    """


class IndentedSafeOrderedDumper(IndentMixin, SafeOrderedDumper):
    """
    A YAML safe dumper that represents python OrderedDict as simple YAML map,
    and also indents lists by two spaces.
    """


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(list(data.items()))


def represent_undefined(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "NULL")


def represent_optsdict(dumper, data):
    """Represent OptsDict as a plain dict for YAML serialization."""
    # Use to_dict() to recursively convert proxies to plain types
    return dumper.represent_dict(data.to_dict())


def represent_dictproxy(dumper, data):
    """Represent DictProxy as a plain dict for YAML serialization."""
    return dumper.represent_dict(dict(data))


def represent_listproxy(dumper, data):
    """Represent ListProxy as a plain list for YAML serialization."""
    return dumper.represent_list(list(data))


OrderedDumper.add_representer(OrderedDict, represent_ordereddict)
OrderedDumper.add_representer(HashableOrderedDict, represent_ordereddict)
SafeOrderedDumper.add_representer(OrderedDict, represent_ordereddict)
SafeOrderedDumper.add_representer(HashableOrderedDict, represent_ordereddict)
SafeOrderedDumper.add_representer(None, represent_undefined)

OrderedDumper.add_representer(
    collections.defaultdict, yaml.representer.SafeRepresenter.represent_dict
)
SafeOrderedDumper.add_representer(
    collections.defaultdict, yaml.representer.SafeRepresenter.represent_dict
)
OrderedDumper.add_representer(
    salt.utils.context.NamespacedDictWrapper,
    yaml.representer.SafeRepresenter.represent_dict,
)
SafeOrderedDumper.add_representer(
    salt.utils.context.NamespacedDictWrapper,
    yaml.representer.SafeRepresenter.represent_dict,
)

OrderedDumper.add_representer(OptsDict, represent_optsdict)
SafeOrderedDumper.add_representer(OptsDict, represent_optsdict)
OrderedDumper.add_representer(DictProxy, represent_dictproxy)
SafeOrderedDumper.add_representer(DictProxy, represent_dictproxy)
OrderedDumper.add_representer(ListProxy, represent_listproxy)
SafeOrderedDumper.add_representer(ListProxy, represent_listproxy)
# Also register with base YAML dumpers for salt.utils.yaml.dump()
yaml.Dumper.add_representer(OptsDict, represent_optsdict)
yaml.SafeDumper.add_representer(OptsDict, represent_optsdict)
yaml.Dumper.add_representer(DictProxy, represent_dictproxy)
yaml.SafeDumper.add_representer(DictProxy, represent_dictproxy)
yaml.Dumper.add_representer(ListProxy, represent_listproxy)
yaml.SafeDumper.add_representer(ListProxy, represent_listproxy)

OrderedDumper.add_representer(
    "tag:yaml.org,2002:timestamp", OrderedDumper.represent_scalar
)
SafeOrderedDumper.add_representer(
    "tag:yaml.org,2002:timestamp", SafeOrderedDumper.represent_scalar
)


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
    if "allow_unicode" not in kwargs:
        kwargs["allow_unicode"] = True
    kwargs.setdefault("default_flow_style", None)
    return yaml.dump(data, stream, **kwargs)


def safe_dump(data, stream=None, **kwargs):
    """
    Use a custom dumper to ensure that defaultdict and OrderedDict are
    represented properly. Ensure that unicode strings are encoded unless
    explicitly told not to.
    """
    if "allow_unicode" not in kwargs:
        kwargs["allow_unicode"] = True
    kwargs.setdefault("default_flow_style", None)
    return yaml.dump(data, stream, Dumper=SafeOrderedDumper, **kwargs)
