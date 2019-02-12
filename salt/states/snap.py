# -*- coding: utf-8 -*-
'''
Management of snap packages
===============================================
'''
from __future__ import absolute_import, print_function, unicode_literals

def __virtual__():
    if salt.utils.path.which('snap'):
        return __virtualname__

    return (False, 'The snap state module cannot be loaded: the "snap" binary is not in the path.')


def installed(name, channel=None):
    '''
    Ensure that the snap package is installed

    name : str
        The snap package

    channel : str
        Optional. The channel to install the package from.
    '''

    old = __salt__['snap.is_installed']
