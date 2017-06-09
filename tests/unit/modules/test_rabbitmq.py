# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.rabbitmq as rabbitmq
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.rabbitmq
    '''
    def setup_loader_modules(self):
        return {rabbitmq: {'__context__': {'rabbitmqctl': None, 'rabbitmq-plugins': None}}}

    # 'list_users_rabbitmq2' function tests: 1

    def test_list_users_rabbitmq2(self):
        '''
        Test if it return a list of users based off of rabbitmqctl user_list.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'Listing users ...\nguest\t[administrator, user]\njustAnAdmin\t[administrator]\n',
            'stderr': '',
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_users(),
                                 {'guest': ['administrator', 'user'], 'justAnAdmin': ['administrator']})

    # 'list_users_rabbitmq3' function tests: 1

    def test_list_users_rabbitmq3(self):
        '''
        Test if it return a list of users based off of rabbitmqctl user_list.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'guest\t[administrator user]\r\nother\t[a b]\r\n',
            'stderr': ''
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_users(), {'guest': ['administrator', 'user'], 'other': ['a', 'b']})

    # 'list_users_with_warning_rabbitmq2' function tests: 1

    def test_list_users_with_warning_rabbitmq2(self):
        '''
        Test if having a leading WARNING returns the user_list anyway.
        '''
        rtn_stdout = '\n'.join([
            'WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to /etc/rabbitmq/rabbitmq-env.conf',
            'Listing users ...',
            'guest\t[administrator, user]\n',
        ])
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': rtn_stdout, 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_users(), {'guest': ['administrator', 'user']})

    # 'list_users_with_warning_rabbitmq3' function tests: 1

    def test_list_users_with_warning_rabbitmq3(self):
        '''
        Test if having a leading WARNING returns the user_list anyway.
        '''
        rtn_stdout = '\n'.join([
            'WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to /etc/rabbitmq/rabbitmq-env.conf',
            'Listing users ...',
            'guest\t[administrator user]\n',
        ])
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': rtn_stdout, 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_users(), {'guest': ['administrator', 'user']})

    # 'list_vhosts' function tests: 2

    def test_list_vhosts(self):
        '''
        Test if it return a list of vhost based on rabbitmqctl list_vhosts.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': '/\nsaltstack\n...', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertListEqual(rabbitmq.list_vhosts(), ['/', 'saltstack', '...'])

    def test_list_vhosts_with_warning(self):
        '''
        Test if it return a list of vhost based on rabbitmqctl list_vhosts even with a leading WARNING.
        '''
        rtn_stdout = '\n'.join([
            'WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to /etc/rabbitmq/rabbitmq-env.conf',
            'Listing users ...',
            '/',
            'saltstack',
            '...\n',
        ])
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': rtn_stdout, 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertListEqual(rabbitmq.list_vhosts(), ['/', 'saltstack', '...'])

    # 'user_exists' function tests: 2

    def test_user_exists(self):
        '''
        Test whether a given rabbitmq-internal user exists based
        on rabbitmqctl list_users.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing users ...\nsaltstack\t[administrator]\n...done', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.user_exists('saltstack'))

    def test_user_exists_negative(self):
        '''
        Negative test of whether rabbitmq-internal user exists based
        on rabbitmqctl list_users.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing users ...\nsaltstack\t[administrator]\n...done', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertFalse(rabbitmq.user_exists('salt'))

    # 'vhost_exists' function tests: 2

    def test_vhost_exists(self):
        '''
        Test if it return whether the vhost exists based
        on rabbitmqctl list_vhosts.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing vhosts ...\nsaltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.vhost_exists('saltstack'))

    def test_vhost_exists_negative(self):
        '''
        Test if it return whether the vhost exists based
        on rabbitmqctl list_vhosts.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing vhosts ...\nsaltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertFalse(rabbitmq.vhost_exists('salt'))

    # 'add_user' function tests: 1

    def test_add_user(self):
        '''
        Test if it add a rabbitMQ user via rabbitmqctl
        user_add <user> <password>
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.add_user('saltstack'),
                                 {'Added': 'saltstack'})

        mock_run = MagicMock(return_value='Error')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            with patch.object(rabbitmq, 'clear_password',
                              return_value={'Error': 'Error', 'retcode': 1}):
                self.assertRaises(CommandExecutionError, rabbitmq.add_user, 'saltstack')

    # 'delete_user' function tests: 1

    def test_delete_user(self):
        '''
        Test if it deletes a user via rabbitmqctl delete_user.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.delete_user('saltstack'),
                                 {'Deleted': 'saltstack'})

    # 'change_password' function tests: 1

    def test_change_password(self):
        '''
        Test if it changes a user's password.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.change_password('saltstack',
                                                          'salt@123'),
                                 {'Password Changed': 'saltstack'})

    # 'clear_password' function tests: 1

    def test_clear_password(self):
        '''
        Test if it removes a user's password.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.clear_password('saltstack'),
                                 {'Password Cleared': 'saltstack'})

    # 'add_vhost' function tests: 1

    def test_add_vhost(self):
        '''
        Test if it adds a vhost via rabbitmqctl add_vhost.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.add_vhost('saltstack'),
                                 {'Added': 'saltstack'})

    # 'delete_vhost' function tests: 1

    def test_delete_vhost(self):
        '''
        Test if it deletes a vhost rabbitmqctl delete_vhost.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.delete_vhost('saltstack'),
                                 {'Deleted': 'saltstack'})

    # 'set_permissions' function tests: 1

    def test_set_permissions(self):
        '''
        Test if it sets permissions for vhost via rabbitmqctl set_permissions.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.set_permissions('myvhost', 'myuser'),
                                 {'Permissions Set': 'saltstack'})

    # 'list_permissions' function tests: 1

    def test_list_permissions(self):
        '''
        Test if it lists permissions for a vhost
        via rabbitmqctl list_permissions.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'Listing stuff ...\nsaltstack\tsaltstack\t.*\t1\nguest\t0\tone\n...done',
            'stderr': '',
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_user_permissions('myuser'),
                                 {'saltstack': ['saltstack', '.*', '1'], 'guest': ['0', 'one']})

    # 'list_user_permissions' function tests: 1

    def test_list_user_permissions(self):
        '''
        Test if it list permissions for a user
        via rabbitmqctl list_user_permissions.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'Listing stuff ...\nsaltstack\tsaltstack\t0\t1\nguest\t0\tone\n...done',
            'stderr': '',
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_user_permissions('myuser'),
                                 {'saltstack': ['saltstack', '0', '1'], 'guest': ['0', 'one']})

    # 'set_user_tags' function tests: 1

    def test_set_user_tags(self):
        '''
        Test if it add user tags via rabbitmqctl set_user_tags.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.set_user_tags('myadmin', 'admin'),
                                 {'Tag(s) set': 'saltstack'})

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return rabbitmq status.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.status(), 'saltstack')

    # 'cluster_status' function tests: 1

    def test_cluster_status(self):
        '''
        Test if it return rabbitmq cluster_status.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.cluster_status(), 'saltstack')

    # 'join_cluster' function tests: 1

    def test_join_cluster(self):
        '''
        Test if it join a rabbit cluster.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.join_cluster('rabbit.example.com'),
                                 {'Join': 'saltstack'})

    # 'stop_app' function tests: 1

    def test_stop_app(self):
        '''
        Test if it stops the RabbitMQ application,
        leaving the Erlang node running.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.stop_app(), 'saltstack')

    # 'start_app' function tests: 1

    def test_start_app(self):
        '''
        Test if it start the RabbitMQ application.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.start_app(), 'saltstack')

    # 'reset' function tests: 1

    def test_reset(self):
        '''
        Test if it return a RabbitMQ node to its virgin state
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.reset(), 'saltstack')

    # 'force_reset' function tests: 1

    def test_force_reset(self):
        '''
        Test if it forcefully Return a RabbitMQ node to its virgin state
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertEqual(rabbitmq.force_reset(), 'saltstack')

    # 'list_queues' function tests: 1

    def test_list_queues(self):
        '''
        Test if it returns queue details of the / virtual host
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\t0\nceleryev.234-234\t10', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_queues(), {'saltstack': ['0'], 'celeryev.234-234': ['10']})

    # 'list_queues_vhost' function tests: 1

    def test_list_queues_vhost(self):
        '''
        Test if it returns queue details of specified virtual host.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\t0\nceleryev.234-234\t10', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_queues_vhost('consumers'), {'saltstack': ['0'], 'celeryev.234-234': ['10']})

    # 'list_policies' function tests: 1

    def test_list_policies(self):
        '''
        Test if it return a dictionary of policies nested by vhost
        and name based on the data returned from rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_policies(), {})

    # 'set_policy' function tests: 1

    def test_set_policy(self):
        '''
        Test if it set a policy based on rabbitmqctl set_policy.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.set_policy('/', 'HA', '.*',
                                                     '{"ha-mode": "all"}'),
                                 {'Set': 'saltstack'})

    # 'delete_policy' function tests: 1

    def test_delete_policy(self):
        '''
        Test if it delete a policy based on rabbitmqctl clear_policy.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.delete_policy('/', 'HA'),
                                 {'Deleted': 'saltstack'})

    # 'policy_exists' function tests: 1

    def test_policy_exists(self):
        '''
        Test if it return whether the policy exists
        based on rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertFalse(rabbitmq.policy_exists('/', 'HA'))

    # 'list_available_plugins' function tests: 2

    def test_list_available_plugins(self):
        '''
        Test if it returns a list of plugins.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\nsalt\nother', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertListEqual(rabbitmq.list_available_plugins(), ['saltstack', 'salt', 'other'])

    def test_list_available_plugins_space_delimited(self):
        '''
        Test if it returns a list of plugins.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack salt other', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertListEqual(rabbitmq.list_available_plugins(), ['saltstack', 'salt', 'other'])

    # 'list_enabled_plugins' function tests: 2

    def test_list_enabled_plugins(self):
        '''
        Test if it returns a list of plugins.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\nsalt\nother', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertListEqual(rabbitmq.list_enabled_plugins(), ['saltstack', 'salt', 'other'])

    def test_list_enabled_plugins_space_delimited(self):
        '''
        Test if it returns a list of plugins.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack salt other', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertListEqual(rabbitmq.list_enabled_plugins(), ['saltstack', 'salt', 'other'])

    # 'plugin_is_enabled' function tests: 2

    def test_plugin_is_enabled(self):
        '''
        Test if it returns true for an enabled plugin.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\nsalt\nother', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertTrue(rabbitmq.plugin_is_enabled('saltstack'))
            self.assertTrue(rabbitmq.plugin_is_enabled('salt'))
            self.assertTrue(rabbitmq.plugin_is_enabled('other'))

    def test_plugin_is_enabled_negative(self):
        '''
        Test if it returns false for a disabled plugin.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\nother', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertFalse(rabbitmq.plugin_is_enabled('salt'))
            self.assertFalse(rabbitmq.plugin_is_enabled('stack'))
            self.assertFalse(rabbitmq.plugin_is_enabled('random'))

    # 'enable_plugin' function tests: 1

    def test_enable_plugin(self):
        '''
        Test if it enable a RabbitMQ plugin via the rabbitmq-plugins command.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
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
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertDictEqual(rabbitmq.disable_plugin('salt'),
                                 {'Disabled': 'saltstack'})
