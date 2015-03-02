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
        if engine in engines:
            proc_mgr.add_process(
                    Engine,
                    args=(
                        opts,
                        engine,
                        opts['engines'][engine]
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
