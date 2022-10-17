"""
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

"""
# pylint: disable=W0232
#         class has no __init__ method


import collections

import yaml  # pylint: disable=blacklisted-import

import salt.utils.context

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


class _RemoveImplicitResolverMixin:
    @classmethod
    def remove_implicit_resolver(cls, tag):
        """Remove a previously registered implicit resolver for a tag."""
        cls.yaml_implicit_resolvers = {
            first_char: [r for r in resolver_list if r[0] != tag]
            for first_char, resolver_list in cls.yaml_implicit_resolvers.items()
        }


class OrderedDumper(Dumper, _RemoveImplicitResolverMixin):
    """
    A YAML dumper that represents python OrderedDict as simple YAML map.
    """


class SafeOrderedDumper(SafeDumper, _RemoveImplicitResolverMixin):
    """
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    """


# This must inherit from yaml.SafeDumper, not yaml.CSafeDumper, because the
# increase_indent hack doesn't work with yaml.CSafeDumper.
# https://github.com/yaml/pyyaml/issues/234#issuecomment-786026671
class IndentedSafeOrderedDumper(yaml.SafeDumper, _RemoveImplicitResolverMixin):
    """Like ``SafeOrderedDumper``, except it indents lists for readability."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(list(data.items()))


def represent_undefined(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "NULL")


# The above Dumper classes do not inherit from each other, so any applicable
# representers must be added to each.
for D in (SafeOrderedDumper, IndentedSafeOrderedDumper):
    # TODO: Why does this representer exist?  It doesn't seem to do anything
    # different compared to PyYAML's yaml.SafeDumper.
    # TODO: Why isn't this representer also registered with OrderedDumper?
    D.add_representer(None, represent_undefined)
for D in (SafeOrderedDumper, IndentedSafeOrderedDumper, OrderedDumper):
    # This multi representer covers collections.OrderedDict and all of its
    # subclasses, including salt.utils.odict.OrderedDict.
    D.add_multi_representer(collections.OrderedDict, represent_ordereddict)
    # This non-multi representer may seem redundant given the multi representer
    # registered above, but it is needed to override the non-multi representer
    # that exists in the ancestor Representer class.  (Non-multi representers
    # take priority over multi representers.)
    D.add_representer(collections.OrderedDict, represent_ordereddict)
    D.add_representer(
        collections.defaultdict, yaml.representer.SafeRepresenter.represent_dict
    )
    D.add_representer(
        salt.utils.context.NamespacedDictWrapper,
        yaml.representer.SafeRepresenter.represent_dict,
    )
    # Explicitly include the `!!timestamp` tag when dumping datetime objects.
    D.remove_implicit_resolver("tag:yaml.org,2002:timestamp")
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

    .. versionchanged:: 3006.0

        The default ``Dumper`` class is now ``OrderedDumper`` instead of
        ``yaml.Dumper``.

    Helper that wraps yaml.dump and ensures that we encode unicode strings
    unless explicitly told not to.
    """
    kwargs = {
        "allow_unicode": True,
        "default_flow_style": None,
        "Dumper": OrderedDumper,
        **kwargs,
    }
    return yaml.dump(data, stream, **kwargs)


def safe_dump(data, stream=None, **kwargs):
    """
    Use a custom dumper to ensure that defaultdict and OrderedDict are
    represented properly. Ensure that unicode strings are encoded unless
    explicitly told not to.
    """
    return dump(data, stream, Dumper=SafeOrderedDumper, **kwargs)
