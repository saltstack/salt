#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Salt returner that report error back to sentry

Pillar need something like::

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
    if not has_raven:
        return False
    return 'sentry'


def returner(ret):
    '''
    If an error occurs, log it to sentry
    '''
    def connect_sentry(result):
        pillar_data = __salt__['pillar.raw']()
        sentry_data = {
            'result': result,
            'returned': ret,
            'pillar': pillar_data,
            'grains': __salt__['grains.items']()
        }
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
                client.captureMessage(ret['comment'], extra=sentry_data)
            except Exception as err:
                logger.error("Can't send message to sentry: %s", err,
                             exc_info=True)

    requisite_error = 'One or more requisite failed'
    try:
        if 'success' not in ret:
            logger.debug('no success data, report')
            connect_sentry(ret['return'])
        else:
            if not ret['success']:
                logger.debug('not a success, report')
                connect_sentry(ret['return'])
            else:
                for state in ret['return']:
                    if not ret['return'][state]['result'] and \
                       ret['return'][state]['comment'] != requisite_error:
                        connect_sentry(state)
    except Exception as err:
        logger.error("Can't run connect_sentry: %s", err, exc_info=True)
