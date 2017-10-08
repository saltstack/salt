# -*- coding: utf-8 -*-
'''
HTTP Logstash engine
==========================

An engine that reads messages from the salt event bus and pushes
them onto a logstash endpoint via HTTP requests.

:configuration: Example configuration

    .. code-block:: yaml

        engines:
          - http_logstash:
              url: http://blabla.com/salt-stuff
              tags:
                  - salt/job/*/new
                  - salt/job/*/ret/*
              funs:
                  - probes.results
                  - bgp.config
'''

from __future__ import absolute_import

# Import python lib
import json
import fnmatch

# Import salt libs
import salt.utils.http
import salt.utils.event

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

_HEADERS = {'Content-Type': 'application/json'}

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------


def _logstash(url, data):

    '''
    Issues HTTP queries to the logstash server.
    '''

    result = salt.utils.http.query(
        url,
        'POST',
        header_dict=_HEADERS,
        data=json.dumps(data),
        decode=True,
        status=True,
        opts=__opts__
    )
    return result

# ----------------------------------------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------------------------------------


def start(url, funs=None, tags=None):

    '''
    Listen to salt events and forward them to logstash via HTTP.
    '''

    if __opts__.get('id').endswith('_master'):
        instance = 'master'
    else:
        instance = 'minion'
    event_bus = salt.utils.event.get_event(instance,
                                           sock_dir=__opts__['sock_dir'],
                                           transport=__opts__['transport'],
                                           opts=__opts__)

    while True:
        event = event_bus.get_event(tag='salt/job', full=True)
        if event:
            publish = True
            if isinstance(tags, list) and len(tags) > 0:
                found_match = False
                for tag in tags:
                    if fnmatch.fnmatch(event['tag'], tag):
                        found_match = True
                publish = found_match
            if funs:
                if not event['data']['fun'] in funs:
                    publish = False
            if publish:
                _logstash(url, event['data'])
