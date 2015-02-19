'''
Initialize the engines system. This plugin system allows for
complex services to be encapsulated within the salt plugin environment
'''
# Import python libs
import multiprocessing

# Import salt libs
import salt


class StartEngines(object):
    '''
    Fire up the configured engines!
    '''
    def __init__(self, opts, proc_mgr):
        self.opts = opts
        self.proc_mgr = proc_mgr
        self.engines = salt.loader.engines(self.opts)

    def run(self):
        for engine in self.opts.get('engines', []):
            if engine in self.engines:
                self.proc_mgr.add_process(
                        Engine,
                        args=(
                            self.opts,
                            engine,
                            self.opts['engines'][engine]
                            )
                        )


class Engine(multiprocessing.Process):
    '''
    Execute the given engine in a new process
    '''
    def __init__(self, opts, service, config):
        '''
        Set up the process executor
        '''
        super(Engine, self).__init__()
        self.opts = opts
        self.config = config
        self.service = service

    def run(self):
        '''
        Run the master service!
        '''
        self.engine = salt.loader.engines(self.opts)
        self.engine[self.service]()
