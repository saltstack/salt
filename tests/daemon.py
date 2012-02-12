'''
Classes used to set up the main components
'''
# Import python libs
import multiprocessing
import os

# Set up paths
TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
SALT_LIBS = os.path.join(os.path.dirname(TEST_DIR), 'salt')

sys.path.insert(0, TEST_DIR)
sys.path.insert(0, SALT_LIBS)

# Import salt libs
from saltunittest import TestLoader, TextTestRunner, TestCase, TestSuite
import salt
import salt.config
import salt.master
import salt.minion


class DaemonCase(TestCase):
    '''
    Set up the master and minion daemons, and run related cases
    '''
    def setUp(self):
        '''
        Start a master and minion
        '''
        master_opts = salt.config.master_config('files/conf/master')
        minion_opts = salt.config.minion_config('files/conf/minion')
        salt.verify_env([os.path.join(self.opts['pki_dir'], 'minions'),
                    os.path.join(self.opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.opts['pki_dir'], 'minions_rejected'),
                    os.path.join(self.opts['cachedir'], 'jobs'),
                    os.path.dirname(self.opts['log_file']),
                    self.opts['extension_modules'],
                    self.opts['sock_dir'],
                    ])
        # Start the master
        master = salt.master.Master(master_opts)
        multiprocessing.Process(target=master.start).start()
        # Start the minion
        minion = salt.minion.Minion(minion_opts)
        multiprocessing.Process(target=minion.tune_in).start()
        
    def tearDown(self):
        '''
        Kill the minion and master processes
        '''
        pass


class ModuleCase(TestCase):
    '''
    Execute a module function
    '''
    def setUp(self):
        '''
        Generate the tools to test a module
        '''
        self.client = salt.client.LocalClient(master_opts, 'files/conf/master')

    def run_function(self, function):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd(function)
        return orig['minion']


