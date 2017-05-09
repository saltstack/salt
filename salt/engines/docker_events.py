# -*- coding: utf-8 -*-
'''
Send events from Docker events
:Depends:   Docker API >= 1.22
'''

# Import Python Libs
from __future__ import absolute_import

import json
import logging
import traceback

import salt.utils

# pylint: disable=import-error
try:
    import docker
    import docker.utils
    HAS_DOCKER_PY = True
except ImportError:
    HAS_DOCKER_PY = False

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# Default timeout as of docker-py 1.0.0
CLIENT_TIMEOUT = 60

# Define the module's virtual name
__virtualname__ = 'docker_events'


def __virtual__():
    '''
    Only load if docker libs are present
    '''
    if not HAS_DOCKER_PY:
        return (False, 'Docker_events engine could not be imported')
    return True


def start(docker_url='unix://var/run/docker.sock',
          timeout=CLIENT_TIMEOUT,
          tag='salt/engines/docker_events'):
    '''
    Scan for Docker events and fire events

    Example Config

    .. code-block:: yaml

        engines:
          docker_events:
            docker_url: unix://var/run/docker.sock

    The config above sets up engines to listen
    for events from the Docker daemon and publish
    them to the Salt event bus.
    '''

    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        '''
        How to fire the event
        '''
        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__['event.send'](tag, msg)

    client = docker.Client(base_url=docker_url,
                           timeout=timeout)
    try:
        events = client.events()
        for event in events:
            data = json.loads(event)
            # https://github.com/docker/cli/blob/master/cli/command/system/events.go#L109
            # https://github.com/docker/engine-api/blob/master/types/events/events.go
            # Each output includes the event type, actor id, name and action.
            # status field can be ommited
            if data['Action']:
                fire('{0}/{1}'.format(tag, data['Action']), data)
            else:
                fire('{0}/{1}'.format(tag, data['status']), data)
    except Exception:
        traceback.print_exc()
