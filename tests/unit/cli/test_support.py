# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

from salt.cli.support.console import IndentOutput
from salt.cli.support.collector import SupportDataCollector, SaltSupport
from salt.utils.color import get_colors
from salt.utils.stringutils import to_bytes
import salt.exceptions
import salt.cli.support.collector
import salt.utils.files
import os
import yaml
import jinja2

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportIndentOutputTestCase(TestCase):
    '''
    Unit Tests for the salt-support indent output.
    '''

    def setUp(self):
        '''
        Setup test
        :return:
        '''

        self.message = 'Stubborn processes on dumb terminal'
        self.device = MagicMock()
        self.iout = IndentOutput(device=self.device)
        self.colors = get_colors()

    def tearDown(self):
        '''
        Remove instances after test run
        :return:
        '''
        del self.message
        del self.device
        del self.iout
        del self.colors

    def test_standard_output(self):
        '''
        Test console standard output.
        '''
        self.iout.put(self.message)
        assert self.device.write.called
        assert self.device.write.call_count == 5
        for idx, data in enumerate(['', str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), os.linesep]):
            assert self.device.write.call_args_list[idx][0][0] == data

    def test_indent_output(self):
        '''
        Test indent distance.
        :return:
        '''
        self.iout.put(self.message, indent=10)
        for idx, data in enumerate([' ' * 10, str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), os.linesep]):
            assert self.device.write.call_args_list[idx][0][0] == data

    def test_color_config(self):
        '''
        Test color config changes on each ident.
        :return:
        '''

        conf = {0: 'MAGENTA', 2: 'RED', 4: 'WHITE', 6: 'YELLOW'}
        self.iout = IndentOutput(conf=conf, device=self.device)
        for indent in sorted(list(conf)):
            self.iout.put(self.message, indent=indent)

        step = 1
        for ident_key in sorted(list(conf)):
            assert str(self.device.write.call_args_list[step][0][0]) == str(self.colors[conf[ident_key]])
            step += 5


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportCollectorTestCase(TestCase):
    '''
    Collector tests.
    '''
    def setUp(self):
        '''
        Setup the test case
        :return:
        '''
        self.archive_path = '/highway/to/hell'
        self.output_device = MagicMock()
        self.collector = SupportDataCollector(self.archive_path, self.output_device)

    def tearDown(self):
        '''
        Tear down the test case elements
        :return:
        '''
        del self.collector
        del self.archive_path
        del self.output_device

    @patch('salt.cli.support.collector.tarfile.TarFile', MagicMock())
    def test_archive_open(self):
        '''
        Test archive is opened.

        :return:
        '''
        self.collector.open()
        assert self.collector.archive_path == self.archive_path
        with pytest.raises(salt.exceptions.SaltException) as err:
            self.collector.open()
        assert 'Archive already opened' in str(err)

    @patch('salt.cli.support.collector.tarfile.TarFile', MagicMock())
    def test_archive_close(self):
        '''
        Test archive is opened.

        :return:
        '''
        self.collector.open()
        self.collector._flush_content = lambda: None
        self.collector.close()
        assert self.collector.archive_path == self.archive_path
        with pytest.raises(salt.exceptions.SaltException) as err:
            self.collector.close()
        assert 'Archive already closed' in str(err)

    def test_archive_addwrite(self):
        '''
        Test add to the archive a section and write to it.

        :return:
        '''
        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('foo')
            self.collector.write(title='title', data='data', output='null')
            self.collector._flush_content()

            assert (archive.bz2open().addfile.call_args[1]['fileobj'].read()
                    == to_bytes('title\n-----\n\nraw-content: data\n\n\n\n'))

    @patch('salt.utils.files.fopen', MagicMock(return_value='path=/dev/null'))
    def test_archive_addlink(self):
        '''
        Test add to the archive a section and link an external file or directory to it.

        :return:
        '''
        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('foo')
            self.collector.link(title='Backup Path', path='/path/to/backup.config')
            self.collector._flush_content()

            assert archive.bz2open().addfile.call_count == 1
            assert (archive.bz2open().addfile.call_args[1]['fileobj'].read()
                    == to_bytes('Backup Path\n-----------\n\npath=/dev/null\n\n\n'))

    @patch('salt.utils.files.fopen', MagicMock(return_value='path=/dev/null'))
    def test_archive_discard_section(self):
        '''
        Test discard a section from the archive.

        :return:
        '''
        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('solar-interference')
            self.collector.link(title='Thermal anomaly', path='/path/to/another/great.config')
            self.collector.add('foo')
            self.collector.link(title='Backup Path', path='/path/to/backup.config')
            self.collector._flush_content()
            assert archive.bz2open().addfile.call_count == 2
            assert (archive.bz2open().addfile.mock_calls[0][2]['fileobj'].read()
                    == to_bytes('Thermal anomaly\n---------------\n\npath=/dev/null\n\n\n'))
            self.collector.close()

        archive = MagicMock()
        with patch('salt.cli.support.collector.tarfile.TarFile', archive):
            self.collector.open()
            self.collector.add('solar-interference')
            self.collector.link(title='Thermal anomaly', path='/path/to/another/great.config')
            self.collector.discard_current()
            self.collector.add('foo')
            self.collector.link(title='Backup Path', path='/path/to/backup.config')
            self.collector._flush_content()
            assert archive.bz2open().addfile.call_count == 2
            assert (archive.bz2open().addfile.mock_calls[0][2]['fileobj'].read()
                    == to_bytes('Backup Path\n-----------\n\npath=/dev/null\n\n\n'))
            self.collector.close()


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportRunnerTestCase(TestCase):
    '''
    Test runner class.
    '''

    def setUp(self):
        '''
        Set up test suite.
        :return:
        '''
        self.archive_path = '/dev/null'
        self.output_device = MagicMock()
        self.runner = SaltSupport()
        self.runner.collector = SupportDataCollector(self.archive_path, self.output_device)

    def tearDown(self):
        '''
        Tear down.

        :return:
        '''
        del self.archive_path
        del self.output_device
        del self.runner

    def test_function_config(self):
        '''
        Test function config formation.

        :return:
        '''
        self.runner.config = {}
        msg = 'Electromagnetic energy loss'
        assert self.runner._setup_fun_config({'description': msg}) == {'print_metadata': False,
                                                                       'file_client': 'local',
                                                                       'fun': '', 'kwarg': {},
                                                                       'description': msg,
                                                                       'cache_jobs': False, 'arg': []}

    def test_local_caller(self):
        '''
        Test local caller.

        :return:
        '''
        msg = 'Because of network lag due to too many people playing deathmatch'
        caller = MagicMock()
        caller().call = MagicMock(return_value=msg)

        self.runner._get_caller = caller
        self.runner.out = MagicMock()
        assert self.runner._local_call({}) == msg

        caller().call = MagicMock(side_effect=SystemExit)
        assert self.runner._local_call({}) == 'Data is not available at this moment'

        err_msg = "The UPS doesn't have a battery backup."
        caller().call = MagicMock(side_effect=Exception(err_msg))
        assert self.runner._local_call({}) == "Unhandled exception occurred: The UPS doesn't have a battery backup."

    def test_local_runner(self):
        '''
        Test local runner.

        :return:
        '''
        msg = 'Big to little endian conversion error'
        runner = MagicMock()
        runner().run = MagicMock(return_value=msg)

        self.runner._get_runner = runner
        self.runner.out = MagicMock()
        assert self.runner._local_run({}) == msg

        runner().run = MagicMock(side_effect=SystemExit)
        assert self.runner._local_run({}) == 'Runner is not available at this moment'

        err_msg = 'Trojan horse ran out of hay'
        runner().run = MagicMock(side_effect=Exception(err_msg))
        assert self.runner._local_run({}) == 'Unhandled exception occurred: Trojan horse ran out of hay'

    @patch('salt.cli.support.intfunc', MagicMock(spec=[]))
    def test_internal_function_call_stub(self):
        '''
        Test missing internal function call is handled accordingly.

        :return:
        '''
        self.runner.out = MagicMock()
        out = self.runner._internal_function_call({'fun': 'everythingisawesome',
                                                   'arg': [], 'kwargs': {}})
        assert out == 'Function everythingisawesome is not available'

    def test_internal_function_call(self):
        '''
        Test missing internal function call is handled accordingly.

        :return:
        '''
        msg = 'Internet outage'
        intfunc = MagicMock()
        intfunc.everythingisawesome = MagicMock(return_value=msg)
        self.runner.out = MagicMock()
        with patch('salt.cli.support.intfunc', intfunc):
            out = self.runner._internal_function_call({'fun': 'everythingisawesome',
                                                       'arg': [], 'kwargs': {}})
            assert out == msg

    def test_get_action(self):
        '''
        Test action meta gets parsed.

        :return:
        '''
        action_meta = {'run:jobs.list_jobs_filter': {'info': 'List jobs filter', 'args': [1]}}
        assert self.runner._get_action(action_meta) == ('List jobs filter', None,
                                                        {'fun': 'run:jobs.list_jobs_filter', 'kwargs': {}, 'arg': [1]})
        action_meta = {'user.info': {'info': 'Information about "usbmux"', 'args': ['usbmux']}}
        assert self.runner._get_action(action_meta) == ('Information about "usbmux"', None,
                                                        {'fun': 'user.info', 'kwargs': {}, 'arg': ['usbmux']})

    def test_extract_return(self):
        '''
        Test extract return from the output.

        :return:
        '''
        out = {'key': 'value'}
        assert self.runner._extract_return(out) == out
        assert self.runner._extract_return({'return': out}) == out

    def test_get_action_type(self):
        '''
        Test action meta determines action type.

        :return:
        '''
        action_meta = {'run:jobs.list_jobs_filter': {'info': 'List jobs filter', 'args': [1]}}
        assert self.runner._get_action_type(action_meta) == 'run'

        action_meta = {'user.info': {'info': 'Information about "usbmux"', 'args': ['usbmux']}}
        assert self.runner._get_action_type(action_meta) == 'call'

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_cleanup(self):
        '''
        Test cleanup routine.

        :return:
        '''
        arch = '/tmp/killme.zip'
        unlink = MagicMock()
        with patch('os.unlink', unlink):
            self.runner.config = {'support_archive': arch}
            self.runner.out = MagicMock()
            self.runner._cleanup()

            assert self.runner.out.warning.call_args[0][0] == 'Terminated earlier, cleaning up'
            unlink.assert_called_once_with(arch)

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_check_existing_archive(self):
        '''
        Test check existing archive.

        :return:
        '''
        arch = '/tmp/endothermal-recalibration.zip'
        unlink = MagicMock()
        with patch('os.unlink', unlink), patch('os.path.exists', MagicMock(return_value=False)):
            self.runner.config = {'support_archive': '',
                                  'support_archive_force_overwrite': True}
            self.runner.out = MagicMock()
            assert self.runner._check_existing_archive()
            assert self.runner.out.warning.call_count == 0

        with patch('os.unlink', unlink):
            self.runner.config = {'support_archive': arch,
                                  'support_archive_force_overwrite': False}
            self.runner.out = MagicMock()
            assert not self.runner._check_existing_archive()
            assert self.runner.out.warning.call_args[0][0] == 'File {} already exists.'.format(arch)

        with patch('os.unlink', unlink):
            self.runner.config = {'support_archive': arch,
                                  'support_archive_force_overwrite': True}
            self.runner.out = MagicMock()
            assert self.runner._check_existing_archive()
            assert self.runner.out.warning.call_args[0][0] == 'Overwriting existing archive: {}'.format(arch)


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProfileIntegrityTestCase(TestCase):
    '''
    Default profile integrity
    '''
    def setUp(self):
        '''
        Set up test suite.

        :return:
        '''
        self.profiles = {}
        profiles = os.path.join(os.path.dirname(salt.cli.support.collector.__file__), 'profiles')
        for profile in os.listdir(profiles):
            self.profiles[profile.split('.')[0]] = os.path.join(profiles, profile)

    def tearDown(self):
        '''
        Tear down test suite.

        :return:
        '''
        del self.profiles

    def _render_template_to_yaml(self, name, *args, **kwargs):
        '''
        Get template referene for rendering.
        :return:
        '''
        with salt.utils.files.fopen(self.profiles[name]) as t_fh:
            template = t_fh.read()
        return yaml.load(jinja2.Environment().from_string(template).render(*args, **kwargs))

    def test_non_template_profiles_parseable(self):
        '''
        Test shipped default profile is YAML parse-able.

        :return:
        '''
        for t_name in ['default', 'jobs-active', 'jobs-last', 'network', 'postgres']:
            with salt.utils.files.fopen(self.profiles[t_name]) as ref:
                try:
                    yaml.load(ref)
                    parsed = True
                except Exception:
                    parsed = False
                assert parsed

    def test_users_template_profile(self):
        '''
        Test users template profile.

        :return:
        '''
        users_data = self._render_template_to_yaml('users', salt=MagicMock(return_value=['pokemon']))
        assert len(users_data['all-users']) == 5
        for user_data in users_data['all-users']:
            for tgt in ['user.list_groups', 'shadow.info', 'cron.raw_cron']:
                if tgt in user_data:
                    assert user_data[tgt]['args'] == ['pokemon']

    def test_jobs_trace_template_profile(self):
        '''
        Test jobs-trace template profile.

        :return:
        '''
        jobs_trace = self._render_template_to_yaml('jobs-trace', runners=MagicMock(return_value=['0000']))
        assert len(jobs_trace['jobs-details']) == 1
        assert jobs_trace['jobs-details'][0]['run:jobs.list_job']['info'] == 'Details on JID 0000'
        assert jobs_trace['jobs-details'][0]['run:jobs.list_job']['args'] == [0]
