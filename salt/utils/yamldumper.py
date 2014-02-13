# -*- coding: utf-8 -*-
'''
    salt.utils.yamldumper
    ~~~~~~~~~~~~~~~~~~~~~

'''

from __future__ import absolute_import
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import CDumper as Dumper

from salt.utils.odict import OrderedDict


class OrderedDumper(Dumper):
    '''
    A YAML dumper that represents python OrderedDict as simple YAML map.
    '''
    pass


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(data.items())

OrderedDumper.add_representer(OrderedDict, represent_ordereddict)
