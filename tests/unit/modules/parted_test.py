# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Dave Rawks (dave@pandora.com)`


    tests.unit.modules.parted_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.exceptions import CommandExecutionError
from salt.modules import parted


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PartedTestCase(TestCase):

    # Setup for each test function.

    def setUp(self):
        parted.__salt__ = {
            'cmd.run': MagicMock(),
            'cmd.run_stdout': MagicMock(),
        }
        self.cmdrun = parted.__salt__['cmd.run']
        self.cmdrun_stdout = parted.__salt__['cmd.run_stdout']
        self.maxDiff = None

    # Test __virtual__ function for module registration

    @patch('salt.utils.is_windows', lambda: True)
    def test_virtual_bails_on_windows(self):
        '''If running windows, __virtual__ shouldn't register module'''
        ret = parted.__virtual__()
        self.assertFalse(ret)

    @patch('salt.utils.which', lambda exe: not exe == "parted")
    def test_virtual_bails_without_parted(self):
        '''If parted not in PATH, __virtual__ shouldn't register module'''
        ret = parted.__virtual__()
        self.assertFalse(ret)

    @patch('salt.utils.which', lambda exe: not exe == "lsblk")
    def test_virtual_bails_without_lsblk(self):
        '''If lsblk not in PATH, __virtual__ shouldn't register module'''
        ret = parted.__virtual__()
        self.assertFalse(ret)

    @patch('salt.utils.which', lambda exe: not exe == "partprobe")
    def test_virtual_bails_without_partprobe(self):
        '''If partprobe not in PATH, __virtual__ shouldn't register module'''
        ret = parted.__virtual__()
        self.assertFalse(ret)

    @patch('salt.utils.is_windows', lambda: False)
    @patch('salt.utils.which',
           lambda exe: (
               exe == "parted"
               or
               exe == "lsblk"
               or
               exe == "partprobe"))
    def test_virtual(self):
        '''On expected platform with correct utils in PATH, register
        "partition" module'''
        ret = parted.__virtual__()
        expect = 'partition'
        self.assertEqual(ret, expect)

    # Test probe function

    def test_probe_wo_args(self):
        parted.probe()
        self.cmdrun.assert_called_once_with('partprobe -- ')

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_probe_w_single_arg(self):
        parted.probe("/dev/sda")
        self.cmdrun.assert_called_once_with('partprobe -- /dev/sda')

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_probe_w_multiple_args(self):
        parted.probe('/dev/sda', '/dev/sdb')
        self.cmdrun.assert_called_once_with('partprobe -- /dev/sda /dev/sdb')

    @staticmethod
    def check_kwargs_warn_until_devices(device_kwargs):
        def check_args(kwargs, version):
            assert kwargs == device_kwargs
            assert version == 'Beryllium'
        parted.salt.utils.kwargs_warn_until.side_effect = check_args

    @patch('salt.utils.kwargs_warn_until')
    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_probe_w_device_kwarg(self, *args, **kwargs):
        device_kwargs = {'device': '/dev/sda'}
        parted.probe(**device_kwargs)
        self.check_kwargs_warn_until_devices(device_kwargs)
        self.cmdrun.assert_called_once_with('partprobe -- /dev/sda')

    @patch('salt.utils.kwargs_warn_until')
    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_probe_w_device_kwarg_and_arg(self, *args, **kwargs):
        '''device arg is concatenated with positional args'''
        device_kwargs = {'device': '/dev/sda'}
        parted.probe("/dev/sdb", **device_kwargs)
        self.check_kwargs_warn_until_devices(device_kwargs)
        self.cmdrun.assert_called_once_with('partprobe -- /dev/sda /dev/sdb')

    @patch('salt.utils.kwargs_warn_until')
    def test_probe_w_extra_kwarg(self, *args, **kwargs):
        device_kwargs = {'foo': 'bar'}
        self.assertRaises(TypeError, parted.probe, **device_kwargs)
        self.check_kwargs_warn_until_devices(device_kwargs)
        self.assertFalse(self.cmdrun.called)

    # Test part_list function

    @patch('salt.modules.parted.list_')
    @patch('salt.utils.warn_until')
    def test_part_list(self, *args, **kwargs):
        '''Function should call new function and raise deprecation warning'''
        parted.part_list("foo", "bar")
        parted.list_.assert_called_once_with("foo", "bar")
        parted.salt.utils.warn_until.assert_called_once_with(
            'Beryllium',
            '''The \'part_list\' function has been deprecated in favor of
        \'list_\'. Please update your code and configs to reflect this.''')

    # Test _list function

    @staticmethod
    def parted_print_output(k):
        output = {
            "valid": (
                '''BYT;\n'''
                '''/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n'''
                '''1:17.4kB:150MB:150MB:ext3::boot;\n'''
                '''2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n'''
            ),
            "valid_legacy": (
                '''BYT;\n'''
                '''/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK;\n'''
                '''1:17.4kB:150MB:150MB:ext3::boot;\n'''
                '''2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n'''
            ),
            "empty": '',
            "bad_label_info": (
                '''BYT;\n'''
                '''badbadbadbad\n'''
                '''1:17.4kB:150MB:150MB:ext3::boot;\n'''
                '''2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n'''
            ),
            "bad_header": (
                '''badbadbadbad\n'''
                '''/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n'''
                '''1:17.4kB:150MB:150MB:ext3::boot;\n'''
                '''2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n'''
            ),
            "bad_partition": (
                '''BYT;\n'''
                '''/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n'''
                '''badbadbadbad\n'''
                '''2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n'''
            ),
        }
        return output[k]

    def test_list__without_device(self):
        self.assertRaises(TypeError, parted.list_)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__empty_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('empty')
        output = parted.list_('/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')
        expected = {'info': {}, 'partitions': {}}
        self.assertEqual(output, expected)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__valid_unit_empty_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('empty')
        output = parted.list_('/dev/sda', unit='s')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda unit s print')
        expected = {'info': {}, 'partitions': {}}
        self.assertEqual(output, expected)

    def test_list__invalid_unit(self):
        self.assertRaises(CommandExecutionError, parted.list_, '/dev/sda',
                          unit='badbadbad')
        self.assertFalse(self.cmdrun.called)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__bad_header(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('bad_header')
        self.assertRaises(CommandExecutionError, parted.list_, '/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__bad_label_info(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('bad_label_info')
        self.assertRaises(CommandExecutionError, parted.list_, '/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__bad_partition(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('bad_partition')
        self.assertRaises(CommandExecutionError, parted.list_, '/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__valid_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('valid')
        output = parted.list_('/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')
        expected = {
            'info': {
                'logical sector': '512',
                'physical sector': '512',
                'interface': 'scsi',
                'model': 'AMCC 9650SE-24M DISK',
                'disk': '/dev/sda',
                'disk flags': '',
                'partition table': 'gpt',
                'size': '4000GB'
            },
            'partitions': {
                '1': {
                    'end': '150MB',
                    'number': '1',
                    'start': '17.4kB',
                    'file system': '',
                    'flags': 'boot',
                    'type': 'ext3',
                    'size': '150MB'},
                '2': {
                    'end': '4000GB',
                    'number': '2',
                    'start': '3921GB',
                    'file system': '',
                    'flags': '',
                    'type': 'linux-swap(v1)',
                    'size': '79.3GB'
                }
            }
        }
        self.assertEqual(output, expected)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__valid_unit_valid_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('valid')
        output = parted.list_('/dev/sda', unit='s')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda unit s print')
        expected = {
            'info': {
                'logical sector': '512',
                'physical sector': '512',
                'interface': 'scsi',
                'model': 'AMCC 9650SE-24M DISK',
                'disk': '/dev/sda',
                'disk flags': '',
                'partition table': 'gpt',
                'size': '4000GB'
            },
            'partitions': {
                '1': {
                    'end': '150MB',
                    'number': '1',
                    'start': '17.4kB',
                    'file system': '',
                    'flags': 'boot',
                    'type': 'ext3',
                    'size': '150MB'},
                '2': {
                    'end': '4000GB',
                    'number': '2',
                    'start': '3921GB',
                    'file system': '',
                    'flags': '',
                    'type': 'linux-swap(v1)',
                    'size': '79.3GB'
                }
            }
        }
        self.assertEqual(output, expected)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__valid_legacy_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('valid_legacy')
        output = parted.list_('/dev/sda')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda print')
        expected = {
            'info': {
                'logical sector': '512',
                'physical sector': '512',
                'interface': 'scsi',
                'model': 'AMCC 9650SE-24M DISK',
                'disk': '/dev/sda',
                'partition table': 'gpt',
                'size': '4000GB'
            },
            'partitions': {
                '1': {
                    'end': '150MB',
                    'number': '1',
                    'start': '17.4kB',
                    'file system': '',
                    'flags': 'boot',
                    'type': 'ext3',
                    'size': '150MB'},
                '2': {
                    'end': '4000GB',
                    'number': '2',
                    'start': '3921GB',
                    'file system': '',
                    'flags': '',
                    'type': 'linux-swap(v1)',
                    'size': '79.3GB'
                }
            }
        }
        self.assertEqual(output, expected)

    @patch('salt.modules.parted._validate_device', MagicMock())
    def test_list__valid_unit_valid_legacy_cmd_output(self):
        self.cmdrun_stdout.return_value = self.parted_print_output('valid_legacy')
        output = parted.list_('/dev/sda', unit='s')
        self.cmdrun_stdout.assert_called_once_with('parted -m -s /dev/sda unit s print')
        expected = {
            'info': {
                'logical sector': '512',
                'physical sector': '512',
                'interface': 'scsi',
                'model': 'AMCC 9650SE-24M DISK',
                'disk': '/dev/sda',
                'partition table': 'gpt',
                'size': '4000GB'
            },
            'partitions': {
                '1': {
                    'end': '150MB',
                    'number': '1',
                    'start': '17.4kB',
                    'file system': '',
                    'flags': 'boot',
                    'type': 'ext3',
                    'size': '150MB'},
                '2': {
                    'end': '4000GB',
                    'number': '2',
                    'start': '3921GB',
                    'file system': '',
                    'flags': '',
                    'type': 'linux-swap(v1)',
                    'size': '79.3GB'
                }
            }
        }
        self.assertEqual(output, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PartedTestCase, needs_daemon=False)
