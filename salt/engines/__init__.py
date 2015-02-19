'''
Initialize the master services system. This plugin system allows for
complex services to be encapsulated within the salt plugin environment
'''
# Import python libs
import multiprocessing

# Import salt libs
import salt


class MSrvc(multiprocessing.Process):
    '''
    Execute the given master service in a new process
    '''
    def __init__(self, opts, service):
        '''
        Set up the process executor
        '''
        super(MSrvc, self).__init__()
        self.opts = opts
        self.service = service

    def run(self):
        '''
        Run the master service!
        '''
        self.msrvc = salt.loader.msrvc(self.opts)
        self.msrvc[self.service]()
