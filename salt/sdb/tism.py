# -*- coding: utf-8 -*-
'''
tISM - the Immutalbe Secrets Manager SDB Module

:maintainer:    tISM
:maturity:      New
:platform:      all

.. versionadded:: TBD

This module will decrypt PGP encrypted secrets against a tISM server.

.. code::

  sdb://<profile>/<encrypted secret>

  sdb://tism/hQEMAzJ+GfdAB3KqAQf9E3cyvrPEWR1sf1tMvH0nrJ0bZa9kDFLPxvtwAOqlRiNp0F7IpiiVRF+h+sW5Mb4ffB1TElMzQ+/G5ptd6CjmgBfBsuGeajWmvLEi4lC6/9v1rYGjjLeOCCcN4Dl5AHlxUUaSrxB8akTDvSAnPvGhtRTZqDlltl5UEHsyYXM8RaeCrBw5Or1yvC9Ctx2saVp3xmALQvyhzkUv5pTb1mH0I9Z7E0ian07ZUOD+pVacDAf1oQcPpqkeNVTQQ15EP0fDuvnW+a0vxeLhkbFLfnwqhqEsvFxVFLHVLcs2ffE5cceeOMtVo7DS9fCtkdZr5hR7a+86n4hdKfwDMFXiBwSIPMkmY980N/H30L/r50+CBkuI/u4M2pXDcMYsvvt4ajCbJn91qaQ7BDI=

A profile must be setup in the minion configuration or pillar.  If you want to use sdb in a runner or pillar you must also placea  configuration in the master configuration.

.. code-block:: yaml

    tism:
      driver: tism
      url: https://my.tismd:8080/decrypt
      token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6MSwiZXhwIjoxNTg1MTExNDYwLCJqdGkiOiI3NnA5cWNiMWdtdmw4Iiwia2V5cyI6WyJBTEwiXX0.RtAhG6Uorf5xnSf4Ya_GwJnoHkCsql4r1_hiOeDSLzo
'''

# import python libs
import logging
import json

import salt.utils.http as http

log = logging.getLogger(__name__)


def set(key, value, service=None, profile=None):  # pylint: disable=W0613
    '''
    TiSM dont't do set
    '''
    return None


def get(key, service=None, profile=None):  # pylint: disable=W0613
    '''
    Get a value from the tISMd
    '''

    #TODO Validate the the profile has everything that we need.
    request = {"token": profile['token'], "encsecret": key} 

    result = http.query(
        profile['url'],
        method='POST',
        data=json.dumps(request),
        decode=True,
    )
    #TODO crash everything if we get back an error
    return result['body']
