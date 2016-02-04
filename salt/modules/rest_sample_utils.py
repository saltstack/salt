# -*- coding: utf-8 -*-
'''
Utility functions for the rest_sample
'''
from __future__ import absolute_import

# Import python libs
import os
import re
import stat
import tempfile

# Import salt libs
import salt.utils
from salt.utils import which as _which
from salt.exceptions import SaltInvocationError


__proxyenabled__ = ['rest_sample']


def fix_outage():
    '''
    "Fix" the outage
    '''
    return __proxy__['rest_sample.fix_outage']()


