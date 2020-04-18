# -*- coding: utf-8 -*-
"""
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import collections
import copy
import datetime
import fnmatch
import logging
import os
import re
import time

# Import salt libs
import salt.config
import salt.minion
import salt.utils.event
import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range, zip

log = logging.getLogger(__file__)

__virtualname__ = "status"
__opts__ = {}

# Don't shadow built-in's.
__func_alias__ = {"time_": "time"}


log = logging.getLogger(__name__)


def __virtual__():
    """
    Not all functions supported by Windows
    """
    if salt.utils.platform.is_windows():
        return False, "Windows platform is not supported by this module"

    return __virtualname__


def _number(text):
    """
    Convert a string to a number.
    Returns an integer if the string represents an integer, a floating
    point number if the string is a real number, or the string unchanged
    otherwise.
    """
    if text.isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text


def _get_boot_time_aix():
    """
    Return the number of seconds since boot time on AIX

    t=$(LC_ALL=POSIX ps -o etime= -p 1)
    d=0 h=0
    case $t in *-*) d=${t%%-*}; t=${t#*-};; esac
    case $t in *:*:*) h=${t%%:*}; t=${t#*:};; esac
    s=$((d*86400 + h*3600 + ${t%%:*}*60 + ${t#*:}))

    t is 7-20:46:46
    """
    boot_secs = 0
    res = __salt__["cmd.run_all"]("ps -o etime= -p 1")
    if res["retcode"] > 0:
        raise CommandExecutionError("Unable to find boot_time for pid 1.")
    bt_time = res["stdout"]
    days = bt_time.split("-")
    hms = days[1].split(":")
    boot_secs = (
        _number(days[0]) * 86400
        + _number(hms[0]) * 3600
        + _number(hms[1]) * 60
        + _number(hms[2])
    )
    return boot_secs


def _aix_loadavg():
    """
    Return the load average on AIX
    """
    #  03:42PM   up 9 days,  20:41,  2 users,  load average: 0.28, 0.47, 0.69
    uptime = __salt__["cmd.run"]("uptime")
    ldavg = uptime.split("load average")
    load_avg = ldavg[1].split()
    return {
        "1-min": load_avg[1].strip(","),
        "5-min": load_avg[2].strip(","),
        "15-min": load_avg[3],
    }


def _aix_nproc():
    """
    Return the maximun number of PROCESSES allowed per user on AIX
    """
    nprocs = __salt__["cmd.run"](
        "lsattr -E -l sys0 | grep maxuproc", python_shell=True
    ).split()
    return _number(nprocs[1])


def procs():
    """
    Return the process data

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
    """
    # Get the user, pid and cmd
    ret = {}
    uind = 0
    pind = 0
    cind = 0
    plines = __salt__["cmd.run"](__grains__["ps"], python_shell=True).splitlines()
    guide = plines.pop(0).split()
    if "USER" in guide:
        uind = guide.index("USER")
    elif "UID" in guide:
        uind = guide.index("UID")
    if "PID" in guide:
        pind = guide.index("PID")
    if "COMMAND" in guide:
        cind = guide.index("COMMAND")
    elif "CMD" in guide:
        cind = guide.index("CMD")
    for line in plines:
        if not line:
            continue
        comps = line.split()
        ret[comps[pind]] = {"user": comps[uind], "cmd": " ".join(comps[cind:])}
    return ret


def custom():
    """
    Return a custom composite of status data and info for this minion,
    based on the minion config file. An example config like might be::

        status.cpustats.custom: [ 'cpu', 'ctxt', 'btime', 'processes' ]

    Where status refers to status.py, cpustats is the function
    where we get our data, and custom is this function It is followed
    by a list of keys that we want returned.

    This function is meant to replace all_status(), which returns
    anything and everything, which we probably don't want.

    By default, nothing is returned. Warning: Depending on what you
    include, there can be a LOT here!

    CLI Example:

    .. code-block:: bash

        salt '*' status.custom
    """
    ret = {}
    conf = __salt__["config.dot_vals"]("status")
    for key, val in six.iteritems(conf):
        func = "{0}()".format(key.split(".")[1])
        vals = eval(func)  # pylint: disable=W0123

        for item in val:
            ret[item] = vals[item]

    return ret


def uptime():
    """
    Return the uptime for this system.

    .. versionchanged:: 2015.8.9
        The uptime function was changed to return a dictionary of easy-to-read
        key/value pairs containing uptime information, instead of the output
        from a ``cmd.run`` call.

    .. versionchanged:: 2016.11.0
        Support for OpenBSD, FreeBSD, NetBSD, MacOS, and Solaris

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.uptime
    """
    curr_seconds = time.time()

    # Get uptime in seconds
    if salt.utils.platform.is_linux():
        ut_path = "/proc/uptime"
        if not os.path.exists(ut_path):
            raise CommandExecutionError(
                "File {ut_path} was not found.".format(ut_path=ut_path)
            )
        with salt.utils.files.fopen(ut_path) as rfh:
            seconds = int(float(rfh.read().split()[0]))
    elif salt.utils.platform.is_sunos():
        # note: some flavors/versions report the host uptime inside a zone
        #       https://support.oracle.com/epmos/faces/BugDisplay?id=15611584
        res = __salt__["cmd.run_all"]("kstat -p unix:0:system_misc:boot_time")
        if res["retcode"] > 0:
            raise CommandExecutionError("The boot_time kstat was not found.")
        seconds = int(curr_seconds - int(res["stdout"].split()[-1]))
    elif salt.utils.platform.is_openbsd() or salt.utils.platform.is_netbsd():
        bt_data = __salt__["sysctl.get"]("kern.boottime")
        if not bt_data:
            raise CommandExecutionError("Cannot find kern.boottime system parameter")
        seconds = int(curr_seconds - int(bt_data))
    elif salt.utils.platform.is_freebsd() or salt.utils.platform.is_darwin():
        # format: { sec = 1477761334, usec = 664698 } Sat Oct 29 17:15:34 2016
        bt_data = __salt__["sysctl.get"]("kern.boottime")
        if not bt_data:
            raise CommandExecutionError("Cannot find kern.boottime system parameter")
        data = bt_data.split("{")[-1].split("}")[0].strip().replace(" ", "")
        uptime = dict(
            [(k, int(v,)) for k, v in [p.strip().split("=") for p in data.split(",")]]
        )
        seconds = int(curr_seconds - uptime["sec"])
    elif salt.utils.platform.is_aix():
        seconds = _get_boot_time_aix()
    else:
        return __salt__["cmd.run"]("uptime")

    # Setup datetime and timedelta objects
    boot_time = datetime.datetime.utcfromtimestamp(curr_seconds - seconds)
    curr_time = datetime.datetime.utcfromtimestamp(curr_seconds)
    up_time = curr_time - boot_time

    # Construct return information
    ut_ret = {
        "seconds": seconds,
        "since_iso": boot_time.isoformat(),
        "since_t": int(curr_seconds - seconds),
        "days": up_time.days,
        "time": "{0}:{1}".format(up_time.seconds // 3600, up_time.seconds % 3600 // 60),
    }

    if salt.utils.path.which("who"):
        who_cmd = (
            "who" if salt.utils.platform.is_openbsd() else "who -s"
        )  # OpenBSD does not support -s
        ut_ret["users"] = len(__salt__["cmd.run"](who_cmd).split(os.linesep))

    return ut_ret


def loadavg():
    """
    Return the load averages for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.loadavg

        :raises CommandExecutionError: If the system cannot report loadaverages to Python
    """
    if __grains__["kernel"] == "AIX":
        return _aix_loadavg()

    try:
        load_avg = os.getloadavg()
    except AttributeError:
        # Some UNIX-based operating systems do not have os.getloadavg()
        raise salt.exceptions.CommandExecutionError(
            "status.loadavag is not available on your platform"
        )
    return {"1-min": load_avg[0], "5-min": load_avg[1], "15-min": load_avg[2]}


def cpustats():
    """
    Return the CPU stats for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.cpustats
    """

    def linux_cpustats():
        """
        linux specific implementation of cpustats
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/stat", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split()
                if comps[0] == "cpu":
                    ret[comps[0]] = {
                        "idle": _number(comps[4]),
                        "iowait": _number(comps[5]),
                        "irq": _number(comps[6]),
                        "nice": _number(comps[2]),
                        "softirq": _number(comps[7]),
                        "steal": _number(comps[8]),
                        "system": _number(comps[3]),
                        "user": _number(comps[1]),
                    }
                elif comps[0] == "intr":
                    ret[comps[0]] = {
                        "total": _number(comps[1]),
                        "irqs": [_number(x) for x in comps[2:]],
                    }
                elif comps[0] == "softirq":
                    ret[comps[0]] = {
                        "total": _number(comps[1]),
                        "softirqs": [_number(x) for x in comps[2:]],
                    }
                else:
                    ret[comps[0]] = _number(comps[1])
        return ret

    def freebsd_cpustats():
        """
        freebsd specific implementation of cpustats
        """
        vmstat = __salt__["cmd.run"]("vmstat -P").splitlines()
        vm0 = vmstat[0].split()
        cpu0loc = vm0.index("cpu0")
        vm1 = vmstat[1].split()
        usloc = vm1.index("us")
        vm2 = vmstat[2].split()
        cpuctr = 0
        ret = {}
        for cpu in vm0[cpu0loc:]:
            ret[cpu] = {
                "us": _number(vm2[usloc + 3 * cpuctr]),
                "sy": _number(vm2[usloc + 1 + 3 * cpuctr]),
                "id": _number(vm2[usloc + 2 + 3 * cpuctr]),
            }
            cpuctr += 1
        return ret

    def sunos_cpustats():
        """
        sunos specific implementation of cpustats
        """
        mpstat = __salt__["cmd.run"]("mpstat 1 2").splitlines()
        fields = mpstat[0].split()
        ret = {}
        for cpu in mpstat:
            if cpu.startswith("CPU"):
                continue
            cpu = cpu.split()
            ret[_number(cpu[0])] = {}
            for i in range(1, len(fields) - 1):
                ret[_number(cpu[0])][fields[i]] = _number(cpu[i])
        return ret

    def aix_cpustats():
        """
        AIX specific implementation of cpustats
        """
        ret = {}
        ret["mpstat"] = []
        procn = None
        fields = []
        for line in __salt__["cmd.run"]("mpstat -a").splitlines():
            if not line:
                continue
            procn = len(ret["mpstat"])
            if line.startswith("System"):
                comps = line.split(":")
                ret["mpstat"].append({})
                ret["mpstat"][procn]["system"] = {}
                cpu_comps = comps[1].split()
                for i in range(0, len(cpu_comps)):
                    cpu_vals = cpu_comps[i].split("=")
                    ret["mpstat"][procn]["system"][cpu_vals[0]] = cpu_vals[1]

            if line.startswith("cpu"):
                fields = line.split()
                continue

            if fields:
                cpustat = line.split()
                ret[_number(cpustat[0])] = {}
                for i in range(1, len(fields) - 1):
                    ret[_number(cpustat[0])][fields[i]] = _number(cpustat[i])

        return ret

    def openbsd_cpustats():
        """
        openbsd specific implementation of cpustats
        """
        systat = __salt__["cmd.run"]("systat -s 2 -B cpu").splitlines()
        fields = systat[3].split()
        ret = {}
        for cpu in systat[4:]:
            cpu_line = cpu.split()
            cpu_idx = cpu_line[0]
            ret[cpu_idx] = {}

            for idx, field in enumerate(fields[1:]):
                ret[cpu_idx][field] = cpu_line[idx + 1]

        return ret

    # dict that return a function that does the right thing per platform
    get_version = {
        "Linux": linux_cpustats,
        "FreeBSD": freebsd_cpustats,
        "OpenBSD": openbsd_cpustats,
        "SunOS": sunos_cpustats,
        "AIX": aix_cpustats,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def meminfo():
    """
    Return the memory info for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.meminfo
    """

    def linux_meminfo():
        """
        linux specific implementation of meminfo
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/meminfo", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split()
                comps[0] = comps[0].replace(":", "")
                ret[comps[0]] = {
                    "value": comps[1],
                }
                if len(comps) > 2:
                    ret[comps[0]]["unit"] = comps[2]
        return ret

    def freebsd_meminfo():
        """
        freebsd specific implementation of meminfo
        """
        sysctlvm = __salt__["cmd.run"]("sysctl vm").splitlines()
        sysctlvm = [x for x in sysctlvm if x.startswith("vm")]
        sysctlvm = [x.split(":") for x in sysctlvm]
        sysctlvm = [[y.strip() for y in x] for x in sysctlvm]
        sysctlvm = [x for x in sysctlvm if x[1]]  # If x[1] not empty

        ret = {}
        for line in sysctlvm:
            ret[line[0]] = line[1]
        # Special handling for vm.total as it's especially important
        sysctlvmtot = __salt__["cmd.run"]("sysctl -n vm.vmtotal").splitlines()
        sysctlvmtot = [x for x in sysctlvmtot if x]
        ret["vm.vmtotal"] = sysctlvmtot
        return ret

    def aix_meminfo():
        """
        AIX specific implementation of meminfo
        """
        ret = {}
        ret["svmon"] = []
        ret["vmstat"] = []
        procn = None
        fields = []
        pagesize_flag = False
        for line in __salt__["cmd.run"]("svmon -G").splitlines():
            # Note: svmon is per-system
            #               size       inuse        free         pin     virtual   mmode
            # memory      1048576     1039740        8836      285078      474993     Ded
            # pg space     917504        2574
            #
            #               work        pers        clnt       other
            # pin          248379           0        2107       34592
            # in use       474993           0      564747
            #
            # PageSize   PoolSize       inuse        pgsp         pin     virtual
            # s    4 KB         -      666956        2574       60726      102209
            # m   64 KB         -       23299           0       14022       23299
            if not line:
                continue

            if re.match(r"\s", line):
                # assume fields line
                fields = line.split()
                continue

            if line.startswith("memory") or line.startswith("pin"):
                procn = len(ret["svmon"])
                ret["svmon"].append({})
                comps = line.split()
                ret["svmon"][procn][comps[0]] = {}
                for i in range(0, len(fields)):
                    if len(comps) > i + 1:
                        ret["svmon"][procn][comps[0]][fields[i]] = comps[i + 1]
                continue

            if line.startswith("pg space") or line.startswith("in use"):
                procn = len(ret["svmon"])
                ret["svmon"].append({})
                comps = line.split()
                pg_space = "{0} {1}".format(comps[0], comps[1])
                ret["svmon"][procn][pg_space] = {}
                for i in range(0, len(fields)):
                    if len(comps) > i + 2:
                        ret["svmon"][procn][pg_space][fields[i]] = comps[i + 2]
                continue

            if line.startswith("PageSize"):
                fields = line.split()
                pagesize_flag = False
                continue

            if pagesize_flag:
                procn = len(ret["svmon"])
                ret["svmon"].append({})
                comps = line.split()
                ret["svmon"][procn][comps[0]] = {}
                for i in range(0, len(fields)):
                    if len(comps) > i:
                        ret["svmon"][procn][comps[0]][fields[i]] = comps[i]
                continue

        for line in __salt__["cmd.run"]("vmstat -v").splitlines():
            # Note: vmstat is per-system
            if not line:
                continue

            procn = len(ret["vmstat"])
            ret["vmstat"].append({})
            comps = line.lstrip().split(" ", 1)
            ret["vmstat"][procn][comps[1]] = comps[0]

        return ret

    def openbsd_meminfo():
        """
        openbsd specific implementation of meminfo
        """
        vmstat = __salt__["cmd.run"]("vmstat").splitlines()
        # We're only interested in memory and page values which are printed
        # as subsequent fields.
        fields = [
            "active virtual pages",
            "free list size",
            "page faults",
            "pages reclaimed",
            "pages paged in",
            "pages paged out",
            "pages freed",
            "pages scanned",
        ]
        data = vmstat[2].split()[2:10]
        ret = dict(zip(fields, data))
        return ret

    # dict that return a function that does the right thing per platform
    get_version = {
        "Linux": linux_meminfo,
        "FreeBSD": freebsd_meminfo,
        "OpenBSD": openbsd_meminfo,
        "AIX": aix_meminfo,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def cpuinfo():
    """
    .. versionchanged:: 2016.3.2
        Return the CPU info for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for NetBSD and OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.cpuinfo
    """

    def linux_cpuinfo():
        """
        linux specific cpuinfo implementation
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/cpuinfo", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split(":")
                comps[0] = comps[0].strip()
                if comps[0] == "flags":
                    ret[comps[0]] = comps[1].split()
                else:
                    ret[comps[0]] = comps[1].strip()
        return ret

    def bsd_cpuinfo():
        """
        bsd specific cpuinfo implementation
        """
        bsd_cmd = "sysctl hw.model hw.ncpu"
        ret = {}
        if __grains__["kernel"].lower() in ["netbsd", "openbsd"]:
            sep = "="
        else:
            sep = ":"

        for line in __salt__["cmd.run"](bsd_cmd).splitlines():
            if not line:
                continue
            comps = line.split(sep)
            comps[0] = comps[0].strip()
            ret[comps[0]] = comps[1].strip()
        return ret

    def sunos_cpuinfo():
        """
        sunos specific cpuinfo implementation
        """
        ret = {}
        ret["isainfo"] = {}
        for line in __salt__["cmd.run"]("isainfo -x").splitlines():
            # Note: isainfo is per-system and not per-cpu
            # Output Example:
            # amd64: rdrand f16c vmx avx xsave pclmulqdq aes sse4.2 sse4.1 ssse3 popcnt tscp cx16 sse3 sse2 sse fxsr mmx cmov amd_sysc cx8 tsc fpu
            # i386: rdrand f16c vmx avx xsave pclmulqdq aes sse4.2 sse4.1 ssse3 popcnt tscp ahf cx16 sse3 sse2 sse fxsr mmx cmov sep cx8 tsc fpu
            if not line:
                continue
            comps = line.split(":")
            comps[0] = comps[0].strip()
            ret["isainfo"][comps[0]] = sorted(comps[1].strip().split())
        ret["psrinfo"] = []
        procn = None
        for line in __salt__["cmd.run"]("psrinfo -v -p").splitlines():
            # Output Example:
            # The physical processor has 6 cores and 12 virtual processors (0-5 12-17)
            #  The core has 2 virtual processors (0 12)
            #  The core has 2 virtual processors (1 13)
            #  The core has 2 virtual processors (2 14)
            #  The core has 2 virtual processors (3 15)
            #  The core has 2 virtual processors (4 16)
            #  The core has 2 virtual processors (5 17)
            #    x86 (GenuineIntel 306E4 family 6 model 62 step 4 clock 2100 MHz)
            #      Intel(r) Xeon(r) CPU E5-2620 v2 @ 2.10GHz
            # The physical processor has 6 cores and 12 virtual processors (6-11 18-23)
            #  The core has 2 virtual processors (6 18)
            #  The core has 2 virtual processors (7 19)
            #  The core has 2 virtual processors (8 20)
            #  The core has 2 virtual processors (9 21)
            #  The core has 2 virtual processors (10 22)
            #  The core has 2 virtual processors (11 23)
            #    x86 (GenuineIntel 306E4 family 6 model 62 step 4 clock 2100 MHz)
            #      Intel(r) Xeon(r) CPU E5-2620 v2 @ 2.10GHz
            #
            # Output Example 2:
            # The physical processor has 4 virtual processors (0-3)
            #  x86 (GenuineIntel 406D8 family 6 model 77 step 8 clock 2400 MHz)
            #        Intel(r) Atom(tm) CPU  C2558  @ 2.40GHz
            if not line:
                continue
            if line.startswith("The physical processor"):
                procn = len(ret["psrinfo"])
                line = line.split()
                ret["psrinfo"].append({})
                if "cores" in line:
                    ret["psrinfo"][procn]["topology"] = {}
                    ret["psrinfo"][procn]["topology"]["cores"] = _number(line[4])
                    ret["psrinfo"][procn]["topology"]["threads"] = _number(line[7])
                elif "virtual" in line:
                    ret["psrinfo"][procn]["topology"] = {}
                    ret["psrinfo"][procn]["topology"]["threads"] = _number(line[4])
            elif line.startswith(" " * 6):  # 3x2 space indent
                ret["psrinfo"][procn]["name"] = line.strip()
            elif line.startswith(" " * 4):  # 2x2 space indent
                line = line.strip().split()
                ret["psrinfo"][procn]["vendor"] = line[1][1:]
                ret["psrinfo"][procn]["family"] = _number(line[4])
                ret["psrinfo"][procn]["model"] = _number(line[6])
                ret["psrinfo"][procn]["step"] = _number(line[8])
                ret["psrinfo"][procn]["clock"] = "{0} {1}".format(
                    line[10], line[11][:-1]
                )
        return ret

    def aix_cpuinfo():
        """
        AIX  specific cpuinfo implementation
        """
        ret = {}
        ret["prtconf"] = []
        ret["lparstat"] = []
        procn = None
        for line in __salt__["cmd.run"](
            'prtconf | grep -i "Processor"', python_shell=True
        ).splitlines():
            # Note: prtconf is per-system and not per-cpu
            # Output Example:
            # prtconf | grep -i "Processor"
            # Processor Type: PowerPC_POWER7
            # Processor Implementation Mode: POWER 7
            # Processor Version: PV_7_Compat
            # Number Of Processors: 2
            # Processor Clock Speed: 3000 MHz
            #  Model Implementation: Multiple Processor, PCI bus
            #  + proc0                                                           Processor
            #  + proc4                                                           Processor
            if not line:
                continue
            procn = len(ret["prtconf"])
            if line.startswith("Processor") or line.startswith("Number"):
                ret["prtconf"].append({})
                comps = line.split(":")
                comps[0] = comps[0].rstrip()
                ret["prtconf"][procn][comps[0]] = comps[1]
            else:
                continue

        for line in __salt__["cmd.run"](
            'prtconf | grep "CPU"', python_shell=True
        ).splitlines():
            # Note: prtconf is per-system and not per-cpu
            # Output Example:
            # CPU Type: 64-bit
            if not line:
                continue
            procn = len(ret["prtconf"])
            if line.startswith("CPU"):
                ret["prtconf"].append({})
                comps = line.split(":")
                comps[0] = comps[0].rstrip()
                ret["prtconf"][procn][comps[0]] = comps[1]
            else:
                continue

        for line in __salt__["cmd.run"](
            "lparstat -i | grep CPU", python_shell=True
        ).splitlines():
            # Note: lparstat is per-system and not per-cpu
            # Output Example:
            # Online Virtual CPUs                        : 2
            # Maximum Virtual CPUs                       : 2
            # Minimum Virtual CPUs                       : 1
            # Maximum Physical CPUs in system            : 32
            # Active Physical CPUs in system             : 32
            # Active CPUs in Pool                        : 32
            # Shared Physical CPUs in system             : 32
            # Physical CPU Percentage                    : 25.00%
            # Desired Virtual CPUs                       : 2
            if not line:
                continue

            procn = len(ret["lparstat"])
            ret["lparstat"].append({})
            comps = line.split(":")
            comps[0] = comps[0].rstrip()
            ret["lparstat"][procn][comps[0]] = comps[1]

        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_cpuinfo,
        "FreeBSD": bsd_cpuinfo,
        "NetBSD": bsd_cpuinfo,
        "OpenBSD": bsd_cpuinfo,
        "SunOS": sunos_cpuinfo,
        "AIX": aix_cpuinfo,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def diskstats():
    """
    .. versionchanged:: 2016.3.2
        Return the disk stats for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskstats
    """

    def linux_diskstats():
        """
        linux specific implementation of diskstats
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/diskstats", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split()
                ret[comps[2]] = {
                    "major": _number(comps[0]),
                    "minor": _number(comps[1]),
                    "device": _number(comps[2]),
                    "reads_issued": _number(comps[3]),
                    "reads_merged": _number(comps[4]),
                    "sectors_read": _number(comps[5]),
                    "ms_spent_reading": _number(comps[6]),
                    "writes_completed": _number(comps[7]),
                    "writes_merged": _number(comps[8]),
                    "sectors_written": _number(comps[9]),
                    "ms_spent_writing": _number(comps[10]),
                    "io_in_progress": _number(comps[11]),
                    "ms_spent_in_io": _number(comps[12]),
                    "weighted_ms_spent_in_io": _number(comps[13]),
                }
        return ret

    def generic_diskstats():
        """
        generic implementation of diskstats
        note: freebsd and sunos
        """
        ret = {}
        iostat = __salt__["cmd.run"]("iostat -xzd").splitlines()
        header = iostat[1]
        for line in iostat[2:]:
            comps = line.split()
            ret[comps[0]] = {}
            for metric, value in zip(header.split()[1:], comps[1:]):
                ret[comps[0]][metric] = _number(value)
        return ret

    def aix_diskstats():
        """
        AIX specific implementation of diskstats
        """
        ret = {}
        procn = None
        fields = []
        disk_name = ""
        disk_mode = ""
        for line in __salt__["cmd.run"]("iostat -dDV").splitlines():
            # Note: iostat -dDV is per-system
            #
            # System configuration: lcpu=8 drives=1 paths=2 vdisks=2
            #
            # hdisk0          xfer:  %tm_act      bps      tps      bread      bwrtn
            #                          0.0      0.8      0.0        0.0        0.8
            #                read:      rps  avgserv  minserv  maxserv   timeouts      fails
            #                          0.0      2.5      0.3     12.4           0          0
            #               write:      wps  avgserv  minserv  maxserv   timeouts      fails
            #                          0.0      0.3      0.2      0.7           0          0
            #               queue:  avgtime  mintime  maxtime  avgwqsz    avgsqsz     sqfull
            #                          0.3      0.0      5.3      0.0        0.0         0.0
            # --------------------------------------------------------------------------------
            if not line or line.startswith("System") or line.startswith("-----------"):
                continue

            if not re.match(r"\s", line):
                # have new disk
                dsk_comps = line.split(":")
                dsk_firsts = dsk_comps[0].split()
                disk_name = dsk_firsts[0]
                disk_mode = dsk_firsts[1]
                fields = dsk_comps[1].split()
                ret[disk_name] = []

                procn = len(ret[disk_name])
                ret[disk_name].append({})
                ret[disk_name][procn][disk_mode] = {}
                continue

            if ":" in line:
                comps = line.split(":")
                fields = comps[1].split()
                disk_mode = comps[0].lstrip()
                procn = len(ret[disk_name])
                ret[disk_name].append({})
                ret[disk_name][procn][disk_mode] = {}
            else:
                comps = line.split()
                for i in range(0, len(fields)):
                    if len(comps) > i:
                        ret[disk_name][procn][disk_mode][fields[i]] = comps[i]

        return ret

    # dict that return a function that does the right thing per platform
    get_version = {
        "Linux": linux_diskstats,
        "FreeBSD": generic_diskstats,
        "SunOS": generic_diskstats,
        "AIX": aix_diskstats,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def diskusage(*args):
    """
    Return the disk usage for this minion

    Usage::

        salt '*' status.diskusage [paths and/or filesystem types]

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskusage         # usage for all filesystems
        salt '*' status.diskusage / /tmp  # usage for / and /tmp
        salt '*' status.diskusage ext?    # usage for ext[234] filesystems
        salt '*' status.diskusage / ext?  # usage for / and all ext filesystems
    """
    selected = set()
    fstypes = set()
    if not args:
        # select all filesystems
        fstypes.add("*")
    else:
        for arg in args:
            if arg.startswith("/"):
                # select path
                selected.add(arg)
            else:
                # select fstype
                fstypes.add(arg)

    if fstypes:
        # determine which mount points host the specified fstypes
        regex = re.compile(
            "|".join(fnmatch.translate(fstype).format("(%s)") for fstype in fstypes)
        )
        # ifile source of data varies with OS, otherwise all the same
        if __grains__["kernel"] == "Linux":
            try:
                with salt.utils.files.fopen("/proc/mounts", "r") as fp_:
                    ifile = salt.utils.stringutils.to_unicode(fp_.read()).splitlines()
            except OSError:
                return {}
        elif __grains__["kernel"] in ("FreeBSD", "SunOS"):
            ifile = __salt__["cmd.run"]("mount -p").splitlines()
        else:
            raise CommandExecutionError(
                "status.diskusage not yet supported on this platform"
            )

        for line in ifile:
            comps = line.split()
            if __grains__["kernel"] == "SunOS":
                if len(comps) >= 4:
                    mntpt = comps[2]
                    fstype = comps[3]
                    if regex.match(fstype):
                        selected.add(mntpt)
            else:
                if len(comps) >= 3:
                    mntpt = comps[1]
                    fstype = comps[2]
                    if regex.match(fstype):
                        selected.add(mntpt)

    # query the filesystems disk usage
    ret = {}
    for path in selected:
        fsstats = os.statvfs(path)
        blksz = fsstats.f_bsize
        available = fsstats.f_bavail * blksz
        total = fsstats.f_blocks * blksz
        ret[path] = {"available": available, "total": total}
    return ret


def vmstats():
    """
    .. versionchanged:: 2016.3.2
        Return the virtual memory stats for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.vmstats
    """

    def linux_vmstats():
        """
        linux specific implementation of vmstats
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/vmstat", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split()
                ret[comps[0]] = _number(comps[1])
        return ret

    def generic_vmstats():
        """
        generic implementation of vmstats
        note: works on FreeBSD, SunOS and OpenBSD (possibly others)
        """
        ret = {}
        for line in __salt__["cmd.run"]("vmstat -s").splitlines():
            comps = line.split()
            if comps[0].isdigit():
                ret[" ".join(comps[1:])] = _number(comps[0].strip())
        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_vmstats,
        "FreeBSD": generic_vmstats,
        "OpenBSD": generic_vmstats,
        "SunOS": generic_vmstats,
        "AIX": generic_vmstats,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def nproc():
    """
    Return the number of processing units available on this system

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for Darwin, FreeBSD and OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.nproc
    """

    def linux_nproc():
        """
        linux specific implementation of nproc
        """
        try:
            return _number(__salt__["cmd.run"]("nproc").strip())
        except ValueError:
            return 0

    def generic_nproc():
        """
        generic implementation of nproc
        """
        ncpu_data = __salt__["sysctl.get"]("hw.ncpu")
        if not ncpu_data:
            # We need at least one CPU to run
            return 1
        else:
            return _number(ncpu_data)

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_nproc,
        "Darwin": generic_nproc,
        "FreeBSD": generic_nproc,
        "OpenBSD": generic_nproc,
        "AIX": _aix_nproc,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def netstats():
    """
    Return the network stats for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.netstats
    """

    def linux_netstats():
        """
        linux specific netstats implementation
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/net/netstat", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            headers = [""]
            for line in stats.splitlines():
                if not line:
                    continue
                comps = line.split()
                if comps[0] == headers[0]:
                    index = len(headers) - 1
                    row = {}
                    for field in range(index):
                        if field < 1:
                            continue
                        else:
                            row[headers[field]] = _number(comps[field])
                    rowname = headers[0].replace(":", "")
                    ret[rowname] = row
                else:
                    headers = comps
        return ret

    def freebsd_netstats():
        return bsd_netstats()

    def bsd_netstats():
        """
        bsd specific netstats implementation
        """
        ret = {}
        for line in __salt__["cmd.run"]("netstat -s").splitlines():
            if line.startswith("\t\t"):
                continue  # Skip, too detailed
            if not line.startswith("\t"):
                key = line.split()[0].replace(":", "")
                ret[key] = {}
            else:
                comps = line.split()
                if comps[0].isdigit():
                    ret[key][" ".join(comps[1:])] = comps[0]
        return ret

    def sunos_netstats():
        """
        sunos specific netstats implementation
        """
        ret = {}
        for line in __salt__["cmd.run"]("netstat -s").splitlines():
            line = line.replace("=", " = ").split()
            if len(line) > 6:
                line.pop(0)
            if "=" in line:
                if len(line) >= 3:
                    if line[2].isdigit() or line[2][0] == "-":
                        line[2] = _number(line[2])
                    ret[line[0]] = line[2]
                if len(line) >= 6:
                    if line[5].isdigit() or line[5][0] == "-":
                        line[5] = _number(line[5])
                    ret[line[3]] = line[5]
        return ret

    def aix_netstats():
        """
        AIX specific netstats implementation
        """
        ret = {}
        fields = []
        procn = None
        proto_name = None
        for line in __salt__["cmd.run"]("netstat -s").splitlines():
            if not line:
                continue

            if not re.match(r"\s", line) and ":" in line:
                comps = line.split(":")
                proto_name = comps[0]
                ret[proto_name] = []
                procn = len(ret[proto_name])
                ret[proto_name].append({})
                continue
            else:
                comps = line.split()
                comps[0] = comps[0].strip()
                if comps[0].isdigit():
                    ret[proto_name][procn][" ".join(comps[1:])] = _number(comps[0])
                else:
                    continue

        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_netstats,
        "FreeBSD": bsd_netstats,
        "OpenBSD": bsd_netstats,
        "SunOS": sunos_netstats,
        "AIX": aix_netstats,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def netdev():
    """
    .. versionchanged:: 2016.3.2
        Return the network device stats for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.netdev
    """

    def linux_netdev():
        """
        linux specific implementation of netdev
        """
        ret = {}
        try:
            with salt.utils.files.fopen("/proc/net/dev", "r") as fp_:
                stats = salt.utils.stringutils.to_unicode(fp_.read())
        except IOError:
            pass
        else:
            for line in stats.splitlines():
                if not line:
                    continue
                if line.find(":") < 0:
                    continue
                comps = line.split()
                # Fix lines like eth0:9999..'
                comps[0] = line.split(":")[0].strip()
                # Support lines both like eth0:999 and eth0: 9999
                comps.insert(1, line.split(":")[1].strip().split()[0])
                ret[comps[0]] = {
                    "iface": comps[0],
                    "rx_bytes": _number(comps[2]),
                    "rx_compressed": _number(comps[8]),
                    "rx_drop": _number(comps[5]),
                    "rx_errs": _number(comps[4]),
                    "rx_fifo": _number(comps[6]),
                    "rx_frame": _number(comps[7]),
                    "rx_multicast": _number(comps[9]),
                    "rx_packets": _number(comps[3]),
                    "tx_bytes": _number(comps[10]),
                    "tx_carrier": _number(comps[16]),
                    "tx_colls": _number(comps[15]),
                    "tx_compressed": _number(comps[17]),
                    "tx_drop": _number(comps[13]),
                    "tx_errs": _number(comps[12]),
                    "tx_fifo": _number(comps[14]),
                    "tx_packets": _number(comps[11]),
                }
        return ret

    def freebsd_netdev():
        """
        freebsd specific implementation of netdev
        """
        _dict_tree = lambda: collections.defaultdict(_dict_tree)
        ret = _dict_tree()
        netstat = __salt__["cmd.run"]("netstat -i -n -4 -b -d").splitlines()
        netstat += __salt__["cmd.run"]("netstat -i -n -6 -b -d").splitlines()[1:]
        header = netstat[0].split()
        for line in netstat[1:]:
            comps = line.split()
            for i in range(4, 13):  # The columns we want
                ret[comps[0]][comps[2]][comps[3]][header[i]] = _number(comps[i])
        return ret

    def sunos_netdev():
        """
        sunos specific implementation of netdev
        """
        ret = {}
        ##NOTE: we cannot use hwaddr_interfaces here, so we grab both ip4 and ip6
        for dev in __grains__["ip4_interfaces"].keys() + __grains__["ip6_interfaces"]:
            # fetch device info
            netstat_ipv4 = __salt__["cmd.run"](
                "netstat -i -I {dev} -n -f inet".format(dev=dev)
            ).splitlines()
            netstat_ipv6 = __salt__["cmd.run"](
                "netstat -i -I {dev} -n -f inet6".format(dev=dev)
            ).splitlines()

            # prepare data
            netstat_ipv4[0] = netstat_ipv4[0].split()
            netstat_ipv4[1] = netstat_ipv4[1].split()
            netstat_ipv6[0] = netstat_ipv6[0].split()
            netstat_ipv6[1] = netstat_ipv6[1].split()

            # add data
            ret[dev] = {}
            for i in range(len(netstat_ipv4[0]) - 1):
                if netstat_ipv4[0][i] == "Name":
                    continue
                if netstat_ipv4[0][i] in ["Address", "Net/Dest"]:
                    ret[dev][
                        "IPv4 {field}".format(field=netstat_ipv4[0][i])
                    ] = netstat_ipv4[1][i]
                else:
                    ret[dev][netstat_ipv4[0][i]] = _number(netstat_ipv4[1][i])
            for i in range(len(netstat_ipv6[0]) - 1):
                if netstat_ipv6[0][i] == "Name":
                    continue
                if netstat_ipv6[0][i] in ["Address", "Net/Dest"]:
                    ret[dev][
                        "IPv6 {field}".format(field=netstat_ipv6[0][i])
                    ] = netstat_ipv6[1][i]
                else:
                    ret[dev][netstat_ipv6[0][i]] = _number(netstat_ipv6[1][i])

        return ret

    def aix_netdev():
        """
        AIX specific implementation of netdev
        """
        ret = {}
        fields = []
        procn = None
        for dev in (
            __grains__["ip4_interfaces"].keys() + __grains__["ip6_interfaces"].keys()
        ):
            # fetch device info
            # root@la68pp002_pub:/opt/salt/lib/python2.7/site-packages/salt/modules# netstat -i -n -I en0 -f inet6
            # Name  Mtu   Network     Address            Ipkts Ierrs    Opkts Oerrs  Coll
            # en0   1500  link#3      e2.eb.32.42.84.c 10029668     0   446490     0     0
            # en0   1500  172.29.128  172.29.149.95    10029668     0   446490     0     0
            # root@la68pp002_pub:/opt/salt/lib/python2.7/site-packages/salt/modules# netstat -i -n -I en0 -f inet6
            # Name  Mtu   Network     Address            Ipkts Ierrs    Opkts Oerrs  Coll
            # en0   1500  link#3      e2.eb.32.42.84.c 10029731     0   446499     0     0

            netstat_ipv4 = __salt__["cmd.run"](
                "netstat -i -n -I {dev} -f inet".format(dev=dev)
            ).splitlines()
            netstat_ipv6 = __salt__["cmd.run"](
                "netstat -i -n -I {dev} -f inet6".format(dev=dev)
            ).splitlines()

            # add data
            ret[dev] = []

            for line in netstat_ipv4:
                if line.startswith("Name"):
                    fields = line.split()
                    continue

                comps = line.split()
                if len(comps) < 3:
                    raise CommandExecutionError(
                        "Insufficent data returned by command to process '{0}'".format(
                            line
                        )
                    )

                if comps[2].startswith("link"):
                    continue

                procn = len(ret[dev])
                ret[dev].append({})
                ret[dev][procn]["ipv4"] = {}
                for i in range(1, len(fields)):
                    if len(comps) > i:
                        ret[dev][procn]["ipv4"][fields[i]] = comps[i]

            for line in netstat_ipv6:
                if line.startswith("Name"):
                    fields = line.split()
                    continue

                comps = line.split()
                if len(comps) < 3:
                    raise CommandExecutionError(
                        "Insufficent data returned by command to process '{0}'".format(
                            line
                        )
                    )

                if comps[2].startswith("link"):
                    continue

                procn = len(ret[dev])
                ret[dev].append({})
                ret[dev][procn]["ipv6"] = {}
                for i in range(1, len(fields)):
                    if len(comps) > i:
                        ret[dev][procn]["ipv6"][fields[i]] = comps[i]

        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_netdev,
        "FreeBSD": freebsd_netdev,
        "SunOS": sunos_netdev,
        "AIX": aix_netdev,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def w():  # pylint: disable=C0103
    """
    Return a list of logged in users for this minion, using the w command

    CLI Example:

    .. code-block:: bash

        salt '*' status.w
    """

    def linux_w():
        """
        Linux specific implementation for w
        """
        user_list = []
        users = __salt__["cmd.run"]("w -fh").splitlines()
        for row in users:
            if not row:
                continue
            comps = row.split()
            rec = {
                "idle": comps[3],
                "jcpu": comps[4],
                "login": comps[2],
                "pcpu": comps[5],
                "tty": comps[1],
                "user": comps[0],
                "what": " ".join(comps[6:]),
            }
            user_list.append(rec)
        return user_list

    def bsd_w():
        """
        Generic BSD implementation for w
        """
        user_list = []
        users = __salt__["cmd.run"]("w -h").splitlines()
        for row in users:
            if not row:
                continue
            comps = row.split()
            rec = {
                "from": comps[2],
                "idle": comps[4],
                "login": comps[3],
                "tty": comps[1],
                "user": comps[0],
                "what": " ".join(comps[5:]),
            }
            user_list.append(rec)
        return user_list

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Darwin": bsd_w,
        "FreeBSD": bsd_w,
        "Linux": linux_w,
        "OpenBSD": bsd_w,
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def all_status():
    """
    Return a composite of all status data and info for this minion.
    Warning: There is a LOT here!

    CLI Example:

    .. code-block:: bash

        salt '*' status.all_status
    """
    return {
        "cpuinfo": cpuinfo(),
        "cpustats": cpustats(),
        "diskstats": diskstats(),
        "diskusage": diskusage(),
        "loadavg": loadavg(),
        "meminfo": meminfo(),
        "netdev": netdev(),
        "netstats": netstats(),
        "uptime": uptime(),
        "vmstats": vmstats(),
        "w": w(),
    }


def pid(sig):
    """
    Return the PID or an empty string if the process is running or not.
    Pass a signature to use to find the process via ps.  Note you can pass
    a Python-compatible regular expression to return all pids of
    processes matching the regexp.

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.pid <sig>
    """

    cmd = __grains__["ps"]
    output = __salt__["cmd.run_stdout"](cmd, python_shell=True)

    pids = ""
    for line in output.splitlines():
        if "status.pid" in line:
            continue
        if re.search(sig, line):
            if pids:
                pids += "\n"
            pids += line.split()[1]

    return pids


def version():
    """
    Return the system version for this minion

    .. versionchanged:: 2016.11.4
        Added support for AIX

    .. versionchanged:: 2018.3.0
        Added support for OpenBSD

    CLI Example:

    .. code-block:: bash

        salt '*' status.version
    """

    def linux_version():
        """
        linux specific implementation of version
        """
        try:
            with salt.utils.files.fopen("/proc/version", "r") as fp_:
                return salt.utils.stringutils.to_unicode(fp_.read()).strip()
        except IOError:
            return {}

    def bsd_version():
        """
        bsd specific implementation of version
        """
        return __salt__["cmd.run"]("sysctl -n kern.version")

    # dict that returns a function that does the right thing per platform
    get_version = {
        "Linux": linux_version,
        "FreeBSD": bsd_version,
        "OpenBSD": bsd_version,
        "AIX": lambda: __salt__["cmd.run"]("oslevel -s"),
    }

    errmsg = "This method is unsupported on the current operating system!"
    return get_version.get(__grains__["kernel"], lambda: errmsg)()


def master(master=None, connected=True):
    """
    .. versionadded:: 2014.7.0

    Return the connection status with master. Fire an event if the
    connection to master is not as expected. This function is meant to be
    run via a scheduled job from the minion. If master_ip is an FQDN/Hostname,
    it must be resolvable to a valid IPv4 address.

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    """
    master_ips = None

    if master:
        master_ips = salt.utils.network.host_to_ips(master)

    if not master_ips:
        return

    master_connection_status = False
    port = __salt__["config.get"]("publish_port", default=4505)
    connected_ips = salt.utils.network.remote_port_tcp(port)

    # Get connection status for master
    for master_ip in master_ips:
        if master_ip in connected_ips:
            master_connection_status = True
            break

    # Connection to master is not as expected
    if master_connection_status is not connected:
        with salt.utils.event.get_event("minion", opts=__opts__, listen=False) as event:
            if master_connection_status:
                event.fire_event(
                    {"master": master}, salt.minion.master_event(type="connected")
                )
            else:
                event.fire_event(
                    {"master": master}, salt.minion.master_event(type="disconnected")
                )

    return master_connection_status


def ping_master(master):
    """
    .. versionadded:: 2016.3.0

    Sends ping request to the given master. Fires '__master_failback' event on success.
    Returns bool result.

    CLI Example:

    .. code-block:: bash

        salt '*' status.ping_master localhost
    """
    if master is None or master == "":
        return False

    opts = copy.deepcopy(__opts__)
    opts["master"] = master
    if "master_ip" in opts:  # avoid 'master ip changed' warning
        del opts["master_ip"]
    opts.update(salt.minion.prep_ip_port(opts))
    try:
        opts.update(salt.minion.resolve_dns(opts, fallback=False))
    except Exception:  # pylint: disable=broad-except
        return False

    timeout = opts.get("auth_timeout", 60)
    load = {"cmd": "ping"}

    result = False
    with salt.transport.client.ReqChannel.factory(opts, crypt="clear") as channel:
        try:
            payload = channel.send(load, tries=0, timeout=timeout)
            result = True
        except Exception as e:  # pylint: disable=broad-except
            pass

        if result:
            with salt.utils.event.get_event(
                "minion", opts=__opts__, listen=False
            ) as event:
                event.fire_event(
                    {"master": master}, salt.minion.master_event(type="failback")
                )

        return result


def proxy_reconnect(proxy_name, opts=None):
    """
    Forces proxy minion reconnection when not alive.

    proxy_name
        The virtual name of the proxy module.

    opts: None
        Opts dictionary. Not intended for CLI usage.

    CLI Example:

        salt '*' status.proxy_reconnect rest_sample
    """

    if not opts:
        opts = __opts__

    if "proxy" not in opts:
        return False  # fail

    proxy_keepalive_fn = proxy_name + ".alive"
    if proxy_keepalive_fn not in __proxy__:
        return False  # fail

    is_alive = __proxy__[proxy_keepalive_fn](opts)
    if not is_alive:
        minion_id = opts.get("proxyid", "") or opts.get("id", "")
        log.info("%s (%s proxy) is down. Restarting.", minion_id, proxy_name)
        __proxy__[proxy_name + ".shutdown"](opts)  # safely close connection
        __proxy__[proxy_name + ".init"](opts)  # reopen connection
        log.debug("Restarted %s (%s proxy)!", minion_id, proxy_name)

    return True  # success


def time_(format="%A, %d. %B %Y %I:%M%p"):
    """
    .. versionadded:: 2016.3.0

    Return the current time on the minion,
    formatted based on the format parameter.

    Default date format: Monday, 27. July 2015 07:55AM

    CLI Example:

    .. code-block:: bash

        salt '*' status.time

        salt '*' status.time '%s'

    """

    dt = datetime.datetime.today()
    return dt.strftime(format)
