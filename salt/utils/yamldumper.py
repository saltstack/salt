# -*- coding: utf-8 -*-
'''
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

'''
# pylint: disable=W0232
#         class has no __init__ method

from __future__ import absolute_import
try:
    from yaml import CDumper as Dumper
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    from yaml import Dumper
    from yaml import SafeDumper

import yaml
import collections

from salt.utils.odict import OrderedDict

try:
    from ioflo.aid.odicting import odict  # pylint: disable=E0611
    HAS_IOFLO = True
except ImportError:
    odict = None
    HAS_IOFLO = False


class IndentMixin(Dumper):
    '''
    Mixin that improves YAML dumped list readability
    by indenting them by two spaces,
    instead of being flush with the key they are under.
    '''

    def increase_indent(self, flow=False, indentless=False):
        return super(IndentMixin, self).increase_indent(flow, False)


class OrderedDumper(Dumper):
    '''
    A YAML dumper that represents python OrderedDict as simple YAML map.
    '''


class SafeOrderedDumper(SafeDumper):
    '''
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    '''


class IndentedSafeOrderedDumper(IndentMixin, SafeOrderedDumper):
    '''
    A YAML safe dumper that represents python OrderedDict as simple YAML map,
    and also indents lists by two spaces.
    '''
    pass


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(list(data.items()))


OrderedDumper.add_representer(OrderedDict, represent_ordereddict)
SafeOrderedDumper.add_representer(OrderedDict, represent_ordereddict)

OrderedDumper.add_representer(
    collections.defaultdict,
    yaml.representer.SafeRepresenter.represent_dict
)
SafeOrderedDumper.add_representer(
    collections.defaultdict,
    yaml.representer.SafeRepresenter.represent_dict
)

if HAS_IOFLO:
    OrderedDumper.add_representer(odict, represent_ordereddict)
    SafeOrderedDumper.add_representer(odict, represent_ordereddict)


def get_dumper(dumper_name):
    return {
        'OrderedDumper': OrderedDumper,
        'SafeOrderedDumper': SafeOrderedDumper,
        'IndentedSafeOrderedDumper': IndentedSafeOrderedDumper,
    }.get(dumper_name)


def safe_dump(data, stream=None, **kwargs):
    '''
    Use a custom dumper to ensure that defaultdict and OrderedDict are
    represented properly
    '''
    return yaml.dump(data, stream, Dumper=SafeOrderedDumper, **kwargs)
