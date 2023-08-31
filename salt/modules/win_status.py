"""
Module for returning various status data about a minion.
These data can be useful for compiling into stats later,
or for problem solving if your minion is having problems.

.. versionadded:: 0.12.0

:depends:  - wmi
"""
import ctypes
import datetime
import logging
import subprocess

import salt.utils.event
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.win_pdh
from salt.modules.status import ping_master, time_
from salt.utils.functools import namespaced_function
from salt.utils.network import host_to_ips as _host_to_ips

log = logging.getLogger(__name__)

try:
    if salt.utils.platform.is_windows():
        import wmi

        import salt.utils.winapi

        HAS_WMI = True
    else:
        HAS_WMI = False
except ImportError:
    HAS_WMI = False

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

if salt.utils.platform.is_windows():
    ping_master = namespaced_function(ping_master, globals())
    time_ = namespaced_function(time_, globals())

__virtualname__ = "status"


# Taken from https://www.geoffchappell.com/studies/windows/km/ntoskrnl/api/ex/sysinfo/performance.htm
class SYSTEM_PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("IdleProcessTime", ctypes.c_int64),
        ("IoReadTransferCount", ctypes.c_int64),
        ("IoWriteTransferCount", ctypes.c_int64),
        ("IoOtherTransferCount", ctypes.c_int64),
        ("IoReadOperationCount", ctypes.c_ulong),
        ("IoWriteOperationCount", ctypes.c_ulong),
        ("IoOtherOperationCount", ctypes.c_ulong),
        ("AvailablePages", ctypes.c_ulong),
        ("CommittedPages", ctypes.c_ulong),
        ("CommitLimit", ctypes.c_ulong),
        ("PeakCommitment", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("CopyOnWriteCount", ctypes.c_ulong),
        ("TransitionCount", ctypes.c_ulong),
        ("CacheTransitionCount", ctypes.c_ulong),
        ("DemandZeroCount", ctypes.c_ulong),
        ("PageReadCount", ctypes.c_ulong),
        ("PageReadIoCount", ctypes.c_ulong),
        ("CacheReadCount", ctypes.c_ulong),  # Was c_ulong ** 2
        ("CacheIoCount", ctypes.c_ulong),
        ("DirtyPagesWriteCount", ctypes.c_ulong),
        ("DirtyWriteIoCount", ctypes.c_ulong),
        ("MappedPagesWriteCount", ctypes.c_ulong),
        ("MappedWriteIoCount", ctypes.c_ulong),
        ("PagedPoolPages", ctypes.c_ulong),
        ("NonPagedPoolPages", ctypes.c_ulong),
        ("PagedPoolAllocs", ctypes.c_ulong),
        ("PagedPoolFrees", ctypes.c_ulong),
        ("NonPagedPoolAllocs", ctypes.c_ulong),
        ("NonPagedPoolFrees", ctypes.c_ulong),
        ("FreeSystemPtes", ctypes.c_ulong),
        ("ResidentSystemCodePage", ctypes.c_ulong),
        ("TotalSystemDriverPages", ctypes.c_ulong),
        ("TotalSystemCodePages", ctypes.c_ulong),
        ("NonPagedPoolLookasideHits", ctypes.c_ulong),
        ("PagedPoolLookasideHits", ctypes.c_ulong),
        ("AvailablePagedPoolPages", ctypes.c_ulong),
        ("ResidentSystemCachePage", ctypes.c_ulong),
        ("ResidentPagedPoolPage", ctypes.c_ulong),
        ("ResidentSystemDriverPage", ctypes.c_ulong),
        ("CcFastReadNoWait", ctypes.c_ulong),
        ("CcFastReadWait", ctypes.c_ulong),
        ("CcFastReadResourceMiss", ctypes.c_ulong),
        ("CcFastReadNotPossible", ctypes.c_ulong),
        ("CcFastMdlReadNoWait", ctypes.c_ulong),
        ("CcFastMdlReadWait", ctypes.c_ulong),
        ("CcFastMdlReadResourceMiss", ctypes.c_ulong),
        ("CcFastMdlReadNotPossible", ctypes.c_ulong),
        ("CcMapDataNoWait", ctypes.c_ulong),
        ("CcMapDataWait", ctypes.c_ulong),
        ("CcMapDataNoWaitMiss", ctypes.c_ulong),
        ("CcMapDataWaitMiss", ctypes.c_ulong),
        ("CcPinMappedDataCount", ctypes.c_ulong),
        ("CcPinReadNoWait", ctypes.c_ulong),
        ("CcPinReadWait", ctypes.c_ulong),
        ("CcPinReadNoWaitMiss", ctypes.c_ulong),
        ("CcPinReadWaitMiss", ctypes.c_ulong),
        ("CcCopyReadNoWait", ctypes.c_ulong),
        ("CcCopyReadWait", ctypes.c_ulong),
        ("CcCopyReadNoWaitMiss", ctypes.c_ulong),
        ("CcCopyReadWaitMiss", ctypes.c_ulong),
        ("CcMdlReadNoWait", ctypes.c_ulong),
        ("CcMdlReadWait", ctypes.c_ulong),
        ("CcMdlReadNoWaitMiss", ctypes.c_ulong),
        ("CcMdlReadWaitMiss", ctypes.c_ulong),
        ("CcReadAheadIos", ctypes.c_ulong),
        ("CcLazyWriteIos", ctypes.c_ulong),
        ("CcLazyWritePages", ctypes.c_ulong),
        ("CcDataFlushes", ctypes.c_ulong),
        ("CcDataPages", ctypes.c_ulong),
        ("ContextSwitches", ctypes.c_ulong),
        ("FirstLevelTbFills", ctypes.c_ulong),
        ("SecondLevelTbFills", ctypes.c_ulong),
        ("SystemCalls", ctypes.c_ulong),
        # Windows 8 and above
        ("CcTotalDirtyPages", ctypes.c_ulonglong),
        ("CcDirtyPagesThreshold", ctypes.c_ulonglong),
        ("ResidentAvailablePages", ctypes.c_longlong),
        # Windows 10 and above
        ("SharedCommittedPages", ctypes.c_ulonglong),
    ]


def __virtual__():
    """
    Only works on Windows systems with WMI and WinAPI
    """
    if not salt.utils.platform.is_windows():
        return False, "win_status.py: Requires Windows"

    if not HAS_WMI:
        return False, "win_status.py: Requires WMI and WinAPI"

    if not HAS_PSUTIL:
        return False, "win_status.py: Requires psutil"

    # Namespace modules from `status.py`
    global ping_master, time_

    return __virtualname__


__func_alias__ = {"time_": "time"}


def cpustats():
    """
    Return information about the CPU.

    Returns
        dict: A dictionary containing information about the CPU stats

    CLI Example:

    .. code-block:: bash

        salt * status.cpustats
    """
    # Tries to gather information similar to that returned by a Linux machine
    # Avoid using WMI as there's a lot of overhead

    # Time related info
    user, system, idle, interrupt, dpc = psutil.cpu_times()
    cpu = {"user": user, "system": system, "idle": idle, "irq": interrupt, "dpc": dpc}
    # Count related info
    ctx_switches, interrupts, soft_interrupts, sys_calls = psutil.cpu_stats()
    intr = {"irqs": {"irqs": [], "total": interrupts}}
    soft_irq = {"softirqs": [], "total": soft_interrupts}
    return {
        "btime": psutil.boot_time(),
        "cpu": cpu,
        "ctxt": ctx_switches,
        "intr": intr,
        "processes": len(psutil.pids()),
        "softirq": soft_irq,
        "syscalls": sys_calls,
    }


def meminfo():
    """
    Return information about physical and virtual memory on the system

    Returns:
        dict: A dictionary of information about memory on the system

    CLI Example:

    .. code-block:: bash

        salt * status.meminfo
    """
    # Get physical memory
    vm_total, vm_available, vm_percent, vm_used, vm_free = psutil.virtual_memory()
    # Get swap memory
    swp_total, swp_used, swp_free, swp_percent, _, _ = psutil.swap_memory()

    def get_unit_value(memory):
        symbols = ("K", "M", "G", "T", "P", "E", "Z", "Y")
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i + 1) * 10
        for s in reversed(symbols):
            if memory >= prefix[s]:
                value = float(memory) / prefix[s]
                return {"unit": s, "value": value}
        return {"unit": "B", "value": memory}

    return {
        "VmallocTotal": get_unit_value(vm_total),
        "VmallocUsed": get_unit_value(vm_used),
        "VmallocFree": get_unit_value(vm_free),
        "VmallocAvail": get_unit_value(vm_available),
        "SwapTotal": get_unit_value(swp_total),
        "SwapUsed": get_unit_value(swp_used),
        "SwapFree": get_unit_value(swp_free),
    }


def vmstats():
    """
    Return information about the virtual memory on the machine

    Returns:
        dict: A dictionary of virtual memory stats

    CLI Example:

    .. code-block:: bash

        salt * status.vmstats
    """
    # Setup the SPI Structure
    spi = SYSTEM_PERFORMANCE_INFORMATION()
    retlen = ctypes.c_ulong()

    # 2 means to query System Performance Information and return it in a
    # SYSTEM_PERFORMANCE_INFORMATION Structure
    ctypes.windll.ntdll.NtQuerySystemInformation(
        2, ctypes.byref(spi), ctypes.sizeof(spi), ctypes.byref(retlen)
    )

    # Return each defined field in a dict
    ret = {}
    for field in spi._fields_:
        ret.update({field[0]: getattr(spi, field[0])})

    return ret


def loadavg():
    """
    Returns counter information related to the load of the machine

    Returns:
        dict: A dictionary of counters

    CLI Example:

    .. code-block:: bash

        salt * status.loadavg
    """
    # Counter List (obj, instance, counter)
    counter_list = [
        ("Memory", None, "Available Bytes"),
        ("Memory", None, "Pages/sec"),
        ("Paging File", "*", "% Usage"),
        ("Processor", "*", "% Processor Time"),
        ("Processor", "*", "DPCs Queued/sec"),
        ("Processor", "*", "% Privileged Time"),
        ("Processor", "*", "% User Time"),
        ("Processor", "*", "% DPC Time"),
        ("Processor", "*", "% Interrupt Time"),
        ("Server", None, "Work Item Shortages"),
        ("Server Work Queues", "*", "Queue Length"),
        ("System", None, "Processor Queue Length"),
        ("System", None, "Context Switches/sec"),
    ]
    return salt.utils.win_pdh.get_counters(counter_list=counter_list)


def cpuload():
    """
    .. versionadded:: 2015.8.0

    Return the processor load as a percentage

    CLI Example:

    .. code-block:: bash

       salt '*' status.cpuload
    """
    return psutil.cpu_percent()


def diskusage(human_readable=False, path=None):
    """
    .. versionadded:: 2015.8.0

    Return the disk usage for this minion

    human_readable : False
        If ``True``, usage will be in KB/MB/GB etc.

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskusage path=c:/salt
    """
    if not path:
        path = "c:/"

    disk_stats = psutil.disk_usage(path)

    total_val = disk_stats.total
    used_val = disk_stats.used
    free_val = disk_stats.free
    percent = disk_stats.percent

    if human_readable:
        total_val = _byte_calc(total_val)
        used_val = _byte_calc(used_val)
        free_val = _byte_calc(free_val)

    return {"total": total_val, "used": used_val, "free": free_val, "percent": percent}


def procs(count=False):
    """
    Return the process data

    count : False
        If ``True``, this function will simply return the number of processes.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
        salt '*' status.procs count
    """
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        processes = wmi_obj.win32_process()

    # this short circuit's the function to get a short simple proc count.
    if count:
        return len(processes)

    # a propper run of the function, creating a nonsensically long out put.
    process_info = {}
    for proc in processes:
        process_info[proc.ProcessId] = _get_process_info(proc)

    return process_info


def saltmem(human_readable=False):
    """
    .. versionadded:: 2015.8.0

    Returns the amount of memory that salt is using

    human_readable : False
        return the value in a nicely formatted number

    CLI Example:

    .. code-block:: bash

        salt '*' status.saltmem
        salt '*' status.saltmem human_readable=True
    """
    # psutil.Process defaults to current process (`os.getpid()`)
    p = psutil.Process()

    # Use oneshot to get a snapshot
    with p.oneshot():
        mem = p.memory_info().rss

    if human_readable:
        return _byte_calc(mem)

    return mem


def uptime(human_readable=False):
    """
    .. versionadded:: 2015.8.0

    Return the system uptime for the machine

    Args:

        human_readable (bool):
            Return uptime in human readable format if ``True``, otherwise
            return seconds. Default is ``False``

            .. note::
                Human readable format is ``days, hours:min:sec``. Days will only
                be displayed if more than 0

    Returns:
        str:
            The uptime in seconds or human readable format depending on the
            value of ``human_readable``

    CLI Example:

    .. code-block:: bash

        salt '*' status.uptime
        salt '*' status.uptime human_readable=True
    """
    # Get startup time
    startup_time = datetime.datetime.fromtimestamp(psutil.boot_time())

    # Subtract startup time from current time to get the uptime of the system
    uptime = datetime.datetime.now() - startup_time

    return str(uptime) if human_readable else uptime.total_seconds()


def _get_process_info(proc):
    """
    Return  process information
    """
    cmd = salt.utils.stringutils.to_unicode(proc.CommandLine or "")
    name = salt.utils.stringutils.to_unicode(proc.Name)
    info = dict(cmd=cmd, name=name, **_get_process_owner(proc))
    return info


def _get_process_owner(process):
    owner = {}
    domain, error_code, user = None, None, None
    try:
        domain, error_code, user = process.GetOwner()
        owner["user"] = salt.utils.stringutils.to_unicode(user)
        owner["user_domain"] = salt.utils.stringutils.to_unicode(domain)
    except Exception as exc:  # pylint: disable=broad-except
        pass
    if not error_code and all((user, domain)):
        owner["user"] = salt.utils.stringutils.to_unicode(user)
        owner["user_domain"] = salt.utils.stringutils.to_unicode(domain)
    elif process.ProcessId in [0, 4] and error_code == 2:
        # Access Denied for System Idle Process and System
        owner["user"] = "SYSTEM"
        owner["user_domain"] = "NT AUTHORITY"
    else:
        log.warning(
            "Error getting owner of process; PID='%s'; Error: %s",
            process.ProcessId,
            error_code,
        )
    return owner


def _byte_calc(val):
    if val < 1024:
        tstr = str(val) + "B"
    elif val < 1038336:
        tstr = str(val / 1024) + "KB"
    elif val < 1073741824:
        tstr = str(val / 1038336) + "MB"
    elif val < 1099511627776:
        tstr = str(val / 1073741824) + "GB"
    else:
        tstr = str(val / 1099511627776) + "TB"
    return tstr


def master(master=None, connected=True):
    """
    .. versionadded:: 2015.5.0

    Fire an event if the minion gets disconnected from its master. This
    function is meant to be run via a scheduled job from the minion. If
    master_ip is an FQDN/Hostname, is must be resolvable to a valid IPv4
    address.

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    """

    def _win_remotes_on(port):
        """
        Windows specific helper function.
        Returns set of ipv4 host addresses of remote established connections
        on local or remote tcp port.

        Parses output of shell 'netstat' to get connections

        PS C:> netstat -n -p TCP

        Active Connections

          Proto  Local Address          Foreign Address        State
          TCP    10.1.1.26:3389         10.1.1.1:4505          ESTABLISHED
          TCP    10.1.1.26:56862        10.1.1.10:49155        TIME_WAIT
          TCP    10.1.1.26:56868        169.254.169.254:80     CLOSE_WAIT
          TCP    127.0.0.1:49197        127.0.0.1:49198        ESTABLISHED
          TCP    127.0.0.1:49198        127.0.0.1:49197        ESTABLISHED
        """
        remotes = set()
        try:
            data = subprocess.check_output(
                ["netstat", "-n", "-p", "TCP"]
            )  # pylint: disable=minimum-python-version
        except subprocess.CalledProcessError:
            log.error("Failed netstat")
            raise

        lines = salt.utils.stringutils.to_unicode(data).split("\n")
        for line in lines:
            if "ESTABLISHED" not in line:
                continue
            chunks = line.split()
            remote_host, remote_port = chunks[2].rsplit(":", 1)
            if int(remote_port) != port:
                continue
            remotes.add(remote_host)
        return remotes

    # the default publishing port
    port = 4505
    master_ips = None

    if master:
        master_ips = _host_to_ips(master)

    if not master_ips:
        return

    if __salt__["config.get"]("publish_port") != "":
        port = int(__salt__["config.get"]("publish_port"))

    master_connection_status = False
    connected_ips = _win_remotes_on(port)

    # Get connection status for master
    for master_ip in master_ips:
        if master_ip in connected_ips:
            master_connection_status = True
            break

    # Connection to master is not as expected
    if master_connection_status is not connected:
        with salt.utils.event.get_event(
            "minion", opts=__opts__, listen=False
        ) as event_bus:
            if master_connection_status:
                event_bus.fire_event(
                    {"master": master}, salt.minion.master_event(type="connected")
                )
            else:
                event_bus.fire_event(
                    {"master": master}, salt.minion.master_event(type="disconnected")
                )

    return master_connection_status
