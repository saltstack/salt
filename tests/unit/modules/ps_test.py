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
    STUB_DISK_PARTITION = psutil._compat.namedtuple('partition', 'device mountpoint fstype, opts')('/dev/disk0s2', '/',
                                                                                                   'hfs',
                                                                                                   'rw,local,rootfs,dovolfs,journaled,multilabel')
    STUB_DISK_USAGE = psutil._compat.namedtuple('usage', 'total used free percent')(1000, 500, 500, 50)
    STUB_NETWORK_IO = psutil._compat.namedtuple('iostat',
                                                'bytes_sent, bytes_recv, packets_sent, packets_recv, errin errout dropin dropout')(
        1000, 2000, 500, 600, 1, 2, 3, 4)
    STUB_DISK_IO = psutil._compat.namedtuple('iostat',
                                             'read_count, write_count, read_bytes, write_bytes, read_time, write_time')(
        1000, 2000, 500, 600, 2000, 3000)
    STUB_USER = psutil._compat.namedtuple('user', 'name, terminal, host, started')('bdobbs', 'ttys000', 'localhost',
                                                                                   0.0)
else:
    (STUB_CPU_TIMES,
     STUB_PHY_MEM_USAGE,
     STUB_DISK_PARTITION,
     STUB_DISK_USAGE,
     STUB_NETWORK_IO,
     STUB_DISK_IO,
     STUB_USER) = [None for val in range(7)]

STUB_PID_LIST = [0, 1, 2, 3]
MOCK_PROC = mocked_proc = MagicMock('psutil.Process')

try:
    import utmp

    HAS_UTMP = True
except ImportError:
    HAS_UTMP = False


@skipIf(not HAS_PSUTIL, "psutils are required for this test case")
class PsTestCase(TestCase):
    def setUp(self):
        MOCK_PROC.name = 'test_mock_proc'
        MOCK_PROC.pid = 9999999999

    @patch('psutil.get_pid_list', new=MagicMock(return_value=STUB_PID_LIST))
    def test_get_pid_list(self):
        self.assertListEqual(STUB_PID_LIST, ps.get_pid_list())

    @patch('psutil.Process')
    def test_kill_pid(self, send_signal_mock):
        ps.kill_pid(0, signal=999)
        self.assertEqual(send_signal_mock.call_args, call(0))

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

    @patch('psutil.phymem_usage', new=MagicMock(return_value=STUB_PHY_MEM_USAGE))
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

    @patch('psutil.disk_partitions', new=MagicMock(return_value=[STUB_DISK_PARTITION]))
    def test_disk_partitions(self):
        self.assertDictEqual(
            {'device': '/dev/disk0s2', 'mountpoint': '/', 'opts': 'rw,local,rootfs,dovolfs,journaled,multilabel',
             'fstype': 'hfs'},
            ps.disk_partitions()[0])

    @patch('psutil.disk_usage', new=MagicMock(return_value=STUB_DISK_USAGE))
    def test_disk_usage(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'percent': 50, 'free': 500}, ps.disk_usage('DUMMY_PATH'))

    @patch('psutil.disk_partitions', new=MagicMock(return_value=[STUB_DISK_PARTITION]))
    def test_disk_partition_usage(self):
        self.assertDictEqual(
            {'device': '/dev/disk0s2', 'mountpoint': '/', 'opts': 'rw,local,rootfs,dovolfs,journaled,multilabel',
             'fstype': 'hfs'},
            ps.disk_partitions()[0])

    ## Should only be tested in integration
    # def test_total_physical_memory(self):
    #     pass

    ## Should only be tested in integration
    # def test_num_cpus(self):
    #     pass

    ## Should only be tested in integration
    # def test_boot_time(self):
    #     pass
    @patch('psutil.network_io_counters', new=MagicMock(return_value=STUB_NETWORK_IO))
    def test_network_io_counters(self):
        self.assertDictEqual(
            {'packets_sent': 500, 'packets_recv': 600, 'bytes_recv': 2000, 'dropout': 4, 'bytes_sent': 1000,
             'errout': 2, 'errin': 1, 'dropin': 3}, ps.network_io_counters())

    @patch('psutil.disk_io_counters', new=MagicMock(return_value=STUB_DISK_IO))
    def test_disk_io_counters(self):
        self.assertDictEqual(
            {'read_time': 2000, 'write_bytes': 600, 'read_bytes': 500, 'write_time': 3000, 'read_count': 1000,
             'write_count': 2000}, ps.disk_io_counters())

    @patch('psutil.get_users', new=MagicMock(return_value=[STUB_USER]))
    def test_get_users(self):
        self.assertDictEqual({'terminal': 'ttys000', 'started': 0.0, 'host': 'localhost', 'name': 'bdobbs'},
                             ps.get_users()[0])

        ## This is commented out pending discussion on https://github.com/saltstack/salt/commit/2e5c3162ef87cca8a2c7b12ade7c7e1b32028f0a
        # @skipIf(not HAS_UTMP, "The utmp module must be installed to run test_get_users_utmp()")
        # @patch('psutil.get_users', new=MagicMock(return_value=None))  # This will force the function to use utmp
        # def test_get_users_utmp(self):
        #     pass
