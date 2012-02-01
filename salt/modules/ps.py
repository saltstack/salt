'''
A salt interface to psutil, a system and process library.
See http://code.google.com/p/psutil.
'''

import time
import psutil


def top(num_processes=5, interval=3):
    '''
    Return a list of top CPU consuming processes during the interval.
    num_processes = return the top N CPU consuming processes
    interval = the number of seconds to sample CPU usage over
    '''
    result = []
    start_usage = {}
    for pid in psutil.get_pid_list():
        p = psutil.Process(pid)
        user, sys = p.get_cpu_times()
        start_usage[p] = user + sys
    time.sleep(interval)
    usage = set()
    for p, start in start_usage.iteritems():
        user, sys = p.get_cpu_times()
        now = user + sys
        diff = now - start
        usage.add((diff, p))

    for i, (diff, p) in enumerate(reversed(sorted(usage))):
        if num_processes and i >= num_processes:
            break
        if len(p.cmdline) == 0:
            cmdline = [p.name]
        else:
            cmdline = p.cmdline
        info = {'cmd': cmdline,
                'pid': p.pid,
                'create_time': p.create_time}
        for k, v in p.get_cpu_times()._asdict().iteritems():
            info['cpu.' + k] = v
        for k, v in p.get_memory_info()._asdict().iteritems():
            info['mem.' + k] = v
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

        salt '*' virtual_memory_usage
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
