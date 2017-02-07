# -*- coding: utf-8 -*-
'''
Unit tests for the Snapper module

:codeauthor:    Duncan Mac-Vicar P. <dmacvicar@suse.de>
:codeauthor:    Pablo Suárez Hernández <psuarezhernandez@suse.de>
'''

# Import Python libs
from __future__ import absolute_import
import sys

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch,
    mock_open,
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import salt.ext.six as six
from salt.exceptions import CommandExecutionError
from salt.modules import snapper

# Globals
snapper.__salt__ = dict()

DBUS_RET = {
    'ListSnapshots': [
        [42, 1, 0, 1457006571,
         0, 'Some description', '',
         {'userdata1': 'userval1', 'salt_jid': '20160607130930720112'}],
        [43, 2, 42, 1457006572,
         0, 'Blah Blah', '',
         {'userdata2': 'userval2', 'salt_jid': '20160607130930720112'}]
    ],
    'ListConfigs': [
        [u'root', u'/', {
            u'SUBVOLUME': u'/', u'NUMBER_MIN_AGE': u'1800',
            u'TIMELINE_LIMIT_YEARLY': u'4-10', u'NUMBER_LIMIT_IMPORTANT': u'10',
            u'FSTYPE': u'btrfs', u'TIMELINE_LIMIT_MONTHLY': u'4-10',
            u'ALLOW_GROUPS': u'', u'EMPTY_PRE_POST_MIN_AGE': u'1800',
            u'EMPTY_PRE_POST_CLEANUP': u'yes', u'BACKGROUND_COMPARISON': u'yes',
            u'TIMELINE_LIMIT_HOURLY': u'4-10', u'ALLOW_USERS': u'',
            u'TIMELINE_LIMIT_WEEKLY': u'0', u'TIMELINE_CREATE': u'no',
            u'NUMBER_CLEANUP': u'yes', u'TIMELINE_CLEANUP': u'yes',
            u'SPACE_LIMIT': u'0.5', u'NUMBER_LIMIT': u'10',
            u'TIMELINE_MIN_AGE': u'1800', u'TIMELINE_LIMIT_DAILY': u'4-10',
            u'SYNC_ACL': u'no', u'QGROUP': u'1/0'}
        ]
    ],
    'GetFiles': [
        ['/root/.viminfo', 8],
        ['/tmp/foo', 52],
        ['/tmp/foo2', 1],
        ['/tmp/foo3', 2],
        ['/var/log/snapper.log', 8],
        ['/var/cache/salt/minion/extmods/modules/snapper.py', 8],
        ['/var/cache/salt/minion/extmods/modules/snapper.pyc', 8],
    ],
}

FILE_CONTENT = {
    '/tmp/foo': {
        "pre": "dummy text",
        "post": "another foobar"
    },
    '/tmp/foo2': {
        "post": "another foobar"
    }
}

MODULE_RET = {
    'SNAPSHOTS': [
        {
            'userdata': {'userdata1': 'userval1', 'salt_jid': '20160607130930720112'},
            'description': 'Some description', 'timestamp': 1457006571,
            'cleanup': '', 'user': 'root', 'type': 'pre', 'id': 42
        },
        {
            'pre': 42,
            'userdata': {'userdata2': 'userval2', 'salt_jid': '20160607130930720112'},
            'description': 'Blah Blah', 'timestamp': 1457006572,
            'cleanup': '', 'user': 'root', 'type': 'post', 'id': 43
        }
    ],
    'LISTCONFIGS': {
        u'root': {
            u'SUBVOLUME': u'/', u'NUMBER_MIN_AGE': u'1800',
            u'TIMELINE_LIMIT_YEARLY': u'4-10', u'NUMBER_LIMIT_IMPORTANT': u'10',
            u'FSTYPE': u'btrfs', u'TIMELINE_LIMIT_MONTHLY': u'4-10',
            u'ALLOW_GROUPS': u'', u'EMPTY_PRE_POST_MIN_AGE': u'1800',
            u'EMPTY_PRE_POST_CLEANUP': u'yes', u'BACKGROUND_COMPARISON': u'yes',
            u'TIMELINE_LIMIT_HOURLY': u'4-10', u'ALLOW_USERS': u'',
            u'TIMELINE_LIMIT_WEEKLY': u'0', u'TIMELINE_CREATE': u'no',
            u'NUMBER_CLEANUP': u'yes', u'TIMELINE_CLEANUP': u'yes',
            u'SPACE_LIMIT': u'0.5', u'NUMBER_LIMIT': u'10',
            u'TIMELINE_MIN_AGE': u'1800', u'TIMELINE_LIMIT_DAILY': u'4-10',
            u'SYNC_ACL': u'no', u'QGROUP': u'1/0'
        }
    },
    'GETFILES': {
        '/root/.viminfo': {'status': ['modified']},
        '/tmp/foo': {'status': ['type changed', 'permission changed', 'owner changed']},
        '/tmp/foo2': {'status': ['created']},
        '/tmp/foo3': {'status': ['deleted']},
        '/var/log/snapper.log': {'status': ['modified']},
        '/var/cache/salt/minion/extmods/modules/snapper.py': {'status': ['modified']},
        '/var/cache/salt/minion/extmods/modules/snapper.pyc': {'status': ['modified']},
    },
    'DIFF': {
        '/tmp/foo': {
            'comment': 'text file changed',
            'diff': "--- /.snapshots/55/snapshot/tmp/foo\n"
                    "+++ /tmp/foo\n"
                    "@@ -1 +1 @@\n"
                    "-dummy text"
                    "+another foobar"
        },
        '/tmp/foo2': {
            'comment': 'text file created',
            'diff': "--- /.snapshots/55/snapshot/tmp/foo2\n"
                    "+++ /tmp/foo2\n"
                    "@@ -0,0 +1 @@\n"
                    "+another foobar",
        },
        '/tmp/foo26': {
            'comment': 'text file created',
            'diff': "--- /.snapshots/55/snapshot/tmp/foo2 \n"
                    "+++ /tmp/foo2 \n"
                    "@@ -1,0 +1,1 @@\n"
                    "+another foobar",
        },
        '/tmp/foo3': {
            'comment': 'binary file changed',
            'old_sha256_digest': 'e61f8b762d83f3b4aeb3689564b0ffbe54fa731a69a1e208dc9440ce0f69d19b',
            'new_sha256_digest': 'f18f971f1517449208a66589085ddd3723f7f6cefb56c141e3d97ae49e1d87fa',
        }
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SnapperTestCase(TestCase):
    def setUp(self):
        self.dbus_mock = MagicMock()
        self.DBusExceptionMock = MagicMock()  # pylint: disable=invalid-name
        self.dbus_mock.configure_mock(DBusException=self.DBusExceptionMock)
        snapper.dbus = self.dbus_mock
        snapper.snapper = MagicMock()

    def test__snapshot_to_data(self):
        data = snapper._snapshot_to_data(DBUS_RET['ListSnapshots'][0])  # pylint: disable=protected-access
        self.assertEqual(data['id'], 42)
        self.assertNotIn('pre', data)
        self.assertEqual(data['type'], 'pre')
        self.assertEqual(data['user'], 'root')
        self.assertEqual(data['timestamp'], 1457006571)
        self.assertEqual(data['description'], 'Some description')
        self.assertEqual(data['cleanup'], '')
        self.assertEqual(data['userdata']['userdata1'], 'userval1')

    @patch('salt.modules.snapper.snapper.ListSnapshots', MagicMock(return_value=DBUS_RET['ListSnapshots']))
    def test_list_snapshots(self):
        self.assertEqual(snapper.list_snapshots(), MODULE_RET["SNAPSHOTS"])

    @patch('salt.modules.snapper.snapper.GetSnapshot', MagicMock(return_value=DBUS_RET['ListSnapshots'][0]))
    def test_get_snapshot(self):
        self.assertEqual(snapper.get_snapshot(), MODULE_RET["SNAPSHOTS"][0])
        self.assertEqual(snapper.get_snapshot(number=42), MODULE_RET["SNAPSHOTS"][0])
        self.assertNotEqual(snapper.get_snapshot(number=42), MODULE_RET["SNAPSHOTS"][1])

    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    def test_list_configs(self):
        self.assertEqual(snapper.list_configs(), MODULE_RET["LISTCONFIGS"])

    @patch('salt.modules.snapper.snapper.GetConfig', MagicMock(return_value=DBUS_RET['ListConfigs'][0]))
    def test_get_config(self):
        self.assertEqual(snapper.get_config(), DBUS_RET["ListConfigs"][0])

    @patch('salt.modules.snapper.snapper.SetConfig', MagicMock())
    def test_set_config(self):
        opts = {'sync_acl': True, 'dummy': False, 'foobar': 1234}
        self.assertEqual(snapper.set_config(opts), True)

    def test_status_to_string(self):
        self.assertEqual(snapper.status_to_string(1), ["created"])
        self.assertEqual(snapper.status_to_string(2), ["deleted"])
        self.assertEqual(snapper.status_to_string(4), ["type changed"])
        self.assertEqual(snapper.status_to_string(8), ["modified"])
        self.assertEqual(snapper.status_to_string(16), ["permission changed"])
        self.assertListEqual(snapper.status_to_string(24), ["modified", "permission changed"])
        self.assertEqual(snapper.status_to_string(32), ["owner changed"])
        self.assertEqual(snapper.status_to_string(64), ["group changed"])
        self.assertListEqual(snapper.status_to_string(97), ["created", "owner changed", "group changed"])
        self.assertEqual(snapper.status_to_string(128), ["extended attributes changed"])
        self.assertEqual(snapper.status_to_string(256), ["ACL info changed"])

    @patch('salt.modules.snapper.snapper.CreateConfig', MagicMock())
    @patch('salt.modules.snapper.snapper.GetConfig', MagicMock(return_value=DBUS_RET['ListConfigs'][0]))
    def test_create_config(self):
        opts = {
            'name': 'testconfig',
            'subvolume': '/foo/bar/',
            'fstype': 'btrfs',
            'template': 'mytemplate',
            'extra_opts': {"NUMBER_CLEANUP": False},
        }
        with patch('salt.modules.snapper.set_config', MagicMock()) as set_config_mock:
            self.assertEqual(snapper.create_config(**opts), DBUS_RET['ListConfigs'][0])
            set_config_mock.assert_called_with("testconfig", **opts['extra_opts'])

        with patch('salt.modules.snapper.set_config', MagicMock()) as set_config_mock:
            del opts['extra_opts']
            self.assertEqual(snapper.create_config(**opts), DBUS_RET['ListConfigs'][0])
            assert not set_config_mock.called
            self.assertRaises(CommandExecutionError, snapper.create_config)

    @patch('salt.modules.snapper.snapper.CreateSingleSnapshot', MagicMock(return_value=1234))
    @patch('salt.modules.snapper.snapper.CreatePreSnapshot', MagicMock(return_value=1234))
    @patch('salt.modules.snapper.snapper.CreatePostSnapshot', MagicMock(return_value=1234))
    def test_create_snapshot(self):
        for snapshot_type in ['pre', 'post', 'single']:
            opts = {
                '__pub_jid': 20160607130930720112,
                'type': snapshot_type,
                'description': 'Test description',
                'cleanup_algorithm': 'number',
                'pre_number': 23,
            }
            self.assertEqual(snapper.create_snapshot(**opts), 1234)

    @patch('salt.modules.snapper.snapper.DeleteSnapshots', MagicMock())
    @patch('salt.modules.snapper.snapper.ListSnapshots', MagicMock(return_value=DBUS_RET['ListSnapshots']))
    def test_delete_snapshot_id_success(self):
        self.assertEqual(snapper.delete_snapshot(snapshots_ids=43), {"root": {"ids": [43], "status": "deleted"}})
        self.assertEqual(snapper.delete_snapshot(snapshots_ids=[42, 43]), {"root": {"ids": [42, 43], "status": "deleted"}})

    @patch('salt.modules.snapper.snapper.DeleteSnapshots', MagicMock())
    @patch('salt.modules.snapper.snapper.ListSnapshots', MagicMock(return_value=DBUS_RET['ListSnapshots']))
    def test_delete_snapshot_id_fail(self):
        self.assertRaises(CommandExecutionError, snapper.delete_snapshot)
        self.assertRaises(CommandExecutionError, snapper.delete_snapshot, snapshots_ids=1)
        self.assertRaises(CommandExecutionError, snapper.delete_snapshot, snapshots_ids=[1, 2])

    @patch('salt.modules.snapper.snapper.SetSnapshot', MagicMock())
    def test_modify_snapshot(self):
        _ret = {
            'userdata': {'userdata2': 'uservalue2'},
            'description': 'UPDATED DESCRIPTION', 'timestamp': 1457006571,
            'cleanup': 'number', 'user': 'root', 'type': 'pre', 'id': 42
        }
        _opts = {
            'config': 'root',
            'snapshot_id': 42,
            'cleanup': 'number',
            'description': 'UPDATED DESCRIPTION',
            'userdata': {'userdata2': 'uservalue2'},
        }
        with patch('salt.modules.snapper.get_snapshot', MagicMock(side_effect=[DBUS_RET['ListSnapshots'][0], _ret])):
            self.assertDictEqual(snapper.modify_snapshot(**_opts), _ret)

    @patch('salt.modules.snapper._get_last_snapshot', MagicMock(return_value={'id': 42}))
    def test__get_num_interval(self):
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=None, num_post=None), (42, 0))  # pylint: disable=protected-access
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=None, num_post=50), (42, 50))  # pylint: disable=protected-access
        self.assertEqual(snapper._get_num_interval(config=None, num_pre=42, num_post=50), (42, 50))  # pylint: disable=protected-access

    def test_run(self):
        patch_dict = {
            'snapper.create_snapshot': MagicMock(return_value=43),
            'test.ping': MagicMock(return_value=True),
        }
        with patch.dict(snapper.__salt__, patch_dict):
            self.assertEqual(snapper.run("test.ping"), True)
            self.assertRaises(CommandExecutionError, snapper.run, "unknown.func")

    @patch('salt.modules.snapper._get_num_interval', MagicMock(return_value=(42, 43)))
    @patch('salt.modules.snapper.snapper.GetComparison', MagicMock())
    @patch('salt.modules.snapper.snapper.GetFiles', MagicMock(return_value=DBUS_RET['GetFiles']))
    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    def test_status(self):
        if six.PY3:
            self.assertCountEqual(snapper.status(), MODULE_RET['GETFILES'])
            self.assertCountEqual(snapper.status(num_pre="42", num_post=43), MODULE_RET['GETFILES'])
            self.assertCountEqual(snapper.status(num_pre=42), MODULE_RET['GETFILES'])
            self.assertCountEqual(snapper.status(num_post=43), MODULE_RET['GETFILES'])
        else:
            self.assertItemsEqual(snapper.status(), MODULE_RET['GETFILES'])
            self.assertItemsEqual(snapper.status(num_pre="42", num_post=43), MODULE_RET['GETFILES'])
            self.assertItemsEqual(snapper.status(num_pre=42), MODULE_RET['GETFILES'])
            self.assertItemsEqual(snapper.status(num_post=43), MODULE_RET['GETFILES'])

    @patch('salt.modules.snapper.status', MagicMock(return_value=MODULE_RET['GETFILES']))
    def test_changed_files(self):
        self.assertEqual(snapper.changed_files(), MODULE_RET['GETFILES'].keys())

    @patch('salt.modules.snapper._get_num_interval', MagicMock(return_value=(42, 43)))
    @patch('salt.modules.snapper.status', MagicMock(return_value=MODULE_RET['GETFILES']))
    def test_undo(self):
        cmd_ret = 'create:0 modify:1 delete:0'
        with patch.dict(snapper.__salt__, {'cmd.run': MagicMock(return_value=cmd_ret)}):
            module_ret = {'create': '0', 'delete': '0', 'modify': '1'}
            self.assertEqual(snapper.undo(files=['/tmp/foo']), module_ret)

        cmd_ret = 'create:1 modify:1 delete:0'
        with patch.dict(snapper.__salt__, {'cmd.run': MagicMock(return_value=cmd_ret)}):
            module_ret = {'create': '1', 'delete': '0', 'modify': '1'}
            self.assertEqual(snapper.undo(files=['/tmp/foo', '/tmp/foo2']), module_ret)

        cmd_ret = 'create:1 modify:1 delete:1'
        with patch.dict(snapper.__salt__, {'cmd.run': MagicMock(return_value=cmd_ret)}):
            module_ret = {'create': '1', 'delete': '1', 'modify': '1'}
            self.assertEqual(snapper.undo(files=['/tmp/foo', '/tmp/foo2', '/tmp/foo3']), module_ret)

    @patch('salt.modules.snapper.list_snapshots', MagicMock(return_value=MODULE_RET['SNAPSHOTS']))
    def test__get_jid_snapshots(self):
        self.assertEqual(
            snapper._get_jid_snapshots("20160607130930720112"),  # pylint: disable=protected-access
            (MODULE_RET['SNAPSHOTS'][0]['id'], MODULE_RET['SNAPSHOTS'][1]['id'])
        )

    @patch('salt.modules.snapper._get_jid_snapshots', MagicMock(return_value=(42, 43)))
    @patch('salt.modules.snapper.undo', MagicMock(return_value='create:1 modify:1 delete:1'))
    def test_undo_jid(self):
        self.assertEqual(snapper.undo_jid(20160607130930720112), 'create:1 modify:1 delete:1')

    @patch('salt.modules.snapper._get_num_interval', MagicMock(return_value=(42, 43)))
    @patch('salt.modules.snapper.snapper.MountSnapshot', MagicMock(side_effect=["/.snapshots/55/snapshot", ""]))
    @patch('salt.modules.snapper.snapper.UmountSnapshot', MagicMock(return_value=""))
    @patch('os.path.isdir', MagicMock(return_value=False))
    @patch('salt.modules.snapper.changed_files', MagicMock(return_value=["/tmp/foo2"]))
    @patch('salt.modules.snapper._is_text_file', MagicMock(return_value=True))
    @patch('os.path.isfile', MagicMock(side_effect=[False, True]))
    @patch('salt.utils.fopen', mock_open(read_data=FILE_CONTENT["/tmp/foo2"]['post']))
    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    def test_diff_text_file(self):
        if sys.version_info < (2, 7):
            self.assertEqual(snapper.diff(), {"/tmp/foo2": MODULE_RET['DIFF']['/tmp/foo26']})
        else:
            self.assertEqual(snapper.diff(), {"/tmp/foo2": MODULE_RET['DIFF']['/tmp/foo2']})

    @patch('salt.modules.snapper._get_num_interval', MagicMock(return_value=(55, 0)))
    @patch('salt.modules.snapper.snapper.MountSnapshot', MagicMock(
        side_effect=["/.snapshots/55/snapshot", "", "/.snapshots/55/snapshot", ""]))
    @patch('salt.modules.snapper.snapper.UmountSnapshot', MagicMock(return_value=""))
    @patch('salt.modules.snapper.changed_files', MagicMock(return_value=["/tmp/foo", "/tmp/foo2"]))
    @patch('salt.modules.snapper._is_text_file', MagicMock(return_value=True))
    @patch('os.path.isfile', MagicMock(side_effect=[True, True, False, True]))
    @patch('os.path.isdir', MagicMock(return_value=False))
    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    @skipIf(sys.version_info < (2, 7), 'Python 2.7 required to compare diff properly')
    def test_diff_text_files(self):
        fopen_effect = [
            mock_open(read_data=FILE_CONTENT["/tmp/foo"]['pre']).return_value,
            mock_open(read_data=FILE_CONTENT["/tmp/foo"]['post']).return_value,
            mock_open(read_data=FILE_CONTENT["/tmp/foo2"]['post']).return_value,
        ]
        with patch('salt.utils.fopen') as fopen_mock:
            fopen_mock.side_effect = fopen_effect
            module_ret = {
                "/tmp/foo": MODULE_RET['DIFF']["/tmp/foo"],
                "/tmp/foo2": MODULE_RET['DIFF']["/tmp/foo2"],
            }
            self.assertEqual(snapper.diff(), module_ret)

    @patch('salt.modules.snapper._get_num_interval', MagicMock(return_value=(55, 0)))
    @patch('salt.modules.snapper.snapper.MountSnapshot', MagicMock(
        side_effect=["/.snapshots/55/snapshot", "", "/.snapshots/55/snapshot", ""]))
    @patch('salt.modules.snapper.snapper.UmountSnapshot', MagicMock(return_value=""))
    @patch('salt.modules.snapper.changed_files', MagicMock(return_value=["/tmp/foo3"]))
    @patch('salt.modules.snapper._is_text_file', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(side_effect=[True, True]))
    @patch('os.path.isdir', MagicMock(return_value=False))
    @patch.dict(snapper.__salt__, {
        'hashutil.sha256_digest': MagicMock(side_effect=[
            "e61f8b762d83f3b4aeb3689564b0ffbe54fa731a69a1e208dc9440ce0f69d19b",
            "f18f971f1517449208a66589085ddd3723f7f6cefb56c141e3d97ae49e1d87fa",
        ])
    })
    @patch('salt.modules.snapper.snapper.ListConfigs', MagicMock(return_value=DBUS_RET['ListConfigs']))
    def test_diff_binary_files(self):
        fopen_effect = [
            mock_open(read_data="dummy binary").return_value,
            mock_open(read_data="dummy binary").return_value,
        ]
        with patch('salt.utils.fopen') as fopen_mock:
            fopen_mock.side_effect = fopen_effect
            module_ret = {
                "/tmp/foo3": MODULE_RET['DIFF']["/tmp/foo3"],
            }
            self.assertEqual(snapper.diff(), module_ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SnapperTestCase, needs_daemon=False)
