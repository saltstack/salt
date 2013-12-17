# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, call

ensure_in_syspath('../../')

from salt.modules import ps

HAS_PSUTIL = ps.__virtual__()

if HAS_PSUTIL:
    import psutil
    STUB_CPU_TIMES = psutil._compat.namedtuple('cputimes', 'user nice system idle')(1, 2, 3, 4)
    STUB_PHY_MEM_USAGE = psutil._compat.namedtuple('usage', 'total used free percent')(1000, 500, 500, 50)
    STUB_DISK_PARTITION = psutil._compat.namedtuple('partition', 'device mountpoint fstype, opts')('/dev/disk0s2', '/', 'hfs', 'rw,local,rootfs,dovolfs,journaled,multilabel')
STUB_PID_LIST = [0, 1, 2, 3]
MOCK_PROC = mocked_proc = MagicMock('psutil.Process')


@skipIf(not HAS_PSUTIL, "psutils are required for this test case")
class PsTestCase(TestCase):

    def setUp(self):
        MOCK_PROC.name = 'test_mock_proc'
        MOCK_PROC.pid = 9999999999

    @patch('psutil.get_pid_list', new=MagicMock(return_value=STUB_PID_LIST))
    def test_get_pid_list(self):
        self.assertListEqual(STUB_PID_LIST, ps.get_pid_list())

    @patch('psutil.Process.send_signal')
    def test_kill_pid(self, send_signal_mock):
        ps.kill_pid(0, signal=999)
        self.assertEqual(send_signal_mock.call_args, call(999))

    @patch('psutil.Process.send_signal')
    @patch('psutil.process_iter', new=MagicMock(return_value=[MOCK_PROC]))
    def test_pkill(self, send_signal_mock):
        mocked_proc.send_signal = MagicMock()
        test_signal = 1234
        ps.pkill(mocked_proc.name, signal=test_signal)
        self.assertEqual(mocked_proc.send_signal.call_args, call(test_signal))

    @patch('psutil.process_iter', new=MagicMock(return_value=[MOCK_PROC]))
    def test_pgrep(self):
        self.assertIn(MOCK_PROC.pid, ps.pgrep(MOCK_PROC.name))

    @patch('psutil.cpu_percent', new=MagicMock(return_value=1))
    def test_cpu_percent(self):
        self.assertEqual(ps.cpu_percent(), 1)

    @patch('psutil.cpu_times', new=MagicMock(return_value=STUB_CPU_TIMES))
    def test_cpu_times(self):
        self.assertDictEqual({'idle': 4, 'nice': 2, 'system': 3, 'user': 1}, ps.cpu_times())

    @patch('psutil.phymem_usage',  new=MagicMock(return_value=STUB_PHY_MEM_USAGE))
    def test_physical_memory_usage(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'percent': 50, 'free': 500}, ps.physical_memory_usage())

    @patch('psutil.virtmem_usage', new=MagicMock(return_value=STUB_PHY_MEM_USAGE))
    def test_virtual_memory_usage(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'percent': 50, 'free': 500}, ps.virtual_memory_usage())

    # ps.cached_physical_memory is deprecated! See #9301
    # def test_cached_physical_memory(self):
    #    pass

    #ps.physical_memory_buffers is deprecated! See #9301
    # def test_physical_memory_buffers(self):
    #     pass
