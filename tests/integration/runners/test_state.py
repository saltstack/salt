# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import
import errno
import logging
import os
import shutil
import signal
import tempfile
import time
import textwrap
import yaml
import threading
from salt.ext.six.moves import queue

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.helpers import flaky
from tests.support.paths import TMP
from tests.support.unit import skipIf

# Import Salt Libs
import salt.utils
import salt.utils.event

log = logging.getLogger(__name__)


class StateRunnerTest(ShellCase):
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
        ret_output = self.run_run('state.orchestrate orch.simple')
        bad_out = ['outputter:', '    highstate']
        good_out = ['    Function: salt.state',
                    '      Result: True',
                    'Succeeded: 1 (changed=1)',
                    'Failed:    0',
                    'Total states run:     1']

        # First, check that we don't have the "bad" output that was displaying in
        # Issue #31330 where only the highstate outputter was listed
        assert bad_out != ret_output

        # Now test that some expected good sample output is present in the return.
        for item in good_out:
            assert item in ret_output

    def test_orchestrate_nested(self):
        '''
        test salt-run state.orchestrate and failhard with nested orchestration
        '''
        if os.path.exists('/tmp/ewu-2016-12-13'):
            os.remove('/tmp/ewu-2016-12-13')

        _, code = self.run_run(
                'state.orchestrate nested-orch.outer',
                with_retcode=True)

        assert os.path.exists('/tmp/ewu-2016-12-13') is False
        assert code != 0

    @flaky
    def test_orchestrate_target_exists(self):
        '''
        test orchestration when target exists
        while using multiple states
        '''
        ret = self.run_run('state.orchestrate orch.target-exists')

        first = ['          ID: core',
                 '    Function: salt.state',
                 '      Result: True']

        second = ['          ID: test-state',
                  '    Function: salt.state',
                  '      Result: True']

        third = ['          ID: cmd.run',
                 '    Function: salt.function',
                 '      Result: True']

        ret_out = [first, second, third]

        for out in ret_out:
            for item in out:
                assert item in ret

    @flaky
    def test_orchestrate_target_doesnt_exist(self):
        '''
        test orchestration when target doesn't exist
        while using multiple states
        '''
        ret = self.run_run('state.orchestrate orch.target-doesnt-exists')

        first = ['No minions matched the target. No command was sent, no jid was assigned.',
                 '          ID: core',
                 '    Function: salt.state',
                 '      Result: False']

        second = ['          ID: test-state',
                  '    Function: salt.state',
                  '      Result: True']

        third = ['          ID: cmd.run',
                 '    Function: salt.function',
                 '      Result: True']

        ret_out = [first, second, third]

        for out in ret_out:
            for item in out:
                assert item in ret

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
        assert expect in str(out)

        server_thread.join()

    def test_orchestrate_subset(self):
        '''
        test orchestration state using subset
        '''
        ret = self.run_run('state.orchestrate orch.subset')

        def count(thing, listobj):
            return sum([obj.strip() == thing for obj in listobj])

        assert count('ID: test subset', ret) == 1
        assert count('Succeeded: 1', ret) == 1
        assert count('Failed:    0', ret) == 1

    def test_orchestrate_salt_function_return_false_failure(self):
        '''
        Ensure that functions that only return False in the return
        are flagged as failed when run as orchestrations.

        See https://github.com/saltstack/salt/issues/30367
        '''
        self.run_run('saltutil.sync_modules')
        ret = salt.utils.json.loads(
            '\n'.join(
                self.run_run('state.orchestrate orch.issue30367 --out=json')
            )
        )
        # Drill down to the changes dict
        state_result = ret['data']['master']['salt_|-deploy_check_|-test.false_|-function']['result']

        assert state_result is False


@skipIf(salt.utils.is_windows(), '*NIX-only test')
class OrchEventTest(ShellCase):
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
        self.base_env = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.base_env)
        self.addCleanup(self.conf.close)
        for attr in ('timeout', 'master_d_dir', 'conf', 'base_env'):
            self.addCleanup(delattr, self, attr)
        # Force a reload of the configuration now that our temp config file has
        # been removed.
        self.addCleanup(self.run_run_plus, 'test.arg', __reload_config=True)

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
            del listener
            signal.alarm(0)

    def test_parallel_orchestrations(self):
        '''
        Test to confirm that the parallel state requisite works in orch
        we do this by running 10 test.sleep's of 10 seconds, and insure it only takes roughly 10s
        '''
        self.write_conf({
            'fileserver_backend': ['roots'],
            'file_roots': {
                'base': [self.base_env],
            },
        })

        orch_sls = os.path.join(self.base_env, 'test_par_orch.sls')

        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                {% for count in range(1, 20) %}

                sleep {{ count }}:
                    module.run:
                        - name: test.sleep
                        - length: 10
                        - parallel: True

                {% endfor %}

                sleep 21:
                    module.run:
                        - name: test.sleep
                        - length: 10
                        - parallel: True
                        - require:
                            - module: sleep 1
            '''))

        orch_sls = os.path.join(self.base_env, 'test_par_orch.sls')

        listener = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)

        start_time = time.time()
        jid = self.run_run_plus(
            'state.orchestrate',
            'test_par_orch',
            __reload_config=True).get('jid')

        if jid is None:
            raise Exception('jid missing from run_run_plus output')

        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)
        received = False
        try:
            while True:
                event = listener.get_event(full=True)
                if event is None:
                    continue

                # if we receive the ret for this job before self.timeout (60),
                # the test is implicitly sucessful; if it were happening in serial it would be
                # atleast 110 seconds.
                if event['tag'] == 'salt/run/{0}/ret'.format(jid):
                    received = True
                    # Don't wrap this in a try/except. We want to know if the
                    # data structure is different from what we expect!
                    ret = event['data']['return']['data']['master']
                    for state in ret:
                        data = ret[state]
                        # we expect each duration to be greater than 10s
                        self.assertTrue(data['duration'] > 10000)
                    break

                # self confirm that the total runtime is roughly 30s (left 10s for buffer)
                self.assertTrue((time.time() - start_time) < 40)
        finally:
            self.assertTrue(received)
            del listener
            signal.alarm(0)

    def test_orchestration_with_pillar_dot_items(self):
        '''
        Test to confirm when using a state file that includes other state file, if
        one of those state files includes pillar related functions that will not
        be pulling from the pillar cache that all the state files are available and
        the file_roots has been preserved.  See issues #48277 and #46986.
        '''
        self.write_conf({
            'fileserver_backend': ['roots'],
            'file_roots': {
                'base': [self.base_env],
            },
        })

        orch_sls = os.path.join(self.base_env, 'main.sls')
        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                include:
                  - one
                  - two
                  - three
            '''))

        orch_sls = os.path.join(self.base_env, 'one.sls')
        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                {%- set foo = salt['saltutil.runner']('pillar.show_pillar') %}
                placeholder_one:
                  test.succeed_without_changes
            '''))

        orch_sls = os.path.join(self.base_env, 'two.sls')
        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                placeholder_two:
                  test.succeed_without_changes
            '''))

        orch_sls = os.path.join(self.base_env, 'three.sls')
        with salt.utils.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                placeholder_three:
                  test.succeed_without_changes
            '''))

        orch_sls = os.path.join(self.base_env, 'main.sls')

        listener = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)

        start_time = time.time()
        jid = self.run_run_plus(
            'state.orchestrate',
            'main',
            __reload_config=True).get('jid')

        if jid is None:
            raise salt.exceptions.SaltInvocationError('jid missing from run_run_plus output')

        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)
        received = False
        try:
            while True:
                event = listener.get_event(full=True)
                if event is None:
                    continue
                if event.get('tag', '') == 'salt/run/{0}/ret'.format(jid):
                    received = True
                    # Don't wrap this in a try/except. We want to know if the
                    # data structure is different from what we expect!
                    ret = event['data']['return']['data']['master']
                    for state in ret:
                        data = ret[state]
                        # Each state should be successful
                        self.assertEqual(data['comment'], 'Success!')
                    break
        finally:
            self.assertTrue(received)
            del listener
            signal.alarm(0)
