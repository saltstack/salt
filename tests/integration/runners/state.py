# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import
import errno
import os
import shutil
import signal
import tempfile
import textwrap
import yaml
import threading
from salt.ext.six.moves import queue

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

import integration

# Import Salt Libs
import salt.utils
import salt.utils.event


class StateRunnerTest(integration.ShellCase):
    '''
    Test the state runner.
    '''
    def add_to_queue(self, q, cmd):
        '''
        helper method to add salt-run
        return data to a queue
        '''
        ret = self.run_run(cmd)
        q.put(ret)
        q.task_done()

    def test_orchestrate_output(self):
        '''
        Ensure the orchestrate runner outputs useful state data.

        In Issue #31330, the output only contains ['outputter:', '    highstate'],
        and not the full stateful return. This tests ensures we don't regress in that
        manner again.

        Also test against some sample "good" output that would be included in a correct
        orchestrate run.
        '''
        #ret_output = self.run_run_plus('state.orchestrate', 'orch.simple')['out']
        ret_output = self.run_run('state.orchestrate orch.simple')
        bad_out = ['outputter:', '    highstate']
        good_out = ['    Function: salt.state',
                    '      Result: True',
                    'Succeeded: 1 (changed=1)',
                    'Failed:    0',
                    'Total states run:     1']

        # First, check that we don't have the "bad" output that was displaying in
        # Issue #31330 where only the highstate outputter was listed
        self.assertIsNot(bad_out, ret_output)

        # Now test that some expected good sample output is present in the return.
        for item in good_out:
            self.assertIn(item, ret_output)

    def test_orchestrate_nested(self):
        '''
        test salt-run state.orchestrate and failhard with nested orchestration
        '''
        if os.path.exists('/tmp/ewu-2016-12-13'):
            os.remove('/tmp/ewu-2016-12-13')

        _, code = self.run_run(
                'state.orchestrate nested-orch.outer',
                with_retcode=True)

        self.assertFalse(os.path.exists('/tmp/ewu-2016-12-13'))
        self.assertNotEqual(code, 0)

    def test_state_event(self):
        '''
        test to ensure state.event
        runner returns correct data
        '''
        q = queue.Queue(maxsize=0)

        cmd = 'state.event salt/job/*/new count=1'
        expect = '"minions": ["minion"]'
        server_thread = threading.Thread(target=self.add_to_queue, args=(q, cmd))
        server_thread.setDaemon(True)
        server_thread.start()

        while q.empty():
            self.run_salt('minion test.ping --static')
        out = q.get()
        self.assertIn(expect, str(out))

        server_thread.join()


@skipIf(salt.utils.is_windows(), '*NIX-only test')
class OrchEventTest(integration.ShellCase):
    '''
    Tests for orchestration events
    '''
    def setUp(self):
        self.timeout = 60
        self.master_d_dir = os.path.join(self.get_config_dir(), 'master.d')
        try:
            os.makedirs(self.master_d_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        self.conf = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.conf',
            dir=self.master_d_dir,
            delete=True,
        )
        self.base_env = tempfile.mkdtemp(dir=integration.TMP)

    def tearDown(self):
        shutil.rmtree(self.base_env)
        self.conf.close()
        # Force a reload of the configuration now that our temp config file has
        # been removed.
        self.run_run_plus('test.arg', __reload_config=True)

    def alarm_handler(self, signal, frame):
        raise Exception('Timeout of {0} seconds reached'.format(self.timeout))

    def write_conf(self, data):
        '''
        Dump the config dict to the conf file
        '''
        self.conf.write(yaml.dump(data, default_flow_style=False))
        self.conf.flush()

    def test_jid_in_ret_event(self):
        '''
        Test to confirm that the ret event for the orchestration contains the
        jid for the jobs spawned.
        '''
        self.write_conf({
            'fileserver_backend': ['roots'],
            'file_roots': {
                'base': [self.base_env],
            },
        })

        state_sls = os.path.join(self.base_env, 'test_state.sls')
        with salt.utils.fopen(state_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                date:
                  cmd.run
            '''))

        orch_sls = os.path.join(self.base_env, 'test_orch.sls')
        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                date_cmd:
                  salt.state:
                    - tgt: minion
                    - sls: test_state

                ping_minion:
                  salt.function:
                    - name: test.ping
                    - tgt: minion

                fileserver.file_list:
                  salt.runner

                config.values:
                  salt.wheel
            '''))

        listener = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)

        jid = self.run_run_plus(
            'state.orchestrate',
            'test_orch',
            __reload_config=True).get('jid')

        if jid is None:
            raise Exception('jid missing from run_run_plus output')

        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)
        try:
            while True:
                event = listener.get_event(full=True)
                if event is None:
                    continue

                if event['tag'] == 'salt/run/{0}/ret'.format(jid):
                    # Don't wrap this in a try/except. We want to know if the
                    # data structure is different from what we expect!
                    ret = event['data']['return']['data']['master']
                    for job in ret:
                        self.assertTrue('__jid__' in ret[job])
                    break
        finally:
            signal.alarm(0)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateRunnerTest)
    run_tests(OrchEventTest)
