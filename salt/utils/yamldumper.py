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

from salt.utils.odict import OrderedDict

# pylint: disable=import-error
try:
    from ioflo.aid.odicting import odict
    HAS_IOFLO = True
except ImportError:
    odict = None
    HAS_IOFLO = False
# pylint: enable=import-error


class OrderedDumper(Dumper):
    '''
    A YAML dumper that represents python OrderedDict as simple YAML map.
    '''


class SafeOrderedDumper(SafeDumper):
    '''
    A YAML safe dumper that represents python OrderedDict as simple YAML map.
    '''


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(list(data.items()))


OrderedDumper.add_representer(OrderedDict, represent_ordereddict)
SafeOrderedDumper.add_representer(OrderedDict, represent_ordereddict)

if HAS_IOFLO:
    OrderedDumper.add_representer(odict, represent_ordereddict)
    SafeOrderedDumper.add_representer(odict, represent_ordereddict)
