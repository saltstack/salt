# -*- coding: utf-8 -*-
'''
A salt interface to psutil, a system and process library.
See http://code.google.com/p/psutil.

:depends:   - psutil Python module, version 0.3.0 or later
            - python-utmp package (optional)
'''

# Import python libs
import time
import datetime

# Import salt libs
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import third party libs
try:
    import psutil

    HAS_PSUTIL = True
    PSUTIL2 = psutil.version_info >= (2, 0)
except ImportError:
    HAS_PSUTIL = False


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
        return True
    return False


def _get_proc_cmdline(proc):
    '''
    Returns the cmdline of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    return proc.cmdline() if PSUTIL2 else proc.cmdline


def _get_proc_create_time(proc):
    '''
    Returns the create_time of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    return proc.create_time() if PSUTIL2 else proc.create_time


def _get_proc_name(proc):
    '''
    Returns the name of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    ret = []
    try:
        ret = proc.name() if PSUTIL2 else proc.name
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return ret


def _get_proc_status(proc):
    '''
    Returns the status of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    return proc.status() if PSUTIL2 else proc.status


def _get_proc_username(proc):
    '''
    Returns the username of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    return proc.username() if PSUTIL2 else proc.username


def _get_proc_pid(proc):
    '''
    Returns the pid of a Process instance.

    It's backward compatible with < 2.0 versions of psutil.
    '''
    return proc.pid


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
        try:
            user, system = process.get_cpu_times()
        except psutil.NoSuchProcess:
            continue
        now = user + system
        diff = now - start
        usage.add((diff, process))

    for idx, (diff, process) in enumerate(reversed(sorted(usage))):
        if num_processes and idx >= num_processes:
            break
        if len(_get_proc_cmdline(process)) == 0:
            cmdline = [_get_proc_name(process)]
        else:
            cmdline = _get_proc_cmdline(process)
        info = {'cmd': cmdline,
                'user': _get_proc_username(process),
                'status': _get_proc_status(process),
                'pid': _get_proc_pid(process),
                'create_time': _get_proc_create_time(process),
                'cpu': {},
                'mem': {},
        }
        for key, value in process.get_cpu_times()._asdict().items():
            info['cpu'][key] = value
        for key, value in process.get_memory_info()._asdict().items():
            info['mem'][key] = value
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
    Kill a process by PID.

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

        salt 'www.*' ps.pkill httpd signal=1

    Send SIGKILL to all bash processes owned by user 'tom':

    .. code-block:: bash

        salt '*' ps.pkill bash signal=9 user=tom
    '''

    killed = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(_get_proc_cmdline(proc)) if full \
            else pattern in _get_proc_name(proc)
        user_match = True if user is None else user == _get_proc_username(proc)
        if name_match and user_match:
            try:
                proc.send_signal(signal)
                killed.append(_get_proc_pid(proc))
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

        salt 'www.*' ps.pgrep httpd

    Find all bash processes owned by user 'tom':

    .. code-block:: bash

        salt '*' ps.pgrep bash user=tom
    '''

    procs = []
    for proc in psutil.process_iter():
        name_match = pattern in ' '.join(_get_proc_cmdline(proc)) if full \
            else pattern in _get_proc_name(proc)
        user_match = True if user is None else user == _get_proc_username(proc)
        if name_match and user_match:
            procs.append(_get_proc_pid(proc))
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


def virtual_memory():
    '''
    .. versionadded:: 2014.7.0

    Return a dict that describes statistics about system memory usage.

    .. note::

        This function is only available in psutil version 0.6.0 and above.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.virtual_memory
    '''
    if psutil.version_info < (0, 6, 0):
        msg = 'virtual_memory is only available in psutil 0.6.0 or greater'
        raise CommandExecutionError(msg)
    return dict(psutil.virtual_memory()._asdict())


def swap_memory():
    '''
    .. versionadded:: 2014.7.0

    Return a dict that describes swap memory statistics.

    .. note::

        This function is only available in psutil version 0.6.0 and above.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.swap_memory
    '''
    if psutil.version_info < (0, 6, 0):
        msg = 'swap_memory is only available in psutil 0.6.0 or greater'
        raise CommandExecutionError(msg)
    return dict(psutil.swap_memory()._asdict())


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
    try:
        return psutil.virtual_memory().total
    except AttributeError:
        # TOTAL_PHYMEM is deprecated but with older psutil versions this is
        # needed as a fallback.
        return psutil.TOTAL_PHYMEM


def num_cpus():
    '''
    Return the number of CPUs.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.num_cpus
    '''
    try:
        return psutil.cpu_count()
    except AttributeError:
        # NUM_CPUS is deprecated but with older psutil versions this is needed
        # as a fallback.
        return psutil.NUM_CPUS


def boot_time(time_format=None):
    '''
    Return the boot time in number of seconds since the epoch began.

    CLI Example:

    time_format
        Optionally specify a `strftime`_ format string. Use
        ``time_format='%c'`` to get a nicely-formatted locale specific date and
        time (i.e. ``Fri May  2 19:08:32 2014``).

        .. _strftime: https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior

        .. versionadded:: 2014.1.4

    .. code-block:: bash

        salt '*' ps.boot_time
    '''
    try:
        b_time = int(psutil.boot_time())
    except AttributeError:
        # get_boot_time() has been removed in newer psutil versions, and has
        # been replaced by boot_time() which provides the same information.
        b_time = int(psutil.get_boot_time())
    if time_format:
        # Load epoch timestamp as a datetime.datetime object
        b_time = datetime.datetime.fromtimestamp(b_time)
        try:
            return b_time.strftime(time_format)
        except TypeError as exc:
            raise SaltInvocationError('Invalid format string: {0}'.format(exc))
    return b_time


def network_io_counters(interface=None):
    '''
    Return network I/O statistics.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.network_io_counters

        salt '*' ps.network_io_counters interface=eth0
    '''
    if not interface:
        return dict(psutil.network_io_counters()._asdict())
    else:
        stats = psutil.network_io_counters(pernic=True)
        if interface in stats:
            return dict(stats[interface]._asdict())
        else:
            return False


def disk_io_counters(device=None):
    '''
    Return disk I/O statistics.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.disk_io_counters

        salt '*' ps.disk_io_counters device=sda1
    '''
    if not device:
        return dict(psutil.disk_io_counters()._asdict())
    else:
        stats = psutil.disk_io_counters(perdisk=True)
        if device in stats:
            return dict(stats[device]._asdict())
        else:
            return False


def get_users():
    '''
    Return logged-in users.

    CLI Example:

    .. code-block:: bash

        salt '*' ps.get_users
    '''
    try:
        recs = psutil.get_users()
        return [dict(x._asdict()) for x in recs]
    except AttributeError:
        # get_users is only present in psutil > v0.5.0
        # try utmp
        try:
            import utmp

            result = []
            while True:
                rec = utmp.utmpaccess.getutent()
                if rec is None:
                    return result
                elif rec[0] == 7:
                    started = rec[8]
                    if isinstance(started, tuple):
                        started = started[0]
                    result.append({'name': rec[4], 'terminal': rec[2],
                                   'started': started, 'host': rec[5]})
        except ImportError:
            return False
