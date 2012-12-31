'''
A salt interface to psutil, a system and process library.
See http://code.google.com/p/psutil.

:depends:   - psutil Python module
'''

# Import python libs
import sys
import time

# Import third party libs
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def __virtual__():
    if not HAS_PSUTIL:
        return False

    # The python 2.6 version of psutil lacks several functions
    # used in this salt module so instead of spaghetti  string
    # code to try to bring sanity to everything, disable it.
    if sys.version_info[0] == 2 and sys.version_info[1] < 7:
        return False
    return "ps"


def top(num_processes=5, interval=3):
    '''
    Return a list of top CPU consuming processes during the interval.
    num_processes = return the top N CPU consuming processes
    interval = the number of seconds to sample CPU usage over

    CLI Examples::

        salt '*' ps.top

        salt '*' ps.top 5 10
    '''
    result = []
    start_usage = {}
    for pid in psutil.get_pid_list():
        process = psutil.Process(pid)
        user, system = process.get_cpu_times()
        start_usage[process] = user + system
    time.sleep(interval)
    usage = set()
    for process, start in start_usage.items():
        user, system = process.get_cpu_times()
        now = user + system
        diff = now - start
        usage.add((diff, process))

    for idx, (diff, process) in enumerate(reversed(sorted(usage))):
        if num_processes and idx >= num_processes:
            break
        if len(process.cmdline) == 0:
            cmdline = [process.name]
        else:
            cmdline = process.cmdline
        info = {'cmd': cmdline,
                'pid': process.pid,
                'create_time': process.create_time}
        for key, value in process.get_cpu_times()._asdict().items():
            info['cpu.{0}'.format(key)] = value
        for key, value in process.get_memory_info()._asdict().items():
            info['mem.{0}'.format(key)] = value
        result.append(info)

    return result


def get_pid_list():
    '''
    Return a list of process ids (PIDs) for all running processes.

    CLI Example::

        salt '*' ps.get_pid_list
    '''
    return psutil.get_pid_list()


def cpu_percent(interval=0.1, per_cpu=False):
    '''
    Return the percent of time the CPU is busy.

    interval
        the number of seconds to sample CPU usage over
    per_cpu
        if True return an array of CPU percent busy for each CPU, otherwise
        aggregate all percents into one number

    CLI Example::

        salt '*' ps.cpu_percent
    '''
    if per_cpu:
        result = []
        for cpu_percent in psutil.cpu_percent(interval, True):
            result.append(cpu_percent)
    else:
        result = psutil.cpu_percent(interval)
    return result


def cpu_times(per_cpu=False):
    '''
    Return the percent of time the CPU spends in each state,
    e.g. user, system, idle, nice, iowait, irq, softirq.

    per_cpu
        if True return an array of percents for each CPU, otherwise aggregate
        all percents into one number

    CLI Example::

        salt '*' ps.cpu_times
    '''
    if per_cpu:
        result = []
        for cpu_times in psutil.cpu_times(True):
            result.append(dict(cpu_times._asdict()))
    else:
        result = dict(psutil.cpu_times(per_cpu)._asdict())
    return result


def physical_memory_usage():
    '''
    Return a dict that describes free and available physical memory.

    CLI Examples::

        salt '*' ps.physical_memory_usage
    '''
    return dict(psutil.phymem_usage()._asdict())


def virtual_memory_usage():
    '''
    Return a dict that describes free and available memory, both physical
    and virtual.

    CLI Example::

        salt '*' ps.virtual_memory_usage
    '''
    return dict(psutil.virtmem_usage()._asdict())


def cached_physical_memory():
    '''
    Return the amount cached memory.

    CLI Example::

        salt '*' ps.cached_physical_memory
    '''
    return psutil.cached_phymem()


def physical_memory_buffers():
    '''
    Return the amount of physical memory buffers.

    CLI Example::

        salt '*' ps.physical_memory_buffers
    '''
    return psutil.phymem_buffers()


def disk_partitions(all=False):
    '''
    Return a list of disk partitions and their device, mount point, and
    filesystem type.

    all
        if set to False, only return local, physical partitions (hard disk,
        USB, CD/DVD partitions).  If True, return all filesystems.

    CLI Example::

        salt '*' ps.disk_partitions
    '''
    result = []
    for partition in psutil.disk_partitions(all):
        result.append(dict(partition._asdict()))
    return result


def disk_usage(path):
    '''
    Given a path, return a dict listing the total available space as well as
    the free space, and used space.

    CLI Example::

        salt '*' ps.disk_usage /home
    '''
    return dict(psutil.disk_usage(path)._asdict())


def disk_partition_usage(all=False):
    '''
    Return a list of disk partitions plus the mount point, filesystem and usage
    statistics.

    CLI Example::

        salt '*' ps.disk_partition_usage
    '''
    result = disk_partitions(all)
    for partition in result:
        partition.update(disk_usage(partition['mountpoint']))
    return result


def total_physical_memory():
    '''
    Return the total number of bytes of physical memory.

    CLI Example::

        salt '*' ps.total_physical_memory
    '''
    return psutil.TOTAL_PHYMEM


def num_cpus():
    '''
    Return the number of CPUs.

    CLI Example::

        salt '*' ps.num_cpus
    '''
    return psutil.NUM_CPUS


def boot_time():
    '''
    Return the boot time in number of seconds since the epoch began.

    CLI Example::

        salt '*' ps.boot_time
    '''
    return psutil.BOOT_TIME


def network_io_counters():
    '''
    Return network I/O statisitics.

    CLI Example::

        salt '*' ps.network_io_counters
    '''
    return dict(psutil.network_io_counters()._asdict())


def disk_io_counters():
    '''
    Return disk I/O statisitics.

    CLI Example::

        salt '*' ps.disk_io_counters
    '''
    return dict(psutil.disk_io_counters()._asdict())
