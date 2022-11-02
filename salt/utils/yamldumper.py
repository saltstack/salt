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
from salt.version import SaltStackVersion

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


class _ExplicitTimestampMixin:
    """Disables the implicit timestamp resolver for Salt 3007 and later.

    Once support for ``yaml_compatibility`` less than 3007 is dropped, we can
    instead remove the implicit resolver entirely:

    .. code-block:: python

        class _RemoveImplicitResolverMixin:
            @classmethod
            def remove_implicit_resolver(cls, tag):
                cls.yaml_implicit_resolvers = {
                    first_char: [r for r in resolver_list if r[0] != tag]
                    for first_char, resolver_list in cls.yaml_implicit_resolvers.items()
                }

        _CommonMixin.remove_implicit_resolver("tag:yaml.org,2002:timestamp")
    """

    def resolve(self, kind, value, implicit):
        tag = super().resolve(kind, value, implicit)
        if (
            kind is yaml.ScalarNode
            and implicit[0]
            and tag == "tag:yaml.org,2002:timestamp"
            and _yaml_common.compat_ver() >= SaltStackVersion(3007)
        ):
            return self.DEFAULT_SCALAR_TAG
        return tag


class _CommonMixin(
    _ExplicitTimestampMixin,
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
_CommonMixin.V3006.add_representer(OrderedDict, _CommonMixin._rep_ordereddict)
# This multi representer covers collections.OrderedDict and all of its
# subclasses, including salt.utils.odict.OrderedDict.
_CommonMixin.V3007.add_multi_representer(
    collections.OrderedDict, _CommonMixin._rep_ordereddict
)
# This non-multi representer may seem redundant given the multi representer
# registered above, but it is needed to override the non-multi representer
# that exists in the ancestor Representer class.  (Non-multi representers
# take priority over multi representers.)
_CommonMixin.V3007.add_representer(
    collections.OrderedDict, _CommonMixin._rep_ordereddict
)
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


# This must inherit from yaml.SafeDumper, not yaml.CSafeDumper, because the
# increase_indent hack doesn't work with yaml.CSafeDumper.
# https://github.com/yaml/pyyaml/issues/234#issuecomment-786026671
class IndentedSafeOrderedDumper(_CommonMixin, yaml.SafeDumper):
    """Like ``SafeOrderedDumper``, except it indents lists for readability."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

    # TODO: Everything below this point is to provide backwards compatibility.
    # It can be removed once support for yaml_compatibility=3006 is dropped.

    class _Legacy(SafeOrderedDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    def __init__(self, *args, **kwargs):
        super().__setattr__("_in_init", True)
        try:
            super().__init__(*args, **kwargs)
            Legacy = super().__getattribute__("_Legacy")
            super().__setattr__("_legacy", Legacy(*args, **kwargs))
        finally:
            super().__setattr__("_in_init", False)

    def _use_legacy(self):
        if super().__getattribute__("_in_init"):
            return False
        return _yaml_common.compat_ver() < SaltStackVersion(3007)

    def __getattribute__(self, name):
        if super().__getattribute__("_use_legacy")():
            return getattr(super().__getattribute__("_legacy"), name)
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if super().__getattribute__("_use_legacy")():
            return setattr(super().__getattribute__("_legacy"), name, value)
        return super().__setattr__(name, value)

    def __delattr__(self, name):
        if super().__getattribute__("_use_legacy")():
            return delattr(super().__getattribute__("_legacy"), name)
        return super().__delattr__(name)


def get_dumper(dumper_name):
    return {
        "OrderedDumper": OrderedDumper,
        "SafeOrderedDumper": SafeOrderedDumper,
        "IndentedSafeOrderedDumper": IndentedSafeOrderedDumper,
    }.get(dumper_name)


def dump(data, stream=None, **kwargs):
    """
    .. versionadded:: 2018.3.0

    .. versionchanged:: 3007.0

        The default ``Dumper`` class is now ``OrderedDumper`` instead of
        ``yaml.Dumper``.  Set the ``yaml_compatibility`` option to "3006" to
        revert to the previous behavior.

    Helper that wraps yaml.dump and ensures that we encode unicode strings
    unless explicitly told not to.
    """
    kwargs.setdefault("allow_unicode", True)
    kwargs.setdefault("default_flow_style", None)
    if "Dumper" not in kwargs and _yaml_common.compat_ver() >= SaltStackVersion(3007):
        kwargs["Dumper"] = OrderedDumper
    return yaml.dump(data, stream, **kwargs)


def safe_dump(data, stream=None, **kwargs):
    """
    Use a custom dumper to ensure that defaultdict and OrderedDict are
    represented properly. Ensure that unicode strings are encoded unless
    explicitly told not to.
    """
    return dump(data, stream, Dumper=SafeOrderedDumper, **kwargs)
