# -*- coding: utf-8 -*-
'''
Display return data in YAML format
==================================

This outputter defaults to printing in YAML block mode for better readability.

Example output::

    saltmine:
      foo:
        bar: baz
        dictionary:
          abc: 123
          def: 456
        list:
          - Hello
          - World
'''
from __future__ import absolute_import

# Import third party libs
import yaml

# Import salt libs
from salt.utils.yamldumper import OrderedDumper

# Define the module's virtual name
__virtualname__ = 'yaml'


def __virtual__():
    return __virtualname__


def output(data):
    '''
    Print out YAML using the block mode
    '''

    params = dict(Dumper=OrderedDumper)
    if 'output_indent' not in __opts__:
        # default indentation
        params.update(default_flow_style=False)
    elif __opts__['output_indent'] >= 0:
        # custom indent
        params.update(default_flow_style=False,
                      indent=__opts__['output_indent'])
    else:  # no indentation
        params.update(default_flow_style=True,
                      indent=0)
    return yaml.dump(data, **params)
