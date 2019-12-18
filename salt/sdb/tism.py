# -*- coding: utf-8 -*-
'''
tISM - the Immutable Secrets Manager SDB Module

:maintainer:    tISM
:maturity:      New
:platform:      all

.. versionadded:: 2017.7.0

This module will decrypt PGP encrypted secrets against a tISM server.

.. code::

  sdb://<profile>/<encrypted secret>

  sdb://tism/hQEMAzJ+GfdAB3KqAQf9E3cyvrPEWR1sf1tMvH0nrJ0bZa9kDFLPxvtwAOqlRiNp0F7IpiiVRF+h+sW5Mb4ffB1TElMzQ+/G5ptd6CjmgBfBsuGeajWmvLEi4lC6/9v1rYGjjLeOCCcN4Dl5AHlxUUaSrxB8akTDvSAnPvGhtRTZqDlltl5UEHsyYXM8RaeCrBw5Or1yvC9Ctx2saVp3xmALQvyhzkUv5pTb1mH0I9Z7E0ian07ZUOD+pVacDAf1oQcPpqkeNVTQQ15EP0fDuvnW+a0vxeLhkbFLfnwqhqEsvFxVFLHVLcs2ffE5cceeOMtVo7DS9fCtkdZr5hR7a+86n4hdKfwDMFXiBwSIPMkmY980N/H30L/r50+CBkuI/u4M2pXDcMYsvvt4ajCbJn91qaQ7BDI=

A profile must be setup in the minion configuration or pillar. If you want to
use sdb in a runner or pillar you must also place a profile in the master
configuration.

.. code-block:: yaml

    tism:
      driver: tism
      url: https://my.tismd:8080/decrypt
      token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6MSwiZXhwIjoxNTg1MTExNDYwLCJqdGkiOiI3NnA5cWNiMWdtdmw4Iiwia2V5cyI6WyJBTEwiXX0.RtAhG6Uorf5xnSf4Ya_GwJnoHkCsql4r1_hiOeDSLzo
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.utils.json
import salt.utils.http as http
from salt.ext import six
from salt.exceptions import SaltConfigurationError

log = logging.getLogger(__name__)

__virtualname__ = "tism"


def __virtual__():
    '''
    This module has no other system dependencies
    '''
    return __virtualname__


def get(key, service=None, profile=None):  # pylint: disable=W0613
    '''
    Get a decrypted secret from the tISMd API
    '''

    if not profile.get('url') or not profile.get('token'):
        raise SaltConfigurationError("url and/or token missing from the tism sdb profile")

    request = {"token": profile['token'], "encsecret": key}

    result = http.query(
        profile['url'],
        method='POST',
        data=salt.utils.json.dumps(request),
    )

    decrypted = result.get('body')

    if not decrypted:
        log.warning(
            'tism.get sdb decryption request failed with error %s',
            result.get('error', 'unknown')
        )
        return 'ERROR' + six.text_type(result.get('status', 'unknown'))

    return decrypted
