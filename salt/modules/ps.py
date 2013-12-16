# -*- coding: utf-8 -*-
'''
A salt interface to psutil, a system and process library.
See http://code.google.com/p/psutil.

:depends:   - psutil Python module, version 0.3.0 or later
'''

# Import python libs
import time

# Import third party libs
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Define the module's virtual name
__virtualname__ = 'ps'


def __virtual__():
    if not HAS_PSUTIL:
        return False

    # Functions and attributes used in this execution module seem to have been
    # added as of psutil 0.3.0, from an inspection of the source code. Only
    # make this module available if the version of psutil is >= 0.3.0. Note
    # that this may need to be tweaked if we find post-0.3.0 versions which
    # also have problems running the functions in this execution module, but
    # most distributions have already moved to later versions (for example,
    # as of Dec. 2013 EPEL is on 0.6.1, Debian 7 is on 0.5.1, etc.).
    if psutil.version_info >= (0, 3, 0):
        return __virtualname__
    return False


def top(num_processes=5, interval=3):
    '''
    Return a list of top CPU consuming processes during the interval.
    num_processes = return the top N CPU consuming processes
    interval = the number of seconds to sample CPU usage over

    CLI Examples:

    .. code-block:: bash

        salt '*' ps.top

        salt '*' ps.top 5 10
    '''
    result = []
    start_usage = {}
    for pid in psutil.get_pid_list():
        try:
            process = psutil.Process(pid)
            user, system = process.get_cpu_times()
        except psutil.NoSuchProcess:
            continue
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

    CLI Example:

    .. code-block:: bash

        salt '*' ps.get_pid_list
    '''
    return psutil.get_pid_list()


def kill_pid(pid, signal=15):
    '''
    Kill a proccess by PID.

    .. code-block:: bash

        salt 'minion' ps.kill_pid pid [signal=signal_number]

    pid
        PID of process to kill.

    signal
        Signal to send to the process. See manpage entry for kill
        for possible values. Default: 15 (SIGTERM).

    **Example:**

    Send SIGKILL to process with PID 2000:

    .. code-block:: bash

        salt 'minion' ps.kill_pid 2000 signal=9
    '''
    try:
        psutil.Process(pid).send_signal(signal)
        return True
    except psutil.NoSuchProcess:
        return False


def pkill(pattern, user=None, signal=15, full=False):
    '''
    Kill processes matching a pattern.

    .. code-block:: bash

        salt '*' ps.pkill pattern [user=username] [signal=signal_number] \\
                [full=(true|false)]

    pattern
        Pattern to search for in the process list.

    user
        Limit matches to the given username. Default: All users.

    signal
        Signal to send to the process(es). See manpage entry for kill
        for possible values. Default: 15 (SIGTERM).

    full
        A boolean value indicating whether only the name of the command or
        the full command line should be matched against the pattern.

    **Examples:**

    Send SIGHUP to all httpd processes on all 'www' minions:

    .. code-block:: bash

        salt 'www.*' httpd signal=1

    Send SIGKILL to all bash processes owned by user 'tom':

    .. code-block:: bash

        salt '*' bash signal=9 user=tom
    '''

    killed = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(proc.cmdline) if full \
            else pattern in proc.name
        user_match = True if user is None else user == proc.username
        if name_match and user_match:
            try:
                proc.send_signal(signal)
                killed.append(proc.pid)
            except psutil.NoSuchProcess:
                pass
    if not killed:
        return None
    else:
        return {'killed': killed}


def pgrep(pattern, user=None, full=False):
    '''
    Return the pids for processes matching a pattern.

    If full is true, the full command line is searched for a match,
    otherwise only the name of the command is searched.

    .. code-block:: bash

        salt '*' ps.pgrep pattern [user=username] [full=(true|false)]

    pattern
        Pattern to search for in the process list.

    user
        Limit matches to the given username. Default: All users.

    full
        A boolean value indicating whether only the name of the command or
        the full command line should be matched against the pattern.

    **Examples:**

    Find all httpd processes on all 'www' minions:

    .. code-block:: bash

        salt 'www.*' httpd

    Find all bash processes owned by user 'tom':

    .. code-block:: bash

        salt '*' bash user=tom
    '''

    procs = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(proc.cmdline) if full \
            else pattern in proc.name
        user_match = True if user is None else user == proc.username
        if name_match and user_match:
            procs.append(proc.pid)
    return procs or None


def cpu_percent(interval=0.1, per_cpu=False):
    '''
    Return the percent of time the CPU is busy.

    interval
        the number of seconds to sample CPU usage over
    per_cpu
        if True return an array of CPU percent busy for each CPU, otherwise
        aggregate all percents into one number

    CLI Example:

    .. code-block:: bash

        salt '*' ps.cpu_percent
    '''
    if per_cpu:
        result = list(psutil.cpu_percent(interval, True))
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

    CLI Example:

    .. code-block:: bash

        salt '*' ps.cpu_times
    '''
    if per_cpu:
        result = [dict(times._asdict()) for times in psutil.cpu_times(True)]
    else:
        result = dict(psutil.cpu_times(per_cpu)._asdict())
    return result


def physical_memory_usage():
    '''
    Return a dict that describes free and available physical memory.

    CLI Examples:

    .. code-block:: bash

        salt '*' ps.physical_memory_usage
    '''
    return dict(psutil.phymem_usage()._asdict())


def virtual_memory_usage():
    '''
    Return a dict that describes free and available memory, both physical
    and virtual.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.virtual_memory_usage
    '''
    return dict(psutil.virtmem_usage()._asdict())


def cached_physical_memory():
    '''
    Return the amount cached memory.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.cached_physical_memory
    '''
    return psutil.cached_phymem()


def physical_memory_buffers():
    '''
    Return the amount of physical memory buffers.

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' ps.disk_partitions
    '''
    result = [dict(partition._asdict()) for partition in
              psutil.disk_partitions(all)]
    return result


def disk_usage(path):
    '''
    Given a path, return a dict listing the total available space as well as
    the free space, and used space.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.disk_usage /home
    '''
    return dict(psutil.disk_usage(path)._asdict())


def disk_partition_usage(all=False):
    '''
    Return a list of disk partitions plus the mount point, filesystem and usage
    statistics.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.disk_partition_usage
    '''
    result = disk_partitions(all)
    for partition in result:
        partition.update(disk_usage(partition['mountpoint']))
    return result


def total_physical_memory():
    '''
    Return the total number of bytes of physical memory.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.total_physical_memory
    '''
    return psutil.TOTAL_PHYMEM


def num_cpus():
    '''
    Return the number of CPUs.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.num_cpus
    '''
    return psutil.NUM_CPUS


def boot_time():
    '''
    Return the boot time in number of seconds since the epoch began.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.boot_time
    '''
    return psutil.BOOT_TIME


def network_io_counters():
    '''
    Return network I/O statisitics.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.network_io_counters
    '''
    return dict(psutil.network_io_counters()._asdict())


def disk_io_counters():
    '''
    Return disk I/O statisitics.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.disk_io_counters
    '''
    return dict(psutil.disk_io_counters()._asdict())
