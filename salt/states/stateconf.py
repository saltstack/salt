# -*- coding: utf-8 -*-
'''
Stateconf System
================

The stateconf system is intended for use only with the stateconf renderer. This
State module presents the set function. This function does not execute any
functionality, but is used to interact with the stateconf renderer.
'''
from __future__ import absolute_import, print_function, unicode_literals


def _no_op(name, **kwargs):
    '''
    No-op state to support state config via the stateconf renderer.
    '''
    return dict(name=name, result=True, changes={}, comment='')

set = context = _no_op  # pylint: disable=C0103
