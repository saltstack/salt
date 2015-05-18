# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, call, Mock

ensure_in_syspath('../../')

from salt.modules import ps

HAS_PSUTIL = ps.__virtual__()
HAS_PSUTIL_VERSION = False

# Import 3rd-party libs
# pylint: disable=import-error,unused-import
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
if HAS_PSUTIL:
    import salt.utils.psutil_compat as psutil
    from collections import namedtuple

    PSUTIL2 = psutil.version_info >= (2, 0)

    STUB_CPU_TIMES = namedtuple('cputimes', 'user nice system idle')(1, 2, 3, 4)
    STUB_VIRT_MEM = namedtuple('vmem', 'total available percent used free')(1000, 500, 50, 500, 500)
    STUB_SWAP_MEM = namedtuple('swap', 'total used free percent sin sout')(1000, 500, 500, 50, 0, 0)
    STUB_PHY_MEM_USAGE = namedtuple('usage', 'total used free percent')(1000, 500, 500, 50)
    STUB_DISK_PARTITION = namedtuple('partition', 'device mountpoint fstype, opts')('/dev/disk0s2', '/',
                                                                                    'hfs',
                                                                                    'rw,local,rootfs,dovolfs,journaled,multilabel')
    STUB_DISK_USAGE = namedtuple('usage', 'total used free percent')(1000, 500, 500, 50)
    STUB_NETWORK_IO = namedtuple('iostat',
                                 'bytes_sent, bytes_recv, packets_sent, packets_recv, errin errout dropin dropout')(
        1000, 2000, 500, 600, 1, 2, 3, 4)
    STUB_DISK_IO = namedtuple('iostat',
                              'read_count, write_count, read_bytes, write_bytes, read_time, write_time')(
        1000, 2000, 500, 600, 2000, 3000)
    STUB_USER = namedtuple('user', 'name, terminal, host, started')('bdobbs', 'ttys000', 'localhost', 0.0)
    if psutil.version_info >= (0, 6, 0):
        HAS_PSUTIL_VERSION = True

else:
    (STUB_CPU_TIMES,
     STUB_VIRT_MEM,
     STUB_SWAP_MEM,
     STUB_PHY_MEM_USAGE,
     STUB_DISK_PARTITION,
     STUB_DISK_USAGE,
     STUB_NETWORK_IO,
     STUB_DISK_IO,
     STUB_USER) = [None for val in range(9)]

STUB_PID_LIST = [0, 1, 2, 3]
MOCK_PROC = mocked_proc = MagicMock('salt.utils.psutil_compat.Process')

try:
    import utmp  # pylint: disable=W0611

    HAS_UTMP = True
except ImportError:
    HAS_UTMP = False
# pylint: enable=import-error,unused-import


def _get_proc_name(proc):
    return proc.name() if PSUTIL2 else proc.name


def _get_proc_pid(proc):
    return proc.pid


@skipIf(not HAS_PSUTIL, "psutils are required for this test case")
class PsTestCase(TestCase):
    def setUp(self):
        if PSUTIL2:
            MOCK_PROC.name = Mock(return_value="test_mock_proc")
            MOCK_PROC.pid = Mock(return_value=9999999999)
        else:
            MOCK_PROC.name = 'test_mock_proc'
            MOCK_PROC.pid = 9999999999

    @patch('salt.utils.psutil_compat.pids', new=MagicMock(return_value=STUB_PID_LIST))
    def test_get_pid_list(self):
        self.assertListEqual(STUB_PID_LIST, ps.get_pid_list())

    @patch('salt.utils.psutil_compat.Process')
    def test_kill_pid(self, send_signal_mock):
        ps.kill_pid(0, signal=999)
        self.assertEqual(send_signal_mock.call_args, call(0))

    @patch('salt.utils.psutil_compat.Process.send_signal')
    @patch('salt.utils.psutil_compat.process_iter', new=MagicMock(return_value=[MOCK_PROC]))
    def test_pkill(self, send_signal_mock):
        mocked_proc.send_signal = MagicMock()
        test_signal = 1234
        ps.pkill(_get_proc_name(mocked_proc), signal=test_signal)
        self.assertEqual(mocked_proc.send_signal.call_args, call(test_signal))

    @patch('salt.utils.psutil_compat.process_iter', new=MagicMock(return_value=[MOCK_PROC]))
    def test_pgrep(self):
        self.assertIn(_get_proc_pid(MOCK_PROC), ps.pgrep(_get_proc_name(MOCK_PROC)))

    @patch('salt.utils.psutil_compat.cpu_percent', new=MagicMock(return_value=1))
    def test_cpu_percent(self):
        self.assertEqual(ps.cpu_percent(), 1)

    @patch('salt.utils.psutil_compat.cpu_times', new=MagicMock(return_value=STUB_CPU_TIMES))
    def test_cpu_times(self):
        self.assertDictEqual({'idle': 4, 'nice': 2, 'system': 3, 'user': 1}, ps.cpu_times())

    @skipIf(HAS_PSUTIL_VERSION is False, 'psutil 0.6.0 or greater is required for this test')
    @patch('salt.utils.psutil_compat.virtual_memory', new=MagicMock(return_value=STUB_VIRT_MEM))
    def test_virtual_memory(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'available': 500, 'percent': 50, 'free': 500},
                             ps.virtual_memory())

    @skipIf(HAS_PSUTIL_VERSION is False, 'psutil 0.6.0 or greater is required for this test')
    @patch('salt.utils.psutil_compat.swap_memory', new=MagicMock(return_value=STUB_SWAP_MEM))
    def test_swap_memory(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'percent': 50, 'free': 500, 'sin': 0, 'sout': 0},
                             ps.swap_memory())

    @patch('salt.utils.psutil_compat.disk_partitions', new=MagicMock(return_value=[STUB_DISK_PARTITION]))
    def test_disk_partitions(self):
        self.assertDictEqual(
            {'device': '/dev/disk0s2', 'mountpoint': '/', 'opts': 'rw,local,rootfs,dovolfs,journaled,multilabel',
             'fstype': 'hfs'},
            ps.disk_partitions()[0])

    @patch('salt.utils.psutil_compat.disk_usage', new=MagicMock(return_value=STUB_DISK_USAGE))
    def test_disk_usage(self):
        self.assertDictEqual({'used': 500, 'total': 1000, 'percent': 50, 'free': 500}, ps.disk_usage('DUMMY_PATH'))

    @patch('salt.utils.psutil_compat.disk_partitions', new=MagicMock(return_value=[STUB_DISK_PARTITION]))
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
    @patch('salt.utils.psutil_compat.net_io_counters', new=MagicMock(return_value=STUB_NETWORK_IO))
    def test_network_io_counters(self):
        self.assertDictEqual(
            {'packets_sent': 500, 'packets_recv': 600, 'bytes_recv': 2000, 'dropout': 4, 'bytes_sent': 1000,
             'errout': 2, 'errin': 1, 'dropin': 3}, ps.network_io_counters())

    @patch('salt.utils.psutil_compat.disk_io_counters', new=MagicMock(return_value=STUB_DISK_IO))
    def test_disk_io_counters(self):
        self.assertDictEqual(
            {'read_time': 2000, 'write_bytes': 600, 'read_bytes': 500, 'write_time': 3000, 'read_count': 1000,
             'write_count': 2000}, ps.disk_io_counters())

    @patch('salt.utils.psutil_compat.users', new=MagicMock(return_value=[STUB_USER]))
    def test_get_users(self):
        self.assertDictEqual({'terminal': 'ttys000', 'started': 0.0, 'host': 'localhost', 'name': 'bdobbs'},
                             ps.get_users()[0])

        ## This is commented out pending discussion on https://github.com/saltstack/salt/commit/2e5c3162ef87cca8a2c7b12ade7c7e1b32028f0a
        # @skipIf(not HAS_UTMP, "The utmp module must be installed to run test_get_users_utmp()")
        # @patch('salt.utils.psutil_compat.get_users', new=MagicMock(return_value=None))  # This will force the function to use utmp
        # def test_get_users_utmp(self):
        #     pass


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(PsTestCase, needs_daemon=False)
