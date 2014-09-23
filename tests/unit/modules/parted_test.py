# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Dave Rawks (dave@pandora.com)`


    tests.unit.modules.parted_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import parted

parted.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PartedTestCase(TestCase):

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
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            parted.probe()
        run.called_once_with(
            ['partprobe'], python_shell=False)

    def test_probe_w_single_arg(self):
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            parted.probe("/dev/sda")
        run.called_once_with(
            ['partprobe', '/dev/sda'], python_shell=False)

    def test_probe_w_multiple_args(self):
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            parted.probe('/dev/sda', '/dev/sdb')
        run.called_once_with(
            ['partprobe', '/dev/sda', '/dev/sdb'], python_shell=False)

    @patch('salt.utils.kwargs_warn_until')
    def test_probe_w_device_kwarg(self, *args, **kwargs):
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            parted.probe(device="/dev/sda")
        parted.salt.utils.kwargs_warn_until.called_once_with({'device': '/dev/sda'})
        run.called_once_with(['partprobe', '/dev/sda'], python_shell=False)

    @patch('salt.utils.kwargs_warn_until')
    def test_probe_w_device_kwarg_and_arg(self, *args, **kwargs):
        '''device arg is concatanated with possitional args'''
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            parted.probe("/dev/sdb", device="/dev/sda")
        parted.salt.utils.kwargs_warn_until.called_once_with({'device': '/dev/sda'})
        run.called_once_with(
            ['partprobe', '/dev/sda', '/dev/sdb'], python_shell=False)

    @patch('salt.utils.kwargs_warn_until')
    def test_probe_w_extra_kwarg(self, *args, **kwargs):
        run = MagicMock()
        with patch.dict(parted.__salt__, {'cmd.run': run}):
            self.assertRaises(TypeError, parted.probe, foo="bar")
        parted.salt.utils.kwargs_warn_until.called_once_with({'device': '/dev/sda'})
        self.assertFalse(run.called)

    # Test part_list function

    @patch('salt.modules.parted.list_')
    @patch('salt.utils.warn_until')
    def test_part_list(self, *args, **kwargs):
        '''Function should call new function and raise deprecation warning'''
        parted.part_list("foo", "bar")
        parted.list_.called_once_with("foo", "bar")
        parted.salt.utils.warn_until.called_once_with(
            'Beryllium',
            '''The \'part_list\' function has been deprecated in favor of
            \'list\'. Please update your code and configs to reflect
            this.''')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PartedTestCase, needs_daemon=False)
