# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
from __future__ import print_function

# Import 3rd-party libs
import jnpr.junos
import jnpr.junos.utils
import jnpr.junos.cfg
HAS_JUNOS = True

__proxyenabled__ = ['junos']

class Proxyconn(object):

    def __init__(self, details):
        self.conn = jnpr.junos.Device(user=details['username'], host=details['host'], password=details['passwd'])
        self.conn.open()
        self.conn.bind(cu=jnpr.junos.cfg.Resource)

    def proxytype(self):
        return 'junos'

    def id(self, opts):
        return self.conn.facts['hostname']

    def ping(self):
        return self.conn.connected

    def shutdown(self, opts):

        print('Proxy module {0} shutting down!!'.format(opts['id']))
        try:
            self.conn.close()
        except Exception:
            pass
