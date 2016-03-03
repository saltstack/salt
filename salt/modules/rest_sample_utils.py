# -*- coding: utf-8 -*-
'''
Utility functions for the rest_sample
'''
from __future__ import absolute_import

__proxyenabled__ = ['rest_sample']


def fix_outage():
    '''
    "Fix" the outage

    CLI Example:

    .. code-block:: bash

        salt 'rest-sample-proxy' rest_sample.fix_outage

    '''
    return __proxy__['rest_sample.fix_outage']()
