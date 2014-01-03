# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Python libs
import os

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, call, NO_MOCK, NO_MOCK_REASON, DEFAULT, MagicMock
ensure_in_syspath('../')

# Import Salt libs
import integration
from salt import client
from salt.exceptions import EauthAuthenticationError, SaltInvocationError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LocalClientTestCase(TestCase,
                          integration.AdaptedConfigurationTestCaseMixIn):
    def setUp(self):
        if not os.path.exists('/tmp/salttest'):
            # This path is hardcoded in the configuration file
            os.makedirs('/tmp/salttest/cache')
        if not os.path.exists(integration.TMP_CONF_DIR):
            os.makedirs(integration.TMP_CONF_DIR)

        self.local_client = client.LocalClient(
            self.get_config_file_path('master')
        )

    def test_create_local_client(self):
        local_client = client.LocalClient(self.get_config_file_path('master'))
        self.assertIsInstance(local_client, client.LocalClient, 'LocalClient did not create a LocalClient instance')

    def test_check_pub_data(self):
        just_minions = {'minions': ['m1', 'm2']}
        jid_no_minions = {'jid': '1234', 'minions': []}
        valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

        self.assertRaises(EauthAuthenticationError, self.local_client._check_pub_data, None)
        self.assertDictEqual({},
            self.local_client._check_pub_data(just_minions),
            'Did not handle lack of jid correctly')

        self.assertDictEqual(
            {},
            self.local_client._check_pub_data({'jid': '0'}),
            'Passing JID of zero is not handled gracefully')

        with patch.dict(self.local_client.opts, {}):
            self.local_client._check_pub_data(jid_no_minions)

        self.assertDictEqual(valid_pub_data, self.local_client._check_pub_data(valid_pub_data))

    @patch('salt.client.LocalClient.cmd', return_value={'minion1': ['first.func', 'second.func'],
                                                        'minion2': ['first.func', 'second.func']})
    def test_cmd_subset(self, cmd_mock):
        with patch('salt.client.LocalClient.cmd_cli') as cmd_cli_mock:
            self.local_client.cmd_subset('*', 'first.func', sub=1, cli=True)
            cmd_cli_mock.assert_called_with(['minion1'], 'first.func', (), kwarg=None, expr_form='list',
                                                ret=['first.func', 'second.func'])

            self.local_client.cmd_subset('*', 'first.func', sub=10, cli=True)
            cmd_cli_mock.assert_called_with(['minion1', 'minion2'], 'first.func', (), kwarg=None, expr_form='list',
                                                ret=['first.func', 'second.func'])

    def test_pub(self):
        # Make sure we cleanly return if the publisher isn't running
        with patch('os.path.exists', return_value=False):
            ret = self.local_client.pub('*', 'test.ping')
            expected_ret = {'jid': '0', 'minions': []}
            self.assertDictEqual(ret, expected_ret)

        # Check nodegroups behavior
        with patch('os.path.exists', return_value=True):
            with patch.dict(self.local_client.opts,
                            {'nodegroups':
                                 {'group1': 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'}}):
                # Do we raise an exception if the nodegroup can't be matched?
                self.assertRaises(SaltInvocationError,
                                  self.local_client.pub,
                                  'non_existant_group', 'test.ping', expr_form='nodegroup')
