# -*- coding: utf-8 -*-
'''
This is the default glob matcher function.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated


def glob_match(self, tgt):
    '''
    Returns true if the passed glob matches the id
    '''
    if not isinstance(tgt, six.string_types):
        return False

    return fnmatch.fnmatch(self.opts['id'], tgt)
