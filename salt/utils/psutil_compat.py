# -*- coding: utf-8 -*-
'''
Version agnostic psutil hack to fully support both old (<2.0) and new (>=2.0)
psutil versions.

The old <1.0 psutil API is dropped in psutil 3.0

Should be removed once support for psutil <2.0 is dropped. (eg RHEL 6)

Built off of http://grodola.blogspot.com/2014/01/psutil-20-porting.html
'''

from __future__ import absolute_import

# No exception handling, as we want ImportError if psutil doesn't exist
import psutil

if psutil.version_info >= (2, 0):
    from psutil import *  # pylint: disable=wildcard-import
else:
    # Import hack to work around bugs in old psutil's
    # Psuedo "from psutil import *"
    _globals = globals()
    for attr in psutil.__all__:
        _temp = __import__('psutil', globals(), locals(), [attr], -1)
        try:
            _globals[attr] = getattr(_temp, attr)
        except AttributeError:
            pass

    # Import functions not in __all__
    from psutil import disk_partitions  # pylint: disable=unused-import
    from psutil import disk_usage  # pylint: disable=unused-import

    # Alias new module functions
    def boot_time():
        return psutil.BOOT_TIME

    def cpu_count():
        return psutil.NUM_CPUS

    # Alias renamed module functions
    pids = psutil.get_pid_list
    users = psutil.get_users

    # Deprecated in 1.0.1, but not mentioned in blog post
    if psutil.version_info < (1, 0, 1):
        net_io_counters = psutil.network_io_counters()

    class Process(psutil.Process):  # pylint: disable=no-init
        # Reimplement overloaded getters/setters
        def cpu_affinity(self, *args, **kwargs):
            if args or kwargs:
                return self.set_cpu_affinity(*args, **kwargs)
            else:
                return self.get_cpu_affinity()

        def ionice(self, *args, **kwargs):
            if args or kwargs:
                return self.set_ionice(*args, **kwargs)
            else:
                return self.get_ionice()

        def nice(self, *args, **kwargs):
            if args or kwargs:
                return self.set_nice(*args, **kwargs)
            else:
                return self.get_nice()

        def rlimit(self, *args, **kwargs):
            if args or kwargs:
                return self.set_rlimit(*args, **kwargs)
            else:
                return self.get_rlimit()

    # Alias renamed Process functions
    _PROCESS_FUNCTION_MAP = {
        "children": "get_children",
        "connections": "get_connections",
        "cpu_percent": "get_cpu_percent",
        "cpu_times": "get_cpu_times",
        "io_counters": "get_io_counters",
        "memory_info": "get_memory_info",
        "memory_info_ex": "get_ext_memory_info",
        "memory_maps": "get_memory_maps",
        "memory_percent": "get_memory_percent",
        "num_ctx_switches": "get_num_ctx_switches",
        "num_fds": "get_num_fds",
        "num_threads": "get_num_threads",
        "open_files": "get_open_files",
        "threads": "get_threads",
        "cwd": "getcwd",

    }

    for new, old in _PROCESS_FUNCTION_MAP.iteritems():
        try:
            setattr(Process, new, psutil.Process.__dict__[old])
        except KeyError:
            pass
