
# -*- coding: utf-8 -*-
'''
This is the default list matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

from salt.ext import six  # pylint: disable=3rd-party-module-not-gated


def list_match(self, tgt):
    '''
    Determines if this host is on the list
    '''
    if isinstance(tgt, six.string_types):
        tgt = tgt.split(',')
    return bool(self.opts['id'] in tgt)
