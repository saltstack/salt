# -*- coding: utf-8 -*-
'''
Interface with a Junos device via proxy-minion.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import

# Import 3rd-party libs
import jnpr.junos
import jnpr.junos.utils
import jnpr.junos.cfg
HAS_JUNOS = True

__proxyenabled__ = ['junos']


class Proxyconn(object):
    '''
    This class provides the persistent connection to the device that is being
    controlled.
    '''

    def __init__(self, details):
        '''
        Open the connection to the Junos device, login, and bind to the
        Resource class
        '''
        self.conn = jnpr.junos.Device(user=details['username'],
                                      host=details['host'],
                                      password=details['passwd'])
        self.conn.open()
        self.conn.bind(cu=jnpr.junos.cfg.Resource)

    def proxytype(self):
        '''
        Returns the name of this proxy
        '''
        return 'junos'

    def id(self, opts):
        '''
        Returns a unique ID for this proxy minion
        '''
        return self.conn.facts['hostname']

    def ping(self):
        '''
        Ping?  Pong!
        '''
        return self.conn.connected

    def shutdown(self, opts):
        '''
        This is called when the proxy-minion is exiting to make sure the
        connection to the device is closed cleanly.
        '''

        print('Proxy module {0} shutting down!!'.format(opts['id']))
        try:
            self.conn.close()
        except Exception:
            pass
