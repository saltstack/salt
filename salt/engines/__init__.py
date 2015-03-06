# -*- coding: utf-8 -*-
'''
Initialize the engines system. This plugin system allows for
complex services to be encapsulated within the salt plugin environment
'''
# Import python libs
import multiprocessing

# Import salt libs
import salt
import salt.loader


def start_engines(opts, proc_mgr):
    '''
    Fire up the configured engines!
    '''
    if opts['__role'] == 'master':
        funcs = salt.loader.runner(opts)
    else:
        funcs = salt.loader.minion_mods(opts)
    engines = salt.loader.engines(opts, funcs)
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
                        funcs
                        )
                    )


class Engine(multiprocessing.Process):
    '''
    Execute the given engine in a new process
    '''
    def __init__(self, opts, fun, config, funcs):
        '''
        Set up the process executor
        '''
        super(Engine, self).__init__()
        self.opts = opts
        self.config = config
        self.fun = fun
        self.funcs = funcs

    def run(self):
        '''
        Run the master service!
        '''
        self.engine = salt.loader.engines(self.opts, self.funcs)
        kwargs = self.config or {}
        self.engine[self.fun](**kwargs)
