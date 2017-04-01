# -*- coding: utf-8 -*-
'''
NAPALM YANG state
=================

Manage the configuration of network devices according to
the YANG models (OpenConfig/IETF).

.. versionadded:: Nitrogen

Dependencies
------------

- napalm-yang

To be able to load configuration on network devices,
it requires NAPALM_ library to be installed:  ``pip install napalm``.
Please check Installation_ for complete details.

.. _NAPALM: https://napalm.readthedocs.io
.. _Installation: https://napalm.readthedocs.io/en/latest/installation.html
'''
from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

# Import third party libs
try:
    # pylint: disable=W0611
    import aclgen
    HAS_NAPALM_YANG = True
    # pylint: enable=W0611
except ImportError:
    HAS_NAPALM_YANG = False

import salt.utils.napalm

# ------------------------------------------------------------------------------
# state properties
# ------------------------------------------------------------------------------

__virtualname__ = 'napalm_yang'

# ------------------------------------------------------------------------------
# global variables
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    This module in particular requires also napalm-yang.
    '''
    if not HAS_NAPALM_YANG:
        return (False, 'Unable to load napalm_yang execution module: please install napalm-yang!')
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ------------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def managed(data,
            *models,
            **kwargs):
            # profiles=None,
            # test=False,
            # debug=False,
            # commit=True,
            # replace=False):
    # TODO
    # save data to temp file
    # run compliance report
    # run napalm_yang.load_config
    # delete temp file
    # return
    return
