# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import sys
import tempfile
import textwrap
import threading
import time

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.unit import skipIf, WAR_ROOM_SKIP
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt libs
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


DEFAULT_ENDING = salt.utils.stringutils.to_bytes(os.linesep)


def trim_line_end(line):
    '''
    Remove CRLF or LF from the end of line.
    '''
    if line[-2:] == salt.utils.stringutils.to_bytes('\r\n'):
        return line[:-2]
    elif line[-1:] == salt.utils.stringutils.to_bytes('\n'):
        return line[:-1]
    raise Exception("Invalid line ending")


def reline(source, dest, force=False, ending=DEFAULT_ENDING):
    '''
    Normalize the line endings of a file.
    '''
    fp, tmp = tempfile.mkstemp()
    os.close(fp)
    with salt.utils.files.fopen(tmp, 'wb') as tmp_fd:
        with salt.utils.files.fopen(source, 'rb') as fd:
            lines = fd.readlines()
            for line in lines:
                line_noend = trim_line_end(line)
                tmp_fd.write(line_noend + ending)
    if os.path.exists(dest) and force:
        os.remove(dest)
    os.rename(tmp, dest)


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
class StateModuleTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the state module
    '''

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        def _reline(path, ending=DEFAULT_ENDING):
            '''
            Normalize the line endings of a file.
            '''
            with salt.utils.files.fopen(path, 'rb') as fhr:
                lines = fhr.read().splitlines()
            with salt.utils.atomicfile.atomic_open(path, 'wb') as fhw:
                for line in lines:
                    fhw.write(line + ending)

        destpath = os.path.join(RUNTIME_VARS.BASE_FILES, 'testappend', 'firstif')
        _reline(destpath)
        destpath = os.path.join(RUNTIME_VARS.BASE_FILES, 'testappend', 'secondif')
        _reline(destpath)
        cls.TIMEOUT = 600 if salt.utils.platform.is_windows() else 10

    def normalize_ret(self, ret):
        '''
        Normalize the return to the format that we'll use for result checking
        '''
        result = {}
        for item, descr in six.iteritems(ret):
            result[item] = {
                '__run_num__': descr['__run_num__'],
                'comment': descr['comment'],
                'result': descr['result'],
                'changes': descr['changes'] != {}  # whether there where any changes
            }
        return result

    # onfail tests

    # listen tests

    def test_listen_in_requisite_resolution(self):
        '''
        Verify listen_in requisite lookups use ID declaration to check for changes
        '''

        # Only run the state once and keep the return data
        state_run = self.run_function('state.sls', mods='requisites.listen_in_simple')

        # Test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listen_in_resolution_|-echo "Successful listen_in resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

    def test_listen_requisite_resolution(self):
        '''
        Verify listen requisite lookups use ID declaration to check for changes
        '''

        # Only run the state once and keep the return data
        state_run = self.run_function('state.sls', mods='requisites.listen_simple')

        # Both listeners are expected to trigger
        listener_state = 'cmd_|-listener_test_listening_resolution_one_|-echo "Successful listen resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        listener_state = 'cmd_|-listener_test_listening_resolution_two_|-echo "Successful listen resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

    def test_listen_requisite_no_state_module(self):
        '''
        Tests a simple state using the listen requisite
        '''

        # Only run the state once and keep the return data
        state_run = self.run_function('state.sls', mods='requisites.listen_simple_no_state_module')
        # First, test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        # Then, test the result of the state run when a listener should not trigger
        absent_state = 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch'
        self.assertNotIn(absent_state, state_run)

    def test_listen_in_requisite_resolution_names(self):
        '''
        Verify listen_in requisite lookups use ID declaration to check for changes
        and resolves magic names state variable
        '''

        # Only run the state once and keep the return data
        state_run = self.run_function('state.sls', mods='requisites.listen_in_names')
        self.assertIn('test_|-listener_service_|-nginx_|-mod_watch', state_run)
        self.assertIn('test_|-listener_service_|-crond_|-mod_watch', state_run)

    def test_listen_requisite_resolution_names(self):
        '''
        Verify listen requisite lookups use ID declaration to check for changes
        and resolves magic names state variable
        '''

        # Only run the state once and keep the return data
        state_run = self.run_function('state.sls',
                                      mods='requisites.listen_names',
                                      timeout=self.TIMEOUT)
        self.assertIn('test_|-listener_service_|-nginx_|-mod_watch', state_run)
        self.assertIn('test_|-listener_service_|-crond_|-mod_watch', state_run)

    def test_issue_30820_requisite_in_match_by_name(self):
        '''
        This tests the case where a requisite_in matches by name instead of ID

        See https://github.com/saltstack/salt/issues/30820 for more info
        '''
        state_run = self.run_function(
            'state.sls',
            mods='requisites.requisite_in_match_by_name'
        )
        bar_state = 'cmd_|-bar state_|-echo bar_|-wait'

        self.assertIn(bar_state, state_run)
        self.assertEqual(state_run[bar_state]['comment'],
                         'Command "echo bar" run')

    def test_retry_option_defaults(self):
        '''
        test the retry option on a simple state with defaults
        ensure comment is as expected
        ensure state duration is greater than default retry_interval (30 seconds)
        '''
        state_run = self.run_function(
            'state.sls',
            mods='retry.retry_defaults'
        )
        retry_state = 'file_|-file_test_|-/path/to/a/non-existent/file.txt_|-exists'
        expected_comment = ('Attempt 1: Returned a result of "False", with the following '
                'comment: "Specified path /path/to/a/non-existent/file.txt does not exist"\n'
                'Specified path /path/to/a/non-existent/file.txt does not exist')
        self.assertEqual(state_run[retry_state]['comment'], expected_comment)
        self.assertTrue(state_run[retry_state]['duration'] > 30)
        self.assertEqual(state_run[retry_state]['result'], False)

    def test_retry_option_custom(self):
        '''
        test the retry option on a simple state with custom retry values
        ensure comment is as expected
        ensure state duration is greater than custom defined interval * (retries - 1)
        '''
        state_run = self.run_function(
            'state.sls',
            mods='retry.retry_custom'
        )
        retry_state = 'file_|-file_test_|-/path/to/a/non-existent/file.txt_|-exists'
        expected_comment = ('Attempt 1: Returned a result of "False", with the following '
                'comment: "Specified path /path/to/a/non-existent/file.txt does not exist"\n'
                'Attempt 2: Returned a result of "False", with the following comment: "Specified'
                ' path /path/to/a/non-existent/file.txt does not exist"\nAttempt 3: Returned'
                ' a result of "False", with the following comment: "Specified path'
                ' /path/to/a/non-existent/file.txt does not exist"\nAttempt 4: Returned a'
                ' result of "False", with the following comment: "Specified path'
                ' /path/to/a/non-existent/file.txt does not exist"\nSpecified path'
                ' /path/to/a/non-existent/file.txt does not exist')
        self.assertEqual(state_run[retry_state]['comment'], expected_comment)
        self.assertTrue(state_run[retry_state]['duration'] > 40)
        self.assertEqual(state_run[retry_state]['result'], False)

    def test_retry_option_success(self):
        '''
        test a state with the retry option that should return True immedietly (i.e. no retries)
        '''
        testfile = os.path.join(RUNTIME_VARS.TMP, 'retry_file')
        state_run = self.run_function(
            'state.sls',
            mods='retry.retry_success'
        )
        os.unlink(testfile)
        retry_state = 'file_|-file_test_|-{0}_|-exists'.format(testfile)
        self.assertNotIn('Attempt', state_run[retry_state]['comment'])

    def run_create(self):
        '''
        helper function to wait 30 seconds and then create the temp retry file
        '''
        testfile = os.path.join(RUNTIME_VARS.TMP, 'retry_file')
        time.sleep(30)
        with salt.utils.files.fopen(testfile, 'a'):
            pass

    @flaky
    def test_retry_option_eventual_success(self):
        '''
        test a state with the retry option that should return True after at least 4 retry attmempt
        but never run 15 attempts
        '''
        testfile = os.path.join(RUNTIME_VARS.TMP, 'retry_file')
        create_thread = threading.Thread(target=self.run_create)
        create_thread.start()
        state_run = self.run_function(
            'state.sls',
            mods='retry.retry_success2'
        )
        retry_state = 'file_|-file_test_|-{0}_|-exists'.format(testfile)
        self.assertIn('Attempt 1:', state_run[retry_state]['comment'])
        self.assertIn('Attempt 2:', state_run[retry_state]['comment'])
        self.assertIn('Attempt 3:', state_run[retry_state]['comment'])
        self.assertIn('Attempt 4:', state_run[retry_state]['comment'])
        self.assertNotIn('Attempt 15:', state_run[retry_state]['comment'])
        self.assertEqual(state_run[retry_state]['result'], True)

    def test_issue_38683_require_order_failhard_combination(self):
        '''
        This tests the case where require, order, and failhard are all used together in a state definition.

        Previously, the order option, which used in tandem with require and failhard, would cause the state
        compiler to stacktrace. This exposed a logic error in the ``check_failhard`` function of the state
        compiler. With the logic error resolved, this test should now pass.

        See https://github.com/saltstack/salt/issues/38683 for more information.
        '''
        state_run = self.run_function(
            'state.sls',
            mods='requisites.require_order_failhard_combo'
        )
        state_id = 'test_|-b_|-b_|-fail_with_changes'

        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'], 'Failure!')
        self.assertFalse(state_run[state_id]['result'])

    def test_issue_46762_prereqs_on_a_state_with_unfulfilled_requirements(self):
        '''
        This tests the case where state C requires state A, which fails.
        State C is a pre-required state for State B.
        Since state A fails, state C will not run because the requisite failed,
        therefore state B will not run because state C failed to run.

        See https://github.com/saltstack/salt/issues/46762 for
        more information.
        '''
        state_run = self.run_function(
            'state.sls',
            mods='issue-46762'
        )

        state_id = 'test_|-a_|-a_|-fail_without_changes'
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'],
                         'Failure!')
        self.assertFalse(state_run[state_id]['result'])

        state_id = 'test_|-b_|-b_|-nop'
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'],
                         'One or more requisite failed: issue-46762.c')
        self.assertFalse(state_run[state_id]['result'])

        state_id = 'test_|-c_|-c_|-nop'
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'],
                         'One or more requisite failed: issue-46762.a')
        self.assertFalse(state_run[state_id]['result'])

    def test_state_nonbase_environment(self):
        '''
        test state.sls with saltenv using a nonbase environment
        with a salt source
        '''
        filename = os.path.join(RUNTIME_VARS.TMP, 'nonbase_env')
        try:
            ret = self.run_function(
                'state.sls',
                mods='non-base-env',
                saltenv='prod'
            )
            ret = ret[next(iter(ret))]
            assert ret['result']
            assert ret['comment'] == 'File {0} updated'.format(filename)
            assert os.path.isfile(filename)
        finally:
            try:
                os.remove(filename)
            except OSError:
                pass

    @skipIf(sys.platform.startswith('win'), 'Skipped until parallel states can be fixed on Windows')
    def test_parallel_state_with_long_tag(self):
        '''
        This tests the case where the state being executed has a long ID dec or
        name and states are being run in parallel. The filenames used for the
        parallel state cache were previously based on the tag for each chunk,
        and longer ID decs or name params can cause the cache file to be longer
        than the operating system's max file name length. To counter this we
        instead generate a SHA1 hash of the chunk's tag to use as the cache
        filename. This test will ensure that long tags don't cause caching
        failures.

        See https://github.com/saltstack/salt/issues/49738 for more info.
        '''
        short_command = 'helloworld'
        long_command = short_command * 25

        ret = self.run_function(
            'state.sls',
            mods='issue-49738',
            pillar={'short_command': short_command,
                    'long_command': long_command}
        )
        comments = sorted([x['comment'] for x in six.itervalues(ret)])
        expected = sorted(['Command "{0}" run'.format(x)
                           for x in (short_command, long_command)])
        assert comments == expected, '{0} != {1}'.format(comments, expected)

    def _add_runtime_pillar(self, pillar):
        '''
        helper class to add pillar data at runtime
        '''
        import salt.utils.yaml
        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE,
                                                 'pillar.sls'), 'w') as fp:
            salt.utils.yaml.safe_dump(pillar, fp)

        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                     base:
                       '*':
                         - pillar
                     '''))

        self.run_function('saltutil.refresh_pillar')
        self.run_function('test.sleep', [5])

    def test_state_sls_id_test(self):
        '''
        test state.sls_id when test is set
        to true in pillar data
        '''
        self._add_runtime_pillar(pillar={'test': True})
        testfile = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        comment = 'The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.'.format(testfile)
        ret = self.run_function('state.sls', ['core'])

        for key, val in ret.items():
            self.assertEqual(val['comment'], comment)
            self.assertEqual(val['changes'], {'newfile': testfile})

    def test_state_sls_id_test_state_test_post_run(self):
        '''
        test state.sls_id when test is set to
        true post the state already being run previously
        '''
        file_name = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        ret = self.run_function('state.sls', ['core'])
        for key, val in ret.items():
            self.assertEqual(val['comment'],
                             'File {0} updated'.format(file_name))
            self.assertEqual(val['changes']['diff'], 'New file')

        self._add_runtime_pillar(pillar={'test': True})
        ret = self.run_function('state.sls', ['core'])

        for key, val in ret.items():
            self.assertEqual(
                val['comment'],
                'The file {0} is in the correct state'.format(file_name))
            self.assertEqual(val['changes'], {})

    def test_state_sls_id_test_true(self):
        '''
        test state.sls_id when test=True is passed as arg
        '''
        file_name = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        ret = self.run_function('state.sls', ['core'], test=True)
        for key, val in ret.items():
            self.assertEqual(
                val['comment'],
                'The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.'.format(file_name))
            self.assertEqual(val['changes'], {'newfile': file_name})

    def test_state_sls_id_test_true_post_run(self):
        '''
        test state.sls_id when test is set to true as an
        arg post the state already being run previously
        '''
        file_name = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        ret = self.run_function('state.sls', ['core'])
        for key, val in ret.items():
            self.assertEqual(val['comment'],
                             'File {0} updated'.format(file_name))
            self.assertEqual(val['changes']['diff'], 'New file')

        ret = self.run_function('state.sls', ['core'], test=True)

        for key, val in ret.items():
            self.assertEqual(
                val['comment'],
                'The file {0} is in the correct state'.format(file_name))
            self.assertEqual(val['changes'], {})

    def test_state_sls_id_test_false_pillar_true(self):
        '''
        test state.sls_id when test is set to false as an
        arg and minion_state_test is set to True. Should
        return test=False.
        '''
        file_name = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        self._add_runtime_pillar(pillar={'test': True})
        ret = self.run_function('state.sls', ['core'], test=False)

        for key, val in ret.items():
            self.assertEqual(val['comment'],
                             'File {0} updated'.format(file_name))
            self.assertEqual(val['changes']['diff'], 'New file')

    def test_issue_30161_unless_and_onlyif_together(self):
        '''
        test cmd.run using multiple unless options where the first cmd in the
        list will pass, but the second will fail. This tests the fix for issue
        #35384. (The fix is in PR #35545.)
        '''
        sls = self.run_function('state.sls', mods='issue-30161')
        self.assertSaltTrueReturn(sls)
        # We must assert against the comment here to make sure the comment reads that the
        # command "echo "hello"" was run. This ensures that we made it to the last unless
        # command in the state. If the comment reads "unless condition is true", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
        _expected = {'file_|-unless_false_onlyif_false_|-{0}{1}test.txt_|-managed'.format(RUNTIME_VARS.TMP, os.path.sep):
                     {'comment': 'onlyif condition is false\nunless condition is false',
                      'name': '{0}{1}test.txt'.format(RUNTIME_VARS.TMP, os.path.sep),
                      'skip_watch': True,
                      'changes': {},
                      'result': True},
                     'file_|-unless_false_onlyif_true_|-{0}{1}test.txt_|-managed'.format(RUNTIME_VARS.TMP, os.path.sep):
                     {'comment': 'Empty file',
                      'name': '{0}{1}test.txt'.format(RUNTIME_VARS.TMP, os.path.sep),
                      'start_time': '18:10:20.341753',
                      'result': True,
                      'changes': {'new': 'file {0}{1}test.txt created'.format(RUNTIME_VARS.TMP, os.path.sep)}},
                     'file_|-unless_true_onlyif_false_|-{0}{1}test.txt_|-managed'.format(RUNTIME_VARS.TMP, os.path.sep):
                     {'comment': 'onlyif condition is false\nunless condition is true',
                      'name': '{0}{1}test.txt'.format(RUNTIME_VARS.TMP, os.path.sep),
                      'start_time': '18:10:22.936446',
                      'skip_watch': True,
                      'changes': {},
                      'result': True},
                     'file_|-unless_true_onlyif_true_|-{0}{1}test.txt_|-managed'.format(RUNTIME_VARS.TMP, os.path.sep):
                     {'comment': 'onlyif condition is true\nunless condition is true',
                      'name': '{0}{1}test.txt'.format(RUNTIME_VARS.TMP, os.path.sep),
                      'skip_watch': True,
                      'changes': {},
                      'result': True}}
        for id in _expected:
            self.assertEqual(sls[id]['comment'], _expected[id]['comment'])

    @skipIf(six.PY3 and salt.utils.platform.is_darwin(), 'Test is broken on macosx and PY3')
    def test_state_sls_unicode_characters(self):
        '''
        test state.sls when state file contains non-ascii characters
        '''
        ret = self.run_function('state.sls', ['issue-46672'])
        log.debug('== ret %s ==', type(ret))

        _expected = "cmd_|-echo1_|-echo 'This is Æ test!'_|-run"
        self.assertIn(_expected, ret)

    @skipIf(six.PY3 and salt.utils.platform.is_darwin(), 'Test is broken on macosx and PY3')
    def test_state_sls_unicode_characters_cmd_output(self):
        '''
        test the output from running and echo command with non-ascii
        characters.
        '''
        ret = self.run_function('state.sls', ['issue-46672-a'])
        key = list(ret.keys())[0]
        log.debug('== ret %s ==', type(ret))
        _expected = 'This is Æ test!'
        if salt.utils.platform.is_windows():
            # Windows cmd.exe will mangle the output using cmd's codepage.
            if six.PY2:
                _expected = "'This is A+ test!'"
            else:
                _expected = "'This is ’ test!'"
        self.assertEqual(_expected, ret[key]['changes']['stdout'])

    def tearDown(self):
        nonbase_file = os.path.join(RUNTIME_VARS.TMP, 'nonbase_env')
        if os.path.isfile(nonbase_file):
            os.remove(nonbase_file)

        # remove old pillar data
        for filename in os.listdir(RUNTIME_VARS.TMP_PILLAR_TREE):
            os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, filename))
        self.run_function('saltutil.refresh_pillar')
        self.run_function('test.sleep', [5])

        # remove testfile added in core.sls state file
        state_file = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        if os.path.isfile(state_file):
            os.remove(state_file)

        # remove testfile added in issue-30161.sls state file
        state_file = os.path.join(RUNTIME_VARS.TMP, 'test.txt')
        if os.path.isfile(state_file):
            os.remove(state_file)

    def test_state_sls_integer_name(self):
        '''
        This tests the case where the state file is named
        only with integers
        '''
        state_run = self.run_function(
            'state.sls',
            mods='12345'
        )

        state_id = 'test_|-always-passes_|-always-passes_|-succeed_without_changes'
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'],
                         'Success!')
        self.assertTrue(state_run[state_id]['result'])

    def test_state_sls_lazyloader_allows_recursion(self):
        '''
        This tests that referencing dunders like __salt__ work
        context: https://github.com/saltstack/salt/pull/51499
        '''
        state_run = self.run_function('state.sls', mods='issue-51499')

        state_id = 'test_|-always-passes_|-foo_|-succeed_without_changes'
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]['comment'],
                         'Success!')
        self.assertTrue(state_run[state_id]['result'])
