# -*- coding: utf-8 -*-
'''
Manage the Thorium complex event reaction system
'''
from __future__ import absolute_import

# Import salt libs
import salt.thorium


def start():
    '''
    Execute the Thorium runtime
    '''
    state = salt.thorium.ThorState(__opts__)
    state.start_runtime()
