#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Salt returner that report error back to sentry

Pillar need something like:

raven:
  servers:
    - http://192.168.1.1
    - https://sentry.example.com
  public_key: deadbeefdeadbeefdeadbeefdeadbeef
  secret_key: beefdeadbeefdeadbeefdeadbeefdead
  project: 1

and http://pypi.python.org/pypi/raven installed
'''

import logging

try:
    from raven import Client
    has_raven = True
except ImportError:
    has_raven = False

logger = logging.getLogger(__name__)


def __virtual__():
    pillar_data = __salt__['pillar.data']()
    if not has_raven:
        logger.warning("Can't find raven client library")
        return False
    if 'raven' not in pillar_data:
        logger.warning("Missing pillar data 'raven'")
        return False
    for key in ('project', 'public_key', 'secret_key', 'servers'):
        if key not in pillar_data['raven']:
            logger.warning("Missing config '%s' in pillar 'raven'", key)
            return False
    return 'sentry'


def returner(ret):
    '''
    If an error occurs, log it to sentry
    '''
    def connect_sentry(message, result):
        pillar_data = __salt__['pillar.data']()
        sentry_data = {
            'result': result,
            'returned': ret,
            'pillar': pillar_data,
            'grains': __salt__['grains.items']()
        }
        servers = []
        for server in pillar_data['raven']['servers']:
            servers.append(server + '/api/store/')
        try:
            client = Client(
                servers=servers,
                public_key=pillar_data['raven']['public_key'],
                secret_key=pillar_data['raven']['secret_key'],
                project=pillar_data['raven']['project'],
            )
            client.captureMessage(ret['comment'], extra=sentry_data)
        except Exception, err:
            logger.error("Can't send message to sentry: %s", err, exc_info=True)

    requisite_error = 'One or more requisite failed'
    try:
        if 'success' not in ret:
            logger.debug("no success data, report")
            connect_sentry(ret['return'], ret)
        else:
            if not ret['success']:
                logger.debug("not a success, report")
                connect_sentry(ret['return'], ret)
            else:
                for state in ret['return']:
                    if not ret['return'][state]['result'] and \
                       ret['return'][state]['comment'] != requisite_error:
                        connect_sentry(state, ret['return'][state])
    except Exception, err:
        logger.error("Can't run connect_sentry: %s", err, exc_info=True)
