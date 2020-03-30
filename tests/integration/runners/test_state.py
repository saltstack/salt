# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import logging
import os
import shutil
import signal
import tempfile
import time
import textwrap
import threading

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase
from tests.support.helpers import flaky, expensiveTest
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf

# Import Salt Libs
import salt.exceptions
import salt.utils.platform
import salt.utils.event
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import queue

log = logging.getLogger(__name__)


@flaky
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

    def test_orchestrate_with_mine(self):
        '''
        test salt-run state.orchestrate with mine.get call in sls
        '''
        fail_time = time.time() + 120
        self.run_run('mine.update "*"')

        exp_ret = 'Succeeded: 1 (changed=1)'
        while True:
            ret = self.run_run('state.orchestrate orch.mine')
            try:
                assert exp_ret in ret
                break
            except AssertionError:
                if time.time() > fail_time:
                    self.fail('"{0}" was not found in the orchestration call'.format(exp_ret))

    def test_orchestrate_state_and_function_failure(self):
        '''
        Ensure that returns from failed minions are in the changes dict where
        they belong, so they can be programatically analyzed.

        See https://github.com/saltstack/salt/issues/43204
        '''
        self.run_run('saltutil.sync_modules')
        ret = salt.utils.json.loads(
            '\n'.join(
                self.run_run('state.orchestrate orch.issue43204 --out=json')
            )
        )
        # Drill down to the changes dict
        state_ret = ret['data']['master']['salt_|-Step01_|-Step01_|-state']['changes']
        func_ret = ret['data']['master']['salt_|-Step02_|-runtests_helpers.nonzero_retcode_return_false_|-function']['changes']

        # Remove duration and start time from the results, since they would
        # vary with each run and that would make it impossible to test.
        for item in ('duration', 'start_time'):
            state_ret['ret']['minion']['test_|-test fail with changes_|-test fail with changes_|-fail_with_changes'].pop(item)

        self.assertEqual(
            state_ret,
            {
                'out': 'highstate',
                'ret': {
                    'minion': {
                        'test_|-test fail with changes_|-test fail with changes_|-fail_with_changes': {
                            '__id__': 'test fail with changes',
                            '__run_num__': 0,
                            '__sls__': 'orch.issue43204.fail_with_changes',
                            'changes': {
                                'testing': {
                                    'new': 'Something pretended to change',
                                    'old': 'Unchanged'
                                }
                            },
                            'comment': 'Failure!',
                            'name': 'test fail with changes',
                            'result': False,
                        }
                    }
                }
            }
        )

        self.assertEqual(
            func_ret,
            {'out': 'highstate', 'ret': {'minion': False}}
        )

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

    def test_orchestrate_retcode(self):
        '''
        Test orchestration with nonzero retcode set in __context__
        '''
        self.run_run('saltutil.sync_runners')
        self.run_run('saltutil.sync_wheel')
        ret = '\n'.join(self.run_run('state.orchestrate orch.retcode'))

        for result in ('          ID: test_runner_success\n'
                       '    Function: salt.runner\n'
                       '        Name: runtests_helpers.success\n'
                       '      Result: True',

                       '          ID: test_runner_failure\n'
                       '    Function: salt.runner\n'
                       '        Name: runtests_helpers.failure\n'
                       '      Result: False',

                       '          ID: test_wheel_success\n'
                       '    Function: salt.wheel\n'
                       '        Name: runtests_helpers.success\n'
                       '      Result: True',

                       '          ID: test_wheel_failure\n'
                       '    Function: salt.wheel\n'
                       '        Name: runtests_helpers.failure\n'
                       '      Result: False'):
            self.assertIn(result, ret)

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

    def test_orchestrate_batch_with_failhard_error(self):
        '''
        test orchestration properly stops with failhard and batch.
        '''
        ret = self.run_run('state.orchestrate orch.batch --out=json -l critical')
        ret_json = salt.utils.json.loads('\n'.join(ret))
        retcode = ret_json['retcode']
        result = ret_json['data']['master']['salt_|-call_fail_state_|-call_fail_state_|-state']['result']
        changes = ret_json['data']['master']['salt_|-call_fail_state_|-call_fail_state_|-state']['changes']

        # Looks like there is a platform differences in execution.
        # I see empty changes dict in MacOS for some reason. Maybe it's a bug?
        if changes:
            changes_ret = changes['ret']

        # Debug
        print('Retcode: {}'.format(retcode))
        print('Changes: {}'.format(changes))
        print('Result: {}'.format(result))

        assert retcode != 0
        assert result is False
        if changes:
            # The execution should stop after first error, so return dict should contain only one minion
            assert len(changes_ret) == 1

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
        assert expect in six.text_type(out)

        server_thread.join()

    def test_orchestrate_subset(self):
        '''
        test orchestration state using subset
        '''
        ret = self.run_run('state.orchestrate orch.subset', timeout=500)

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
        func_ret = ret['data']['master']['salt_|-deploy_check_|-test.false_|-function']['changes']

        assert state_result is False

        self.assertEqual(
            func_ret,
            {'out': 'highstate', 'ret': {'minion': False}}
        )


@skipIf(salt.utils.platform.is_windows(), '*NIX-only test')
@flaky
class OrchEventTest(ShellCase):
    '''
    Tests for orchestration events
    '''
    def setUp(self):
        self.timeout = 60
        self.master_d_dir = os.path.join(self.config_dir, 'master.d')
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
        self.base_env = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
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
        self.conf.write(salt.utils.yaml.safe_dump(data, default_flow_style=False))
        self.conf.flush()

    @expensiveTest
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
        with salt.utils.files.fopen(state_sls, 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
                date:
                  cmd.run
            ''')))

        orch_sls = os.path.join(self.base_env, 'test_orch.sls')
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(salt.utils.stringutils.to_str(textwrap.dedent('''
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
            ''')))

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

    @expensiveTest
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

        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
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

    @expensiveTest
    def test_orchestration_soft_kill(self):
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

        orch_sls = os.path.join(self.base_env, 'two_stage_orch_kill.sls')

        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                stage_one:
                    test.succeed_without_changes

                stage_two:
                    test.fail_without_changes
            '''))

        listener = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)

        mock_jid = '20131219120000000000'
        self.run_run('state.soft_kill {0} stage_two'.format(mock_jid))
        with patch('salt.utils.jid.gen_jid', MagicMock(return_value=mock_jid)):
            jid = self.run_run_plus(
                'state.orchestrate',
                'two_stage_orch_kill',
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

                # Ensure that stage_two of the state does not run
                if event['tag'] == 'salt/run/{0}/ret'.format(jid):
                    received = True
                    # Don't wrap this in a try/except. We want to know if the
                    # data structure is different from what we expect!
                    ret = event['data']['return']['data']['master']
                    self.assertNotIn('test_|-stage_two_|-stage_two_|-fail_without_changes', ret)
                    break

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
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                include:
                  - one
                  - two
                  - three
            '''))

        orch_sls = os.path.join(self.base_env, 'one.sls')
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                {%- set foo = salt['saltutil.runner']('pillar.show_pillar') %}
                placeholder_one:
                  test.succeed_without_changes
            '''))

        orch_sls = os.path.join(self.base_env, 'two.sls')
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                placeholder_two:
                  test.succeed_without_changes
            '''))

        orch_sls = os.path.join(self.base_env, 'three.sls')
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
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

    def test_orchestration_onchanges_and_prereq(self):
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

        orch_sls = os.path.join(self.base_env, 'orch.sls')
        with salt.utils.files.fopen(orch_sls, 'w') as fp_:
            fp_.write(textwrap.dedent('''
                manage_a_file:
                  salt.state:
                    - tgt: minion
                    - sls:
                      - orch.req_test

                do_onchanges:
                  salt.function:
                    - tgt: minion
                    - name: test.ping
                    - onchanges:
                      - salt: manage_a_file

                do_prereq:
                  salt.function:
                    - tgt: minion
                    - name: test.ping
                    - prereq:
                      - salt: manage_a_file
            '''))

        listener = salt.utils.event.get_event(
            'master',
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            opts=self.master_opts)

        try:
            jid1 = self.run_run_plus(
                'state.orchestrate',
                'orch',
                test=True,
                __reload_config=True).get('jid')

            # Run for real to create the file
            self.run_run_plus(
                'state.orchestrate',
                'orch',
                __reload_config=True).get('jid')

            # Run again in test mode. Since there were no changes, the
            # requisites should not fire.
            jid2 = self.run_run_plus(
                'state.orchestrate',
                'orch',
                test=True,
                __reload_config=True).get('jid')
        finally:
            try:
                os.remove(os.path.join(RUNTIME_VARS.TMP, 'orch.req_test'))
            except OSError:
                pass

        assert jid1 is not None
        assert jid2 is not None

        tags = {'salt/run/{0}/ret'.format(x): x for x in (jid1, jid2)}
        ret = {}

        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)
        try:
            while True:
                event = listener.get_event(full=True)
                if event is None:
                    continue

                if event['tag'] in tags:
                    ret[tags.pop(event['tag'])] = self.repack_state_returns(
                        event['data']['return']['data']['master']
                    )
                    if not tags:
                        # If tags is empty, we've grabbed all the returns we
                        # wanted, so let's stop listening to the event bus.
                        break
        finally:
            del listener
            signal.alarm(0)

        for sls_id in ('manage_a_file', 'do_onchanges', 'do_prereq'):
            # The first time through, all three states should have a None
            # result, while the second time through, they should all have a
            # True result.
            assert ret[jid1][sls_id]['result'] is None, \
                'result of {0} ({1}) is not None'.format(
                    sls_id,
                    ret[jid1][sls_id]['result'])
            assert ret[jid2][sls_id]['result'] is True, \
                'result of {0} ({1}) is not True'.format(
                    sls_id,
                    ret[jid2][sls_id]['result'])

        # The file.managed state should have shown changes in the test mode
        # return data.
        assert ret[jid1]['manage_a_file']['changes']

        # After the file was created, running again in test mode should have
        # shown no changes.
        assert not ret[jid2]['manage_a_file']['changes'], \
            ret[jid2]['manage_a_file']['changes']
