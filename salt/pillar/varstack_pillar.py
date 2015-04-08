# -*- coding: utf-8 -*-
'''
Use varstack data as a Pillar source
'''
from __future__ import absolute_import

# Import python libs
import logging

HAS_VARSTACK = False
try:
    import varstack
    HAS_VARSTACK = True
except ImportError:
    pass

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'varstack'


def __virtual__():
    if not HAS_VARSTACK:
        return False
    return __virtualname__


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Parse varstack data and return the result
    '''
    vs = varstack.Varstack(config_filename=conf)
    return vs.evaluate(__grains__)
