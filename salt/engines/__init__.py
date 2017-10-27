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
import salt.utils
from salt.utils.process import SignalHandlingMultiprocessingProcess

log = logging.getLogger(__name__)


def start_engines(opts, proc_mgr, proxy=None):
    '''
    Fire up the configured engines!
    '''
    utils = salt.loader.utils(opts)
    if opts['__role'] == 'master':
        runners = salt.loader.runner(opts, utils=utils)
    else:
        runners = []
    funcs = salt.loader.minion_mods(opts, utils=utils)
    engines = salt.loader.engines(opts, funcs, runners, proxy=proxy)

    engines_opt = opts.get('engines', [])
    if isinstance(engines_opt, dict):
        engines_opt = [{k: v} for k, v in engines_opt.items()]

    # Function references are not picklable. Windows needs to pickle when
    # spawning processes. On Windows, these will need to be recalculated
    # in the spawned child process.
    if salt.utils.is_windows():
        runners = None
        utils = None
        funcs = None

    for engine in engines_opt:
        if isinstance(engine, dict):
            engine, engine_opts = next(iter(engine.items()))
        else:
            engine_opts = None
        fun = '{0}.start'.format(engine)
        if fun in engines:
            start_func = engines[fun]
            name = '{0}.Engine({1})'.format(__name__, start_func.__module__)
            log.info('Starting Engine {0}'.format(name))
            proc_mgr.add_process(
                    Engine,
                    args=(
                        opts,
                        fun,
                        engine_opts,
                        funcs,
                        runners,
                        proxy
                        ),
                    name=name
                    )


class Engine(SignalHandlingMultiprocessingProcess):
    '''
    Execute the given engine in a new process
    '''
    def __init__(self, opts, fun, config, funcs, runners, proxy, log_queue=None):
        '''
        Set up the process executor
        '''
        super(Engine, self).__init__(log_queue=log_queue)
        self.opts = opts
        self.config = config
        self.fun = fun
        self.funcs = funcs
        self.runners = runners
        self.proxy = proxy

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(
            state['opts'],
            state['fun'],
            state['config'],
            state['funcs'],
            state['runners'],
            state['proxy'],
            log_queue=state['log_queue']
        )

    def __getstate__(self):
        return {'opts': self.opts,
                'fun': self.fun,
                'config': self.config,
                'funcs': self.funcs,
                'runners': self.runners,
                'proxy': self.proxy,
                'log_queue': self.log_queue}

    def run(self):
        '''
        Run the master service!
        '''
        if salt.utils.is_windows():
            # Calculate function references since they can't be pickled.
            self.utils = salt.loader.utils(self.opts, proxy=self.proxy)
            if self.opts['__role'] == 'master':
                self.runners = salt.loader.runner(self.opts, utils=self.utils)
            else:
                self.runners = []
            self.funcs = salt.loader.minion_mods(self.opts, utils=self.utils, proxy=self.proxy)

        self.engine = salt.loader.engines(self.opts,
                                          self.funcs,
                                          self.runners,
                                          proxy=self.proxy)
        kwargs = self.config or {}
        try:
            self.engine[self.fun](**kwargs)
        except Exception as exc:
            log.critical('Engine {0} could not be started! Error: {1}'.format(self.engine, exc))
