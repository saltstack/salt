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
    engines = salt.loader.engines(opts)
    for engine in opts.get('engines', []):
        fun = '{0}.start'.format(engine)
        if fun in engines:
            proc_mgr.add_process(
                    Engine,
                    args=(
                        opts,
                        fun,
                        opts['engines'][engine]
                        )
                    )


class Engine(multiprocessing.Process):
    '''
    Execute the given engine in a new process
    '''
    def __init__(self, opts, fun, config):
        '''
        Set up the process executor
        '''
        super(Engine, self).__init__()
        self.opts = opts
        self.config = config
        self.fun = fun

    def run(self):
        '''
        Run the master service!
        '''
        self.engine = salt.loader.engines(self.opts)
        self.engine[self.fun]()
