# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.rabbitmq as rabbitmq
from salt.exceptions import CommandExecutionError


RABBITMQ_3_5_7_STATUS = """Status of node rabbit@gandalf ...
[{pid,2988},
 {running_applications,
     [{rabbitmq_shovel_management,"Shovel Status","3.5.7"},
      {rabbitmq_management,"RabbitMQ Management Console","3.5.7"},
      {rabbitmq_web_dispatch,"RabbitMQ Web Dispatcher","3.5.7"},
      {webmachine,"webmachine","1.10.3-rmq3.5.7-gite9359c7"},
      {mochiweb,"MochiMedia Web Server","2.7.0-rmq3.5.7-git680dba8"},
      {rabbitmq_shovel,"Data Shovel for RabbitMQ","3.5.7"},
      {rabbitmq_management_agent,"RabbitMQ Management Agent","3.5.7"},
      {rabbit,"RabbitMQ","3.5.7"},
      {ssl,"Erlang/OTP SSL application","7.3.3.2"},
      {public_key,"Public key infrastructure","1.1.1"},
      {crypto,"CRYPTO","3.6.3.1"},
      {asn1,"The Erlang ASN1 compiler version 4.0.2","4.0.2"},
      {amqp_client,"RabbitMQ AMQP Client","3.5.7"},
      {xmerl,"XML parser","1.3.10"},
      {os_mon,"CPO  CXC 138 46","2.4"},
      {mnesia,"MNESIA  CXC 138 12","4.13.4"},
      {inets,"INETS  CXC 138 49","6.2.4.1"},
      {sasl,"SASL  CXC 138 11","2.7"},
      {stdlib,"ERTS  CXC 138 10","2.8"},
      {kernel,"ERTS  CXC 138 10","4.2"}]},
 {os,{unix,linux}},
 {erlang_version,
     "Erlang/OTP 18 [erts-7.3.1.4] [source] [64-bit] [smp:8:8] [async-threads:64] [hipe] [kernel-poll:true]\n"},
 {memory,
     [{total,86817752},
      {connection_readers,2807320},
      {connection_writers,413248},
      {connection_channels,1989064},
      {connection_other,3832384},
      {queue_procs,4740376},
      {queue_slave_procs,0},
      {plugins,514048},
      {other_proc,20519496},
      {mnesia,65560},
      {mgmt_db,2570616},
      {msg_index,47264},
      {other_ets,1767392},
      {binary,11929008},
      {code,22817793},
      {atom,842665},
      {other_system,11961518}]},
 {alarms,[]},
 {listeners,[{clustering,25672,"::"},{'amqp/ssl',5671,"::"}]},
 {vm_memory_high_watermark,0.4},
 {vm_memory_limit,13455246950},
 {disk_free_limit,50000000},
 {disk_free,38402478080},
 {file_descriptors,
     [{total_limit,29900},
      {total_used,96},
      {sockets_limit,26908},
      {sockets_used,93}]},
 {processes,[{limit,1048576},{used,1298}]},
 {run_queue,0},
 {uptime,3788208}]
"""

RABBITMQ_3_8_2_STATUS = """Status of node rabbit@localhost ...
Runtime

OS PID: 2120
OS: Linux
Uptime (seconds): 68586
RabbitMQ version: 3.8.2
Node name: rabbit@localhost
Erlang configuration: Erlang/OTP 22 [erts-10.6.4] [source] [64-bit] [smp:2:2] [ds:2:2:10] [async-threads:64] [hipe]
Erlang processes: 634 used, 1048576 limit
Scheduler run queue: 1
Cluster heartbeat timeout (net_ticktime): 60

Plugins

Enabled plugin file: /etc/rabbitmq/enabled_plugins
Enabled plugins:

 * rabbitmq_shovel_management
 * rabbitmq_management
 * rabbitmq_web_dispatch
 * rabbitmq_shovel
 * rabbitmq_management_agent
 * amqp_client
 * cowboy
 * amqp10_client
 * amqp10_common
 * cowlib

Data directory

Node data directory: /var/lib/rabbitmq/mnesia/rabbit@localhost

Config files

 * /etc/rabbitmq/rabbitmq.config

Log file(s)

 * /var/log/rabbitmq/rabbit@localhost.log
 * /var/log/rabbitmq/rabbit@localhost_upgrade.log

Alarms

(none)

Memory

Calculation strategy: rss
Memory high watermark setting: 0.4 of available memory, computed to: 1.6295 gb
code: 0.0308 gb (30.37 %)
other_proc: 0.0301 gb (29.59 %)
allocated_unused: 0.0162 gb (15.95 %)
other_system: 0.0127 gb (12.54 %)
other_ets: 0.0032 gb (3.17 %)
plugins: 0.0027 gb (2.68 %)
atom: 0.0015 gb (1.5 %)
connection_other: 0.0013 gb (1.32 %)
mgmt_db: 0.0009 gb (0.88 %)
reserved_unallocated: 0.0008 gb (0.78 %)
binary: 0.0004 gb (0.35 %)
metrics: 0.0003 gb (0.25 %)
msg_index: 0.0002 gb (0.23 %)
queue_procs: 0.0001 gb (0.14 %)
mnesia: 0.0001 gb (0.11 %)
connection_readers: 0.0001 gb (0.07 %)
quorum_ets: 0.0 gb (0.04 %)
connection_writers: 0.0 gb (0.02 %)
connection_channels: 0.0 gb (0.01 %)
queue_slave_procs: 0.0 gb (0.0 %)
quorum_queue_procs: 0.0 gb (0.0 %)

File Descriptors

Total: 14, limit: 32671
Sockets: 8, limit: 29401

Free Disk Space

Low free disk space watermark: 0.05 gb
Free disk space: 6.765 gb

Totals

Connection count: 3
Queue count: 6
Virtual host count: 1

Listeners

Interface: [::], port: 25672, protocol: clustering, purpose: inter-node and CLI tool communication
Interface: [::], port: 5671, protocol: amqp/ssl, purpose: AMQP 0-9-1 and AMQP 1.0 over TLS
Interface: [::], port: 55672, protocol: http, purpose: HTTP API
"""


def no_more_cmds(cmd, *args, **kwargs):
    raise AssertionError("No mock for command {cmd}".format(cmd=cmd))


def mock_run_rabbitmqctl_status(output, default=no_more_cmds):
    def cmd_run(cmd, *args, **kwargs):
        if cmd == [rabbitmq.RABBITMQCTL, 'status']:
            return output
        else:
            return default(cmd, *args, **kwargs)

    return cmd_run


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
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing users ...\n'
                                                                   'saltstack\t[administrator]\n...done', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.user_exists('saltstack'))

    def test_user_exists_negative(self):
        '''
        Negative test of whether rabbitmq-internal user exists based
        on rabbitmqctl list_users.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'Listing users ...\n'
                                                                   'saltstack\t[administrator]\n...done', 'stderr': ''})
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
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\t0\nceleryev.234-234\t10',
                                           'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_queues(), {'saltstack': ['0'], 'celeryev.234-234': ['10']})

    # 'list_queues_vhost' function tests: 1

    def test_list_queues_vhost(self):
        '''
        Test if it returns queue details of specified virtual host.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack\t0\nceleryev.234-234\t10',
                                           'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertDictEqual(rabbitmq.list_queues_vhost('consumers'), {'saltstack': ['0'],
                                                                           'celeryev.234-234': ['10']})

    # 'list_policies' function tests: 3

    def test_list_policies(self):
        '''
        Test if it return a dictionary of policies nested by vhost
        and name based on the data returned from rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}), \
                patch.dict(rabbitmq.__grains__, {'os_family': ''}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 8, 2]):
            self.assertDictEqual(rabbitmq.list_policies(), {})

    def test_list_policies_freebsd(self):
        '''
        Test if it return a dictionary of policies nested by vhost
        and name based on the data returned from rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}), \
                patch.dict(rabbitmq.__grains__, {'os_family': 'FreeBSD'}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 8, 2]):
            self.assertDictEqual(rabbitmq.list_policies(), {})

    def test_list_policies_old_version(self):
        '''
        Test if it return a dictionary of policies nested by vhost
        and name based on the data returned from rabbitmqctl list_policies.
        '''
        mock_run = MagicMock(return_value={'retcode': 0, 'stdout': 'saltstack', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}), \
                patch.dict(rabbitmq.__grains__, {'os_family': ''}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 5, 7]):
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
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}), \
                patch.dict(rabbitmq.__grains__, {'os_family': ''}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 8, 2]):
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

    # 'list_upstreams' function tests: 1

    def test_list_upstreams(self):
        '''
        Test if it returns a list of upstreams.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                      ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                      'password@remote.fqdn"}',
            'stderr': ''})
        mock_pkg = MagicMock(return_value='')
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run,
                                            'pkg.version': mock_pkg}):
            self.assertDictEqual(
                rabbitmq.list_upstreams(),
                {'remote-name': ('{"ack-mode":"on-confirm","max-hops":1,'
                                 '"trust-user-id":true,"uri":"amqp://username:'
                                 'password@remote.fqdn"}')}
            )

    # 'upstream_exists' function tests: 2

    def test_upstream_exists(self):
        '''
        Test whether a given rabbitmq-internal upstream exists based
        on rabbitmqctl list_upstream.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                      ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                      'password@remote.fqdn"}',
            'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.upstream_exists('remote-name'))

    def test_upstream_exists_negative(self):
        '''
        Negative test of whether rabbitmq-internal upstream exists based
        on rabbitmqctl list_upstream.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': 'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                      ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                      'password@remote.fqdn"}',
            'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertFalse(rabbitmq.upstream_exists('does-not-exist'))

    # 'add_upstream' function tests: 1

    def test_set_upstream(self):
        '''
        Test if a rabbitMQ upstream gets configured properly.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': ('Setting runtime parameter "federation-upstream" for component '
                       '"remote-name" to "{"trust-user-id": true, "uri": '
                       '"amqp://username:password@remote.fqdn", "ack-mode": "on-confirm", '
                       '"max-hops": 1}" in vhost "/" ...'),
            'stderr': ''
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.set_upstream('remote-name',
                                                  'amqp://username:password@remote.fqdn',
                                                  ack_mode='on-confirm',
                                                  max_hops=1,
                                                  trust_user_id=True))

    # 'delete_upstream' function tests: 2

    def test_delete_upstream(self):
        '''
        Test if an upstream gets deleted properly using rabbitmqctl delete_upstream.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 0,
            'stdout': ('Clearing runtime parameter "remote-name" for component '
                       '"federation-upstream" on vhost "/" ...'),
            'stderr': ''
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertTrue(rabbitmq.delete_upstream('remote-name'))

    def test_delete_upstream_negative(self):
        '''
        Negative test trying to delete a non-existant upstream.
        '''
        mock_run = MagicMock(return_value={
            'retcode': 70,
            'stdout': ('Clearing runtime parameter "remote-name" for component '
                       '"federation-upstream" on vhost "/" ...'),
            'stderr': 'Error:\nParameter does not exist'
        })
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run}):
            self.assertRaises(CommandExecutionError, rabbitmq.delete_upstream, 'remote-name')

    # '_get_server_version' function tests: 2

    def test__get_server_version_old(self):
        '''
        Test if the version from the old (pre-3.7) rabbitmqctl status is parsed correctly
        '''
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run_rabbitmqctl_status(RABBITMQ_3_5_7_STATUS)}):
            self.assertListEqual(rabbitmq._get_server_version(), [3, 5, 7])

    def test__get_server_version_post_3_7(self):
        '''
        Test if the version from the new (post-3.7) rabbitmqctl status is parsed correctly
        '''
        with patch.dict(rabbitmq.__salt__, {'cmd.run': mock_run_rabbitmqctl_status(RABBITMQ_3_8_2_STATUS)}):
            self.assertListEqual(rabbitmq._get_server_version(), [3, 8, 2])

    # 'check_password' function tests: 2

    def test_check_password_old_api(self):
        '''
        Test if check_password uses the old API on old versions (pre-3.5.7)
        '''
        mock_run_all = MagicMock(return_value={'retcode': 0, 'stdout': '', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run_all}), \
                patch.dict(rabbitmq.__grains__, {'os_family': ''}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 5, 6]):
            result = rabbitmq.check_password('saltstack', 'dummy')
            self.assertTrue(result)
            # Ensure "authenticate_user" API is NOT being used
            self.assertNotEqual(mock_run_all.call_args.args[0][1], 'authenticate_user')

    def test_check_password_new_api(self):
        '''
        Test if check_password uses the new API on new versions (post-3.5.7)
        '''
        mock_run_all = MagicMock(return_value={'retcode': 0, 'stdout': '', 'stderr': ''})
        with patch.dict(rabbitmq.__salt__, {'cmd.run_all': mock_run_all}), \
                patch.dict(rabbitmq.__grains__, {'os_family': ''}), \
                patch.object(rabbitmq, '_get_server_version', return_value=[3, 5, 7]):
            result = rabbitmq.check_password('saltstack', 'dummy')
            self.assertTrue(result)
            # Ensure "authenticate_user" API is being used
            self.assertEqual(mock_run_all.call_args.args[0][1], 'authenticate_user')
