# -*- coding: utf-8 -*-
'''
Version agnostic psutil hack to fully support both old (<2.0) and new (>=2.0) psutil versions.
The old <1.0 psutil API is dropped in psutil 3.0

Should be removed once support for psutil <2.0 is dropped. (eg RHEL 6)

Built off of http://grodola.blogspot.com/2014/01/psutil-20-porting.html
'''

from __future__ import absolute_import

# No exception handling, as we want ImportError if psutil doesn't exist
import psutil

if psutil.version_info >= (2, 0):
    from psutil import *
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

    # Alias new module functions
    def boot_time():
        return psutil.BOOT_TIME
    
    def cpu_count():
        return psutil.NUM_CPUS
    
    # Alias renamed module functions
    pids = psutil.get_pid_list
    users = psutil.get_users

    # Alias renamed Process functions
    _PROCESS_FUNCTION_MAP = { 
        "children": "get_children",
        "connections": "get_connections",
        "cpu_affinity": "get_cpu_affinity",
        "cpu_percent": "get_cpu_percent",
        "cpu_times": "get_cpu_times",
        "io_counters": "get_io_counters",
        "ionice": "get_ionice",
        "memory_info": "get_memory_info",
        "memory_info_ex": "get_ext_memory_info",
        "memory_maps": "get_memory_maps",
        "memory_percent": "get_memory_percent",
        "nice": "get_nice",
        "num_ctx_switches": "get_num_ctx_switches",
        "num_fds": "get_num_fds",
        "num_threads": "get_num_threads",
        "open_files": "get_open_files",
        "rlimit": "get_rlimit",
        "threads": "get_threads",
        "cwd": "getcwd",

        "cpu_affinity": "set_cpu_affinity",
        "ionice": "set_ionice",
        "nice": "set_nice",
        "rlimit": "set_rlimit",
    }

    for new, old in _PROCESS_FUNCTION_MAP.iteritems():
        try:
            setattr(Process, new, psutil.Process.__dict__[old])
        except KeyError:
            pass

