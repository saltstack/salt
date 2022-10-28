"""
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

"""
# pylint: disable=W0232
#         class has no __init__ method


import collections

import yaml  # pylint: disable=blacklisted-import

import salt.utils._yaml_common as _yaml_common
import salt.utils.context
from salt.utils.decorators import classproperty
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


class _InheritedRepresentersMixin(
    _yaml_common.InheritMapMixin,
    inherit_map_attrs={
        # The ChainMap used for yaml_representers is not saved directly to
        # cls.yaml_representers because _yaml_common.VersionedSubclassesMixin is
        # used to automatically switch between versioned variants of the
        # ChainMap, and we still need access to the unversioned ChainMap (for
        # add_representer(), and for subclasses to chain off of).
        "_reps": "yaml_representers",
        # Same goes for _mreps.
        "_mreps": "yaml_multi_representers",
    },
):
    @classproperty
    def yaml_representers(cls):  # pylint: disable=no-self-argument
        return cls._reps

    @classproperty
    def yaml_multi_representers(cls):  # pylint: disable=no-self-argument
        return cls._mreps

    @classmethod
    def add_representer(cls, data_type, rep):
        cls._reps[data_type] = rep

    @classmethod
    def add_multi_representer(cls, data_type, rep):
        cls._mreps[data_type] = rep


class _VersionedRepresentersMixin(
    _yaml_common.VersionedSubclassesMixin,
    versioned_properties=(
        "yaml_implicit_resolvers",
        "yaml_multi_representers",
        "yaml_representers",
    ),
):
    pass


class _CommonMixin(
    _VersionedRepresentersMixin,
    _InheritedRepresentersMixin,
):
    def _rep_ordereddict(self, data):
        return self.represent_dict(list(data.items()))

    def _rep_default(self, data):
        """Represent types that don't match any other registered representers.

        PyYAML's default behavior for unsupported types is to raise an
        exception.  This representer instead produces null nodes.

        Note: This representer does not affect ``Dumper``-derived classes
        because ``Dumper`` has a multi representer registered for ``object``
        that will match every object before PyYAML falls back to this
        representer.

        """
        return self.represent_scalar("tag:yaml.org,2002:null", "NULL")


# TODO: Why does this registration exist?  Isn't it better to raise an exception
# for unsupported types?
_CommonMixin.add_representer(None, _CommonMixin._rep_default)
_CommonMixin.add_representer(OrderedDict, _CommonMixin._rep_ordereddict)
_CommonMixin.add_representer(
    collections.defaultdict, yaml.representer.SafeRepresenter.represent_dict
)
_CommonMixin.add_representer(
    salt.utils.context.NamespacedDictWrapper,
    yaml.representer.SafeRepresenter.represent_dict,
)


class OrderedDumper(_CommonMixin, Dumper):
    """
    A YAML dumper that represents python OrderedDict as simple YAML map.
    """


class SafeOrderedDumper(_CommonMixin, SafeDumper):
    """
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    """


class IndentedSafeOrderedDumper(SafeOrderedDumper):
    """Like ``SafeOrderedDumper``, except it indents lists for readability."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


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
