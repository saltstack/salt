# -*- coding: utf-8 -*-
'''
Testing guard
'''
from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)


def check_chunks(chunks):
    return []


def check_state(chunk):
    errors = []
    if chunk['state'].startswith('boto_'):
        # TODO: Make this grain configurable
        if not chunk['name'].startswith(__grains__['service_name']):
            msg = (
                'Found state \'{0}\' trying to manage {1} \'{2}\', '
                'which is not owned by the service \'{3}\'.'
            )
            errors.append(msg.format(
                chunk['__id__'],
                chunk['state'],
                chunk['name'],
                __grains__['service_name'],
            ))
    return errors
