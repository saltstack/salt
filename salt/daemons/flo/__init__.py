# -*- coding: utf-8 -*-
'''
ioflo behaviors for master and minion
'''

# Import modules
from . import master
from . import minion

__all__ = ['master', 'minion']

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
        behaviors.append('salt.transport.road.raet', 'salt.daemons.flo', )

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
        behaviors.append('salt.transport.road.raet', 'salt.daemons.flo', )

        ioflo.app.run.run(
                name='minion',
                filename=self.opts['minion_floscript'],
                period=float(self.opts['ioflo_period']),
                verbose=int(self.opts['ioflo_verbose']),
                realtime=self.opts['ioflo_realtime'],
                behaviors=behaviors,)
