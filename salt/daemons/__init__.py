# -*- coding: utf-8 -*-
'''
The daemons package is used to store implimentations of the Salt Master and
Minion enabling different transports

Package for ioflo and raet based daemons
'''

# Import python libs
import sys

# Import ioflo libs
import ioflo.app.run

class IofloMaster(object):
    '''
    IofloMaster Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        self.opts = opts

    def start(self):
        '''
        Start up ioflo
        '''
        behaviors = []
        behavior.append('salt.transport.road.raet', 'salt.daemons.ioflo', )

        ioflo.app.run.run(
                name='master',
                filename=self.opts['master_floscript'],
                period=float(self.opts['ioflo_period']),
                verbose=int(self.opts['ioflo_verbose']),
                realtime=self.opts['ioflo_realtime'],
                behaviors=behaviors,)


class IofloMinion(object):
    '''
    IofloMinion Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        self.opts = opts

    def start(self):
        '''
        Start up ioflo
        '''
        behaviors = []
        behavior.append('salt.transport.road.raet', 'salt.daemons.ioflo', )

        ioflo.app.run.run(
                name='minion',
                filename=self.opts['minion_floscript'],
                period=float(self.opts['ioflo_period']),
                verbose=int(self.opts['ioflo_verbose']),
                realtime=self.opts['ioflo_realtime'],
                behaviors=behaviors,)
