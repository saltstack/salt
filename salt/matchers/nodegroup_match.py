# -*- coding: utf-8 -*-
'''
This is the default nodegroup matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.minions   # pylint: disable=3rd-party-module-not-gated


def match(self, tgt, nodegroups):
    '''
    This is a compatibility matcher and is NOT called when using
    nodegroups for remote execution, but is called when the nodegroups
    matcher is used in states
    '''
    if tgt in nodegroups:
        return self.compound_match(
            salt.utils.minions.nodegroup_comp(tgt, nodegroups)
        )
    return False
