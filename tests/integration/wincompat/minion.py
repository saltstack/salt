import os
import sys
import threading
import time
import pickle
import subprocess
import copy

import integration

import salt.config
import salt.minion

class MultiprocessingTest(integration.ShellCase):
    '''
    Test multiprocessing windows requirements are satisfied
    '''
    def test_minion_pickle(self):
        '''
        Test minion instance can be pickled
        '''
        minion_opts = salt.config.minion_config(
            os.path.join(integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'minion')
        )
        my_opts=copy.copy(minion_opts)
        my_opts['id']='test_minion_pickle'
        minion = salt.minion.Minion(my_opts)
        process = threading.Thread(target=minion.tune_in_no_block)
        process.start()
        process.join()
        self.run_key('-y -d test_minion_pickle')
        try:
            pickle.dumps(minion)
        except:
            if hasattr(minion, '__getstate__'):
                state = minion.__getstate__()
            else:
                state = minion.__dict__
            failed_attrs=[]
            for k, v in state.items():
                try:
                    pickle.dumps(v)
                except:
                    failed_attrs.append(k)
            self.fail('Minion instance attrs are not picklable: {0}'.format(failed_attrs))

    def test_minion_schedule_pickle(self):
        '''
        Test minion schedule instance can be pickled
        '''
        minion_opts = salt.config.minion_config(
            os.path.join(integration.INTEGRATION_TEST_DIR, 'files', 'conf', 'minion')
        )
        my_opts=copy.copy(minion_opts)
        my_opts['id']='test_minion_schedule_pickle'
        minion = salt.minion.Minion(my_opts)
        process = threading.Thread(target=minion.tune_in_no_block)
        process.start()
        process.join()
        self.run_key('-y -d test_minion_schedule_pickle')
        try:
            pickle.dumps(minion.schedule)
        except:
            if hasattr(minion.schedule, '__getstate__'):
                state = minion.schedule.__getstate__()
            else:
                state = minion.schedule.__dict__
            failed_attrs=[]
            for k, v in state.items():
                try:
                    pickle.dumps(v)
                except:
                    failed_attrs.append(k)
            self.fail('Schedule instance attrs are not picklable: {0}'.format(failed_attrs))

    def test_minion_main_import(self):
        '''
        Test minion salt-minion.py is importable
        '''
        module = 'salt-minion'
        script = '{0}.py'.format(module)
        path = os.path.join(integration.SCRIPT_DIR, script)
        if not os.path.isfile(path):
            self.fail('{0} not found'.format(script))

        ppath = 'PYTHONPATH={0}:{1}:{2}'.format(integration.SCRIPT_DIR, integration.CODE_DIR, ':'.join(sys.path[1:]))
        cmd = '{0} {1} -m {2} --version'.format(ppath, integration.PYEXEC, module)

        popen_kwargs = {
            'shell': True,
            'stdout': subprocess.PIPE
        }
        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True


        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True

        process = subprocess.Popen(cmd, **popen_kwargs)
        data = process.communicate()[0].splitlines()

        expected = self.run_script('salt-minion', '--version')

        self.assertEqual(data[0].split()[1:], expected[0].split()[1:])

