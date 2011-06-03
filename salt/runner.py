'''
Execute salt convenience routines
'''

# Import python modules
import sys

# Import salt modules
import salt.loader

class Runner(object):
    '''
    Execute the salt runner interface
    '''
    def __init__(self, opts):
        self.opts = opts
        self.functions = salt.loader.runner(opts)

    def _verify_fun(self):
        '''
        Verify an environmental issues
        '''
        if not self.opts['fun']:
            err = 'Must pass a runner function'
            sys.stderr.write('%s\n' % err)
            sys.exit(1)
        if not self.functions.has_key(self.opts['fun']):
            err = 'Passed function is unavailable'
            sys.stderr.write('%s\n' % err)
            sys.exit(1)

    def run(self):
        '''
        Execuete the runner sequence
        '''
        self._verify_fun()
        self.functions[self.opts['fun']](*self.opts['arg'])
