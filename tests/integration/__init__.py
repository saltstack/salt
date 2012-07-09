'''
Set up the Salt integration test suite
'''

# Import Python libs
import multiprocessing
import os
import sys
import shutil
import signal
import subprocess
try:
    import pwd
except ImportError:
    pass

# Import Salt libs
import salt
import salt.config
import salt.master
import salt.minion
import salt.runner
from salt.utils.verify import verify_env
from saltunittest import TestCase

INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')

PYEXEC = 'python{0}.{1}'.format(sys.version_info[0], sys.version_info[1])

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
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )
        self.minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'minion')
        )
        self.sub_minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'sub_minion')
        )
        self.smaster_opts = salt.config.master_config(
            os.path.join(
                INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic_master'
            )
        )
        self.syndic_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic'))
        self.syndic_opts['_master_conf_file'] = os.path.join(
            INTEGRATION_TEST_DIR,
            'files/conf/master'
        )
        # Set up config options that require internal data
        self.master_opts['pillar_roots'] = {
            'base': [os.path.join(FILES, 'pillar', 'base')]
        }
        self.master_opts['file_roots'] = {
            'base': [os.path.join(FILES, 'file', 'base')]
        }
        self.master_opts['ext_pillar'] = [
            {'cmd_yaml': 'cat {0}'.format(
                os.path.join(
                    FILES,
                    'ext.yaml'
                )
            )}
        ]
        # clean up the old files
        self._clean()
        self.master_opts['hosts.file'] = os.path.join(TMP, 'hosts')
        self.minion_opts['hosts.file'] = os.path.join(TMP, 'hosts')
        verify_env([os.path.join(self.master_opts['pki_dir'], 'minions'),
                    os.path.join(self.master_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.master_opts['pki_dir'],
                                 'minions_rejected'),
                    os.path.join(self.master_opts['cachedir'], 'jobs'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.smaster_opts['pki_dir'],
                                 'minions_rejected'),
                    os.path.join(self.smaster_opts['cachedir'], 'jobs'),
                    os.path.dirname(self.master_opts['log_file']),
                    self.minion_opts['extension_modules'],
                    self.sub_minion_opts['extension_modules'],
                    self.sub_minion_opts['pki_dir'],
                    self.master_opts['sock_dir'],
                    self.smaster_opts['sock_dir'],
                    self.sub_minion_opts['sock_dir'],
                    self.minion_opts['sock_dir'],
                    ],
                   pwd.getpwuid(os.getuid())[0])

        master = salt.master.Master(self.master_opts)
        self.master_process = multiprocessing.Process(target=master.start)
        self.master_process.start()

        minion = salt.minion.Minion(self.minion_opts)
        self.minion_process = multiprocessing.Process(target=minion.tune_in)
        self.minion_process.start()

        sub_minion = salt.minion.Minion(self.sub_minion_opts)
        self.sub_minion_process = multiprocessing.Process(
            target=sub_minion.tune_in
        )
        self.sub_minion_process.start()

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
        self.sub_minion_process.terminate()
        self.minion_process.terminate()
        self.master_process.terminate()
        self.syndic_process.terminate()
        self.smaster_process.terminate()
        self._clean()

    def _clean(self):
        '''
        Clean out the tmp files
        '''
        if os.path.isdir(self.sub_minion_opts['root_dir']):
            shutil.rmtree(self.sub_minion_opts['root_dir'])
        if os.path.isdir(self.master_opts['root_dir']):
            shutil.rmtree(self.master_opts['root_dir'])
        if os.path.isdir(self.smaster_opts['root_dir']):
            shutil.rmtree(self.smaster_opts['root_dir'])
        for fn_ in os.listdir(TMP):
            if fn_ == '_README':
                continue
            path = os.path.join(TMP, fn_)
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
            elif os.path.islink(path):
                os.remove(path)


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
                'files', 'conf', 'master'
            )
        )

    def run_function(self, function, arg=(), **kwargs):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion',
                               function,
                               arg,
                               timeout=100,
                               kwarg=kwargs)
        return orig['minion']

    def state_result(self, ret):
        '''
        Return the result data from a single state return
        '''
        return ret[next(iter(ret))]['result']

    def run_state(self, function, **kwargs):
        '''
        Run the state.single command and return the state return structure
        '''
        return self.run_function('state.single', [function], **kwargs)

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
            os.path.join(
                INTEGRATION_TEST_DIR,
                'files', 'conf', 'minion'
            )
        )

    @property
    def master_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
            os.path.join(
                INTEGRATION_TEST_DIR,
                'files', 'conf', 'master'
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
                'files', 'conf', 'syndic_master'
            )
        )

    def run_function(self, function, arg=()):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg)
        return orig['minion']


class ShellCase(TestCase):
    '''
    Execute a test for a shell command
    '''
    def run_script(self, script, arg_str):
        '''
        Execute a script with the given argument string
        '''
        path = os.path.join(SCRIPT_DIR, script)
        if not os.path.isfile(path):
            return False
        ppath = 'PYTHONPATH={0}:{1}'.format(CODE_DIR, ':'.join(sys.path[1:]))
        cmd = '{0} {1} {2} {3}'.format(ppath, PYEXEC, path, arg_str)
        data = subprocess.Popen(cmd,
                                shell=True,
                                stdout=subprocess.PIPE
                                ).communicate()[0].split('\n')
        return data

    def run_salt(self, arg_str):
        '''
        Execute salt
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt', arg_str)

    def run_run(self, arg_str):
        '''
        Execute salt-run
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-run', arg_str)

    def run_run_plus(self, fun, options='', *arg):
        '''
        Execute Salt run and the salt run function and return the data from
        each in a dict
        '''
        ret = {}
        ret['out'] = self.run_run(
            '{0} {1} {2}'.format(options, fun, ' '.join(arg))
        )
        opts = salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master'))
        opts.update({'doc': False,
                     'fun': fun,
                     'arg': arg})
        runner = salt.runner.Runner(opts)
        ret['fun'] = runner.run()
        return ret

    def run_key(self, arg_str):
        '''
        Execute salt-key
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-key', arg_str)
