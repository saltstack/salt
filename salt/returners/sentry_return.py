# -*- coding: utf-8 -*-
'''
Salt returner that report execution results back to sentry. The returner will
inspect the payload to identify errors and flag them as such.

Pillar need something like::

    raven:
      servers:
        - http://192.168.1.1
        - https://sentry.example.com
      public_key: deadbeefdeadbeefdeadbeefdeadbeef
      secret_key: beefdeadbeefdeadbeefdeadbeefdead
      project: 1
      tags:
        - os
        - master
        - saltversion
        - cpuarch

and http://pypi.python.org/pypi/raven installed

The tags list (optional) specifies grains items that will be used as sentry tags, allowing tagging of events
in the sentry ui.
'''

import logging

try:
    from raven import Client
    has_raven = True
except ImportError:
    has_raven = False

logger = logging.getLogger(__name__)


def __virtual__():
    if not has_raven:
        return False
    return 'sentry'


def returner(ret):
    '''
    Log outcome to sentry. The returner tries to identify errors and report them as such. All other
    messages will be reported at info level.
    '''
    def connect_sentry(message, result):
        pillar_data = __salt__['pillar.raw']()
        grains = __salt__['grains.items']()
        sentry_data = {
            'result': result,
            'pillar': pillar_data,
            'grains': grains
        }
        data = {
            'platform': 'python',
            'culprit': ret['fun'],
            'level': 'error'
        }
        tags = {}
        if 'tags' in pillar_data['raven']:
            for tag in pillar_data['raven']['tags']:
                tags[tag] = grains[tag]

        if ret['return']:
            data['level'] = 'info'

        servers = []
        try:
            for server in pillar_data['raven']['servers']:
                servers.append(server + '/api/store/')
            client = Client(
                servers=servers,
                public_key=pillar_data['raven']['public_key'],
                secret_key=pillar_data['raven']['secret_key'],
                project=pillar_data['raven']['project'],
            )
        except KeyError as missing_key:
            logger.error("Sentry returner need config '%s' in pillar",
                         missing_key)
        else:
            try:
                client.capture('raven.events.Message', message=message, data=data, extra=sentry_data, tags=tags)
            except Exception as err:
                logger.error("Can't send message to sentry: %s", err,
                             exc_info=True)

    try:
        connect_sentry(ret['fun'], ret)
    except Exception as err:
        logger.error("Can't run connect_sentry: %s", err, exc_info=True)
