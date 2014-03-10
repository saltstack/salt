# -*- coding: utf-8 -*-
'''
Package for ioflo and raet based daemons and associated ioflo behaviors

To use set
opts['transport'] ='raet'
master minion config
transport: raet

See salt.config.py for relevant defaults

opts['raet_port']
opts['master_floscript']
opts['minion_floscript']
opts['ioflo_period']
opts['ioflo_realtime']
opts['ioflo_verbose']
'''

# Import modules
from . import master
from . import minion

__all__ = ['master', 'minion']

# Import ioflo libs
import ioflo.app.run


def explode_opts(opts):
    '''
    Explode the opts into a preloads list
    '''
    preloads = []
    preloads = [('.salt.opts', dict(value=opts))]
    for key, val in opts.items():
        ukey = key.replace('.', '_')
        preloads.append(('.salt.etc.{0}'.format(ukey), dict(value=val)))
    return preloads


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

        port = self.opts['raet_port']
        '''
        behaviors = ['salt.transport.road.raet', 'salt.daemons.flo']
        preloads = explode_opts(self.opts)
        ioflo.app.run.start(
                name='master',
                period=float(self.opts['ioflo_period']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['master_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts['ioflo_verbose']),
                )


class IofloMinion(object):
    '''
    IofloMinion Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        self.opts = opts

    def tune_in(self):
        '''
        Start up ioflo

        port = self.opts['raet_port']
        '''
        behaviors = ['salt.transport.road.raet', 'salt.daemons.flo']
        preloads = explode_opts(self.opts)

        ioflo.app.run.start(
                name=self.opts['id'],
                period=float(self.opts['ioflo_period']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['minion_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts['ioflo_verbose']),
                )

    start = tune_in  # alias
