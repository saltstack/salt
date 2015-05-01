# -*- coding: utf-8 -*-
'''
Initialize the engines system. This plugin system allows for
complex services to be encapsulated within the salt plugin environment
'''
# Import python libs
from __future__ import absolute_import
import multiprocessing
import logging

# Import salt libs
import salt
import salt.loader

log = logging.getLogger(__name__)


def start_engines(opts, proc_mgr):
    '''
    Fire up the configured engines!
    '''
    if opts['__role'] == 'master':
        runners = salt.loader.runner(opts)
    else:
        runners = []
    utils = salt.loader.utils(opts)
    funcs = salt.loader.minion_mods(opts, utils=utils)
    engines = salt.loader.engines(opts, funcs, runners)

    engines_opt = opts.get('engines', [])
    if isinstance(engines_opt, dict):
        engines_opt = [{k: v} for k, v in engines_opt.items()]

    for engine in engines_opt:
        if isinstance(engine, dict):
            engine, engine_opts = engine.items()[0]
        else:
            engine_opts = None
        fun = '{0}.start'.format(engine)
        if fun in engines:
            proc_mgr.add_process(
                    Engine,
                    args=(
                        opts,
                        fun,
                        engine_opts,
                        funcs,
                        runners
                        )
                    )


class Engine(multiprocessing.Process):
    '''
    Execute the given engine in a new process
    '''
    def __init__(self, opts, fun, config, funcs, runners):
        '''
        Set up the process executor
        '''
        super(Engine, self).__init__()
        self.opts = opts
        self.config = config
        self.fun = fun
        self.funcs = funcs
        self.runners = runners

    def run(self):
        '''
        Run the master service!
        '''
        self.engine = salt.loader.engines(self.opts,
                                          self.funcs,
                                          self.runners)
        kwargs = self.config or {}
        try:
            self.engine[self.fun](**kwargs)
        except Exception as exc:
            log.critical('Engine {0} could not be started! Error: {1}'.format(self.engine, exc))
