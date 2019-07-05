# -*- coding: utf-8 -*-
'''
    :codeauthor: Mike Place <mp@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON, MagicMock
from tornado.concurrent import Future


# Import Salt libs
from salt import client
import salt.utils.platform
from salt.exceptions import (
    EauthAuthenticationError, SaltInvocationError, SaltClientError, SaltReqTimeoutError
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalClientTestCase(TestCase,
                          integration.SaltClientTestCaseMixin):

    def test_create_local_client(self):
        local_client = client.LocalClient(mopts=self.get_temp_config('master'))
        self.assertIsInstance(local_client, client.LocalClient, 'LocalClient did not create a LocalClient instance')

    def test_check_pub_data(self):
        just_minions = {'minions': ['m1', 'm2']}
        jid_no_minions = {'jid': '1234', 'minions': []}
        valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

        self.assertRaises(EauthAuthenticationError, self.client._check_pub_data, '')
        self.assertDictEqual({},
            self.client._check_pub_data(just_minions),
            'Did not handle lack of jid correctly')

        self.assertDictEqual(
            {},
            self.client._check_pub_data({'jid': '0'}),
            'Passing JID of zero is not handled gracefully')

        with patch.dict(self.client.opts, {}):
            self.client._check_pub_data(jid_no_minions)

        self.assertDictEqual(valid_pub_data, self.client._check_pub_data(valid_pub_data))

    def test__prep_pub(self):
        fake_pub = self.client._prep_pub('*', 'first.func', [], 'glob', None, '', 30, True)
        self.assertTrue(salt.utils.jid.is_jid(fake_pub['jid']))

    def test_get_iter_returns(self):
        closure_jid = {'count': 1}

        def get_load(jid):
            return {'jid': jid}

        def get_returns_no_block(tag, matcher=None):
            jid = int(tag.split('/').pop())

            if jid == 1:
                # original ret iterator
                def jit_iter():
                    while True:
                        if closure_jid['count'] < 5:
                            yield None
                        elif closure_jid['count'] >= 5:
                            yield {'data': {'retcode': 0, 'return': { 'ret': 'final result'}, 'id': 'minion1'}}
                            break
                return jit_iter()
            else:
                # gather_job_info calls
                self.assertTrue(len(self.client.event.pending_tags) == 1, msg='pending tags tracking only single jid while in flight')
                return iter([{'data': {'retcode': 0, 'return': { 'ret': 'still running'}, 'id': 'minion1'}}])

        def run_job(*args, **kwargs):
            closure_jid['count'] += 1
            return {'jid': str(closure_jid['count'])}

        with patch('salt.client.LocalClient.get_returns_no_block', side_effect=get_returns_no_block), \
                patch('salt.client.LocalClient.run_job', side_effect=run_job), \
                patch.object(self.client, 'returners', new={'local_cache.get_load': get_load}), \
                patch.dict(self.client.opts, {'timeout': 1, 'gather_job_timeout': 1, 'master_job_cache': 'local_cache'}):
            # clear pending tags to ensure test is sane
            self.client.event.pending_tags = []

            ret = list(self.client.get_iter_returns('1', 'minion1'))

            self.assertFalse(len(self.client.event.pending_tags), msg='pending tags are empty after get_iter_returns')
            self.assertIn('final result', ret[0]['minion1']['ret']['ret'])

    def test_cmd_subset(self):
        with patch('salt.client.LocalClient.cmd', return_value={'minion1': ['first.func', 'second.func'],
                                                                'minion2': ['first.func', 'second.func']}):
            with patch('salt.client.LocalClient.cmd_cli') as cmd_cli_mock:
                self.client.cmd_subset('*', 'first.func', sub=1, cli=True)
                try:
                    cmd_cli_mock.assert_called_with(['minion2'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=False,
                                                    ret='')
                except AssertionError:
                    cmd_cli_mock.assert_called_with(['minion1'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=False,
                                                    ret='')
                self.client.cmd_subset('*', 'first.func', sub=10, cli=True)
                try:
                    cmd_cli_mock.assert_called_with(['minion2', 'minion1'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=False,
                                                    ret='')
                except AssertionError:
                    cmd_cli_mock.assert_called_with(['minion1', 'minion2'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=False,
                                                    ret='')

                ret = self.client.cmd_subset('*', 'first.func', sub=1, cli=True, full_return=True)
                try:
                    cmd_cli_mock.assert_called_with(['minion2'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=True,
                                                    ret='')
                except AssertionError:
                    cmd_cli_mock.assert_called_with(['minion1'], 'first.func', (), progress=False,
                                                    kwarg=None, tgt_type='list', full_return=True,
                                                    ret='')

    @skipIf(salt.utils.platform.is_windows(), 'Not supported on Windows')
    def test_pub(self):
        '''
        Tests that the client cleanly returns when the publisher is not running

        Note: Requires ZeroMQ's IPC transport which is not supported on windows.
        '''
        if self.get_config('minion')['transport'] != 'zeromq':
            self.skipTest('This test only works with ZeroMQ')
        # Make sure we cleanly return if the publisher isn't running
        with patch('os.path.exists', return_value=False):
            self.assertRaises(SaltClientError, lambda: self.client.pub('*', 'test.ping'))

        # Check nodegroups behavior
        with patch('os.path.exists', return_value=True):
            with patch.dict(self.client.opts,
                            {'nodegroups':
                                 {'group1': 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'}}):
                # Do we raise an exception if the nodegroup can't be matched?
                self.assertRaises(SaltInvocationError,
                                  self.client.pub,
                                  'non_existent_group', 'test.ping', tgt_type='nodegroup')

    @skipIf(not salt.utils.platform.is_windows(), 'Windows only test')
    def test_pub_win32(self):
        '''
        Tests that the client raises a timeout error when using ZeroMQ's TCP
        transport and publisher is not running.

        Note: Requires ZeroMQ's TCP transport, this is only the default on Windows.
        '''
        if self.get_config('minion')['transport'] != 'zeromq':
            self.skipTest('This test only works with ZeroMQ')
        # Make sure we cleanly return if the publisher isn't running
        with patch('os.path.exists', return_value=False):
            self.assertRaises(SaltReqTimeoutError, lambda: self.client.pub('*', 'test.ping'))

        # Check nodegroups behavior
        with patch('os.path.exists', return_value=True):
            with patch.dict(self.client.opts,
                            {'nodegroups':
                                 {'group1': 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'}}):
                # Do we raise an exception if the nodegroup can't be matched?
                self.assertRaises(SaltInvocationError,
                                  self.client.pub,
                                  'non_existent_group', 'test.ping', tgt_type='nodegroup')

    # all of these parse_input test wrapper tests can be replaced by
    # parameterize if/when we switch to pytest runner
    #@pytest.mark.parametrize('method', [('run_job', 'cmd', ...)])
    def _test_parse_input(self, method, asynchronous=False):
        if asynchronous:
            target = 'salt.client.LocalClient.pub_async'
            pub_ret = Future()
            pub_ret.set_result({'jid': '123456789', 'minions': ['m1']})
        else:
            target = 'salt.client.LocalClient.pub'
            pub_ret = {'jid': '123456789', 'minions': ['m1']}

        with patch(target, return_value=pub_ret) as pub_mock:
            with patch('salt.client.LocalClient.get_cli_event_returns', return_value=[{'m1': {'ret': ['test.arg']}}]):
                with patch('salt.client.LocalClient.get_iter_returns', return_value=[{'m1': {'ret': True}}]):
                    ret = getattr(self.client, method)('*',
                            'test.arg',
                            arg=['a', 5, "yaml_arg={qux: Qux}", "another_yaml={bax: 12345}"],
                            jid='123456789')

                    # iterate generator if needed
                    if asynchronous:
                        pass
                    else:
                        ret = list(ret)

                    # main test here is that yaml_arg is getting deserialized properly
                    parsed_args = ['a', 5, {'yaml_arg': {'qux': 'Qux'}, 'another_yaml': {'bax': 12345}, '__kwarg__': True}]
                    self.assertTrue(any(parsed_args in call[0] for call in pub_mock.call_args_list))

    def test_parse_input_is_called(self):
        self._test_parse_input('run_job')
        self._test_parse_input('cmd')
        self._test_parse_input('cmd_subset')
        self._test_parse_input('cmd_batch')
        self._test_parse_input('cmd_cli')
        self._test_parse_input('cmd_full_return')
        self._test_parse_input('cmd_iter')
        self._test_parse_input('cmd_iter_no_block')
        self._test_parse_input('cmd_async')
        self._test_parse_input('run_job_async', asynchronous=True)
