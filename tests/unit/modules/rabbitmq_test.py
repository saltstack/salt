# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import rabbitmq
from salt.exceptions import CommandExecutionError

# Globals
rabbitmq.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqTestCase(TestCase):
    '''
    Test cases for salt.modules.rabbitmq
    '''
    # 'list_users' function tests: 1

    def test_list_users(self):
        '''
        Test if it return a list of users based off of rabbitmqctl user_list.
        '''
        mock_run = MagicMock(return_value='Listing users ...\nguest\t[administrator]\n')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.list_users(), {'guest': set(['administrator'])})

    # 'list_vhosts' function tests: 1

    def test_list_vhosts(self):
        '''
        Test if it return a list of vhost based on rabbitmqctl list_vhosts.
        '''
        mock_run = MagicMock(return_value='...\nsaltstack\n...')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertListEqual(rabbitmq.list_vhosts(), ['...', 'saltstack', '...'])

    # 'user_exists' function tests: 2

    def test_user_exists_negative(self):
        '''
        Negative test of whether rabbitmq-internal user exists based
        on rabbitmqctl list_users.
        '''
        mock_run = MagicMock(return_value='Listing users ...\nsaltstack\t[administrator]\n...done')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertFalse(rabbitmq.user_exists('rabbit_user'))

    def test_user_exists(self):
        '''
        Test whether a given rabbitmq-internal user exists based
        on rabbitmqctl list_users.
        '''
        mock_run = MagicMock(return_value='Listing users ...\nsaltstack\t[administrator]\n...done')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertTrue(rabbitmq.user_exists('saltstack'))

    # 'vhost_exists' function tests: 1

    def test_vhost_exists(self):
        '''
        Test if it return whether the vhost exists based
        on rabbitmqctl list_vhosts.
        '''
        mock_run = MagicMock(return_value='Listing vhosts ...\nsaltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertTrue(rabbitmq.vhost_exists('saltstack'))

    # 'add_user' function tests: 1

    def test_add_user(self):
        '''
        Test if it add a rabbitMQ user via rabbitmqctl
        user_add <user> <password>
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.add_user('saltstack'),
                                 {'Added': 'saltstack'})

        mock_run = MagicMock(return_value='Error')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            with patch.object(rabbitmq, 'clear_password',
                              return_value={'Error': 'Error', 'retcode': 1}):
                self.assertRaises(CommandExecutionError, rabbitmq.add_user, 'saltstack')

    # 'delete_user' function tests: 1

    def test_delete_user(self):
        '''
        Test if it deletes a user via rabbitmqctl delete_user.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.delete_user('saltstack'),
                                 {'Deleted': 'saltstack'})

    # 'change_password' function tests: 1

    def test_change_password(self):
        '''
        Test if it changes a user's password.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.change_password('saltstack',
                                                          'salt@123'),
                                 {'Password Changed': 'saltstack'})

    # 'clear_password' function tests: 1

    def test_clear_password(self):
        '''
        Test if it removes a user's password.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.clear_password('saltstack'),
                                 {'Password Cleared': 'saltstack'})

    # 'add_vhost' function tests: 1

    def test_add_vhost(self):
        '''
        Test if it adds a vhost via rabbitmqctl add_vhost.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.add_vhost('saltstack'),
                                 {'Added': 'saltstack'})

    # 'delete_vhost' function tests: 1

    def test_delete_vhost(self):
        '''
        Test if it deletes a vhost rabbitmqctl delete_vhost.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.delete_vhost('saltstack'),
                                 {'Deleted': 'saltstack'})

    # 'set_permissions' function tests: 1

    def test_set_permissions(self):
        '''
        Test if it sets permissions for vhost via rabbitmqctl set_permissions.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.set_permissions('myvhost', 'myuser'),
                                 {'Permissions Set': 'saltstack'})

    # 'list_user_permissions' function tests: 1

    def test_list_user_permissions(self):
        '''
        Test if it list permissions for a user
        via rabbitmqctl list_user_permissions.
        '''
        mock_run = MagicMock(return_value='Listing stuff ...\nsaltstack\tsaltstack\n...done')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.list_user_permissions('myuser'),
                                 {'saltstack': ['saltstack']})

    # 'set_user_tags' function tests: 1

    def test_set_user_tags(self):
        '''
        Test if it add user tags via rabbitmqctl set_user_tags.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.set_user_tags('myadmin', 'admin'),
                                 {'Tag(s) set': 'saltstack'})

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return rabbitmq status.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.status(), 'saltstack')

    # 'cluster_status' function tests: 1

    def test_cluster_status(self):
        '''
        Test if it return rabbitmq cluster_status.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.cluster_status(), 'saltstack')

    # 'join_cluster' function tests: 1

    def test_join_cluster(self):
        '''
        Test if it join a rabbit cluster.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.join_cluster('rabbit.example.com'),
                                 {'Join': 'saltstack'})

    # 'stop_app' function tests: 1

    def test_stop_app(self):
        '''
        Test if it stops the RabbitMQ application,
        leaving the Erlang node running.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.stop_app(), 'saltstack')

    # 'start_app' function tests: 1

    def test_start_app(self):
        '''
        Test if it start the RabbitMQ application.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.start_app(), 'saltstack')

    # 'reset' function tests: 1

    def test_reset(self):
        '''
        Test if it return a RabbitMQ node to its virgin state
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.reset(), 'saltstack')

    # 'force_reset' function tests: 1

    def test_force_reset(self):
        '''
        Test if it forcefully Return a RabbitMQ node to its virgin state
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.force_reset(), 'saltstack')

    # 'list_queues' function tests: 1

    def test_list_queues(self):
        '''
        Test if it returns queue details of the / virtual host
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.list_queues(), 'saltstack')

    # 'list_queues_vhost' function tests: 1

    def test_list_queues_vhost(self):
        '''
        Test if it returns queue details of specified virtual host.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertEqual(rabbitmq.list_queues_vhost('consumers'),
                             'saltstack')

    # 'list_policies' function tests: 1

    def test_list_policies(self):
        '''
        Test if it return a dictionary of policies nested by vhost
        and name based on the data returned from rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.list_policies(), {})

    # 'set_policy' function tests: 1

    def test_set_policy(self):
        '''
        Test if it set a policy based on rabbitmqctl set_policy.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.set_policy('/', 'HA', '.*',
                                                     '{"ha-mode": "all"}'),
                                 {'Set': 'saltstack'})

    # 'delete_policy' function tests: 1

    def test_delete_policy(self):
        '''
        Test if it delete a policy based on rabbitmqctl clear_policy.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertDictEqual(rabbitmq.delete_policy('/', 'HA'),
                                 {'Deleted': 'saltstack'})

    # 'policy_exists' function tests: 1

    def test_policy_exists(self):
        '''
        Test if it return whether the policy exists
        based on rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value='saltstack')
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run}):
            self.assertFalse(rabbitmq.policy_exists('/', 'HA'))

    # 'plugin_is_enabled' function tests: 1

    def test_plugin_is_enabled(self):
        '''
        Test if it return whether the plugin is enabled.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack'})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertTrue(rabbitmq.plugin_is_enabled('salt'))

    # 'enable_plugin' function tests: 1

    def test_enable_plugin(self):
        '''
        Test if it enable a RabbitMQ plugin via the rabbitmq-plugins command.
        '''
        mock_run = MagicMock(return_value='saltstack')
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertDictEqual(rabbitmq.enable_plugin('salt'),
                                 {'Enabled': 'saltstack'})

    # 'disable_plugin' function tests: 1

    def test_disable_plugin(self):
        '''
        Test if it disable a RabbitMQ plugin via the rabbitmq-plugins command.
        '''
        mock_run = MagicMock(return_value='saltstack')
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertDictEqual(rabbitmq.disable_plugin('salt'),
                                 {'Disabled': 'saltstack'})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqTestCase, needs_daemon=False)
