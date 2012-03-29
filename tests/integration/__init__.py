'''
Set up the Salt integration test suite
'''

# Import Python libs
import multiprocessing
import os
import shutil
import signal

# Import Salt libs
import salt
import salt.config
import salt.master
import salt.minion
from salt.utils.verify import verify_env
from saltunittest import TestCase

INTEGRATION_TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))

TMP = os.path.join(INTEGRATION_TEST_DIR, 'tmp')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')

class TestDaemon(object):
    '''
    Set up the master and minion daemons, and run related cases
    '''

    def __enter__(self):
        '''
        Start a master and minion
        '''
        self.master_opts = salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files/conf/master'))
        self.minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files/conf/minion'))
        self.smaster_opts = salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files/conf/syndic_master'))
        self.syndic_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files/conf/syndic'))
        self.syndic_opts['_master_conf_file'] = os.path.join(INTEGRATION_TEST_DIR, 'files/conf/master')
        # clean up the old files
        if os.path.isdir(self.master_opts['root_dir']):
            shutil.rmtree(self.master_opts['root_dir'])
        self.master_opts['hosts.file'] = os.path.join(TMP, 'hosts')
        self.minion_opts['hosts.file'] = os.path.join(TMP, 'hosts')
        verify_env([
                    os.path.join(self.master_opts['pki_dir'], 'minions'),
                    os.path.join(self.master_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.master_opts['pki_dir'], 'minions_rejected'),
                    os.path.join(self.master_opts['cachedir'], 'jobs'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions_rejected'),
                    os.path.join(self.smaster_opts['cachedir'], 'jobs'),
                    os.path.dirname(self.master_opts['log_file']),
                    self.minion_opts['extension_modules'],
                    self.master_opts['sock_dir'],
                    self.smaster_opts['sock_dir'],
                    ])

        master = salt.master.Master(self.master_opts)
        self.master_process = multiprocessing.Process(target=master.start)
        self.master_process.start()

        minion = salt.minion.Minion(self.minion_opts)
        self.minion_process = multiprocessing.Process(target=minion.tune_in)
        self.minion_process.start()

        smaster = salt.master.Master(self.smaster_opts)
        self.smaster_process = multiprocessing.Process(target=smaster.start)
        self.smaster_process.start()

        syndic = salt.minion.Syndic(self.syndic_opts)
        self.syndic_process = multiprocessing.Process(target=syndic.tune_in)
        self.syndic_process.start()

        return self

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        self.minion_process.terminate()
        self.stop_master_processes()
        self.master_process.terminate()
        self.syndic_process.terminate()
        self.smaster_process.terminate()


    def stop_master_processes(self):
        try:
            with open(self.master_opts['pidfile']) as pidfile:
                for pid in pidfile.readlines():
                    if len(pid.strip()):
                        try:
                            os.kill(int(pid.strip()), signal.SIGTERM)
                        except OSError:
                            pass
        except IOError:
            pass


class ModuleCase(TestCase):
    '''
    Execute a module function
    '''
    def setUp(self):
        '''
        Generate the tools to test a module
        '''
        self.client = salt.client.LocalClient(
                os.path.join(
                    INTEGRATION_TEST_DIR,
                    'files/conf/master'
                    )
                )

    def run_function(self, function, arg=()):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg)
        return orig['minion']

    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
                os.path.join(
                    INTEGRATION_TEST_DIR,
                    'files/conf/minion'
                    )
                )

    def master_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
                os.path.join(
                    INTEGRATION_TEST_DIR,
                    'files/conf/master'
                    )
                )

class SyndicCase(TestCase):
    '''
    Execute a syndic based execution test
    '''
    def setUp(self):
        '''
        Generate the tools to test a module
        '''
        self.client = salt.client.LocalClient(
                os.path.join(
                    INTEGRATION_TEST_DIR,
                    'files/conf/syndic_master'
                    )
                )

    def run_function(self, function, arg=()):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg)
        return orig['minion']
