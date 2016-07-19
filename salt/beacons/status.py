# -*- coding: utf-8 -*-
'''
The status beacon is intended to send a basic health check event up to the
master, this allows for event driven routines based on presence to be set up.

The intention of this beacon is to add the config options to add monitoring
stats to the health beacon making it a one stop shop for gathering systems
health and status data

.. versionadded:: Carbon
'''

# Import python libs
from __future__ import absolute_import
import datetime


def validate(config):
    '''
    Validate the the config is a dict
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for status beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Just say that we are ok!
    '''
    ctime = datetime.datetime.utcnow().isoformat()
    data = {'loadavg': __salt__.status.loadavg(),
            'cpustats': __salt__.status.cpustats(),
            'meminfo': __salt__.status.meminfo(),
            'swapinfo': __salt__.ps.swap_memory(),
            'vmstats': __salt__.ps.virtual_memory(),
            'time': __salt__.status.time(),
            }
    return [{'tag': ctime, 'data': data}]
