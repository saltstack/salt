# -*- coding: utf-8 -*-
from __future__ import absolute_import

from subprocess import PIPE

from salt.modules import openscap

from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OpenscapTestCase(TestCase):

    random_temp_dir = '/tmp/unique-name'
    policy_file = '/usr/share/openscap/policy-file-xccdf.xml'

    def setUp(self):
        patchers = [
            patch('salt.modules.openscap.Caller', MagicMock()),
            patch('salt.modules.openscap.shutil.rmtree', Mock()),
            patch(
                'salt.modules.openscap.tempfile.mkdtemp',
                Mock(return_value=self.random_temp_dir)
            ),
        ]
        for patcher in patchers:
            self.apply_patch(patcher)

    def apply_patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch(
       'salt.modules.openscap.Popen',
       MagicMock(
           return_value=Mock(
               **{'returncode': 0, 'communicate.return_value': ('', '')}
           )
       )
    )
    def test_openscap_xccdf_eval_success(self):
        response = openscap.xccdf(
            'eval --profile Default {0}'.format(self.policy_file))

        self.assertEqual(openscap.tempfile.mkdtemp.call_count, 1)
        expected_cmd = [
            'oscap',
            'xccdf',
            'eval',
            '--oval-results',
            '--results', 'results.xml',
            '--report', 'report.html',
            '--profile', 'Default',
            self.policy_file
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=PIPE,
            stdout=PIPE)
        openscap.Caller().cmd.assert_called_once_with(
            'cp.push_dir', self.random_temp_dir)
        self.assertEqual(openscap.shutil.rmtree.call_count, 1)
        self.assertEqual(
            response,
            {
                'upload_dir': self.random_temp_dir,
                'error': '',
                'success': True,
                'returncode': 0
            }
        )

    @patch(
       'salt.modules.openscap.Popen',
       MagicMock(
           return_value=Mock(
               **{'returncode': 2, 'communicate.return_value': ('', 'some error')}
           )
       )
    )
    def test_openscap_xccdf_eval_success_with_failing_rules(self):
        response = openscap.xccdf(
            'eval --profile Default {0}'.format(self.policy_file))

        self.assertEqual(openscap.tempfile.mkdtemp.call_count, 1)
        expected_cmd = [
            'oscap',
            'xccdf',
            'eval',
            '--oval-results',
            '--results', 'results.xml',
            '--report', 'report.html',
            '--profile', 'Default',
            self.policy_file
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=PIPE,
            stdout=PIPE)
        openscap.Caller().cmd.assert_called_once_with(
            'cp.push_dir', self.random_temp_dir)
        self.assertEqual(openscap.shutil.rmtree.call_count, 1)
        self.assertEqual(
            response,
            {
                'upload_dir': self.random_temp_dir,
                'error': 'some error',
                'success': True,
                'returncode': 2
            }
        )

    def test_openscap_xccdf_eval_fail_no_profile(self):
        response = openscap.xccdf(
            'eval --param Default /unknown/param')
        self.assertEqual(
            response,
            {
                'error': 'argument --profile is required',
                'upload_dir': None,
                'success': False,
                'returncode': None
            }
        )

    @patch(
       'salt.modules.openscap.Popen',
       MagicMock(
           return_value=Mock(
               **{'returncode': 2, 'communicate.return_value': ('', 'some error')}
           )
       )
    )
    def test_openscap_xccdf_eval_success_ignore_unknown_params(self):
        response = openscap.xccdf(
            'eval --profile Default --param Default /policy/file')
        self.assertEqual(
            response,
            {
                'upload_dir': self.random_temp_dir,
                'error': 'some error',
                'success': True,
                'returncode': 2
            }
        )
        expected_cmd = [
            'oscap',
            'xccdf',
            'eval',
            '--oval-results',
            '--results', 'results.xml',
            '--report', 'report.html',
            '--profile', 'Default',
            '/policy/file'
        ]
        openscap.Popen.assert_called_once_with(
            expected_cmd,
            cwd=openscap.tempfile.mkdtemp.return_value,
            stderr=PIPE,
            stdout=PIPE)

    @patch(
       'salt.modules.openscap.Popen',
       MagicMock(
           return_value=Mock(**{
               'returncode': 1,
               'communicate.return_value': ('', 'evaluation error')
           })
       )
    )
    def test_openscap_xccdf_eval_evaluation_error(self):
        response = openscap.xccdf(
            'eval --profile Default {0}'.format(self.policy_file))

        self.assertEqual(
            response,
            {
                'upload_dir': None,
                'error': 'evaluation error',
                'success': False,
                'returncode': 1
            }
        )

    def test_openscap_xccdf_eval_fail_not_implemented_action(self):
        response = openscap.xccdf('info {0}'.format(self.policy_file))

        self.assertEqual(
            response,
            {
                'upload_dir': None,
                'error': "argument action: invalid choice: 'info' (choose from 'eval')",
                'success': False,
                'returncode': None
            }
        )
