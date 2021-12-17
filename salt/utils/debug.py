"""
Print a stacktrace when sent a SIGUSR1 for debugging
"""

import inspect
import os
import signal
import sys
import tempfile
import time
import traceback

import salt.utils.files
import salt.utils.stringutils


def _makepretty(printout, stack):
    """
    Pretty print the stack trace and environment information
    for debugging those hard to reproduce user problems.  :)
    """
    printout.write("======== Salt Debug Stack Trace =========\n")
    traceback.print_stack(stack, file=printout)
    printout.write("=========================================\n")


def _handle_sigusr1(sig, stack):
    """
    Signal handler for SIGUSR1, only available on Unix-like systems
    """
    # When running in the foreground, do the right  thing
    # and spit out the debug info straight to the console
    if sys.stderr.isatty():
        output = sys.stderr
        _makepretty(output, stack)
    else:
        filename = "salt-debug-{}.log".format(int(time.time()))
        destfile = os.path.join(tempfile.gettempdir(), filename)
        with salt.utils.files.fopen(destfile, "w") as output:
            _makepretty(output, stack)


def _handle_sigusr2(sig, stack):
    """
    Signal handler for SIGUSR2, only available on Unix-like systems
    """
    try:
        import yappi
    except ImportError:
        return
    if yappi.is_running():
        yappi.stop()
        filename = "callgrind.salt-{}-{}".format(int(time.time()), os.getpid())
        destfile = os.path.join(tempfile.gettempdir(), filename)
        yappi.get_func_stats().save(destfile, type="CALLGRIND")
        if sys.stderr.isatty():
            sys.stderr.write("Saved profiling data to: {}\n".format(destfile))
        yappi.clear_stats()
    else:
        if sys.stderr.isatty():
            sys.stderr.write("Profiling started\n")
        yappi.start()


def enable_sig_handler(signal_name, handler):
    """
    Add signal handler for signal name if it exists on given platform
    """
    if hasattr(signal, signal_name):
        signal.signal(getattr(signal, signal_name), handler)


def enable_sigusr1_handler():
    """
    Pretty print a stack trace to the console or a debug log under /tmp
    when any of the salt daemons such as salt-master are sent a SIGUSR1
    """
    enable_sig_handler("SIGUSR1", _handle_sigusr1)
    # Also canonical BSD-way of printing progress is SIGINFO
    # which on BSD-derivatives can be sent via Ctrl+T
    enable_sig_handler("SIGINFO", _handle_sigusr1)


def enable_sigusr2_handler():
    """
    Toggle YAPPI profiler
    """
    enable_sig_handler("SIGUSR2", _handle_sigusr2)


def inspect_stack():
    """
    Return a string of which function we are currently in.
    """
    return {"co_name": inspect.stack()[1][3]}


def caller_name(skip=2, include_lineno=False):
    """
    Get a name of a caller in the format module.class.method

    `skip` specifies how many levels of stack to skip while getting caller
    name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

    An empty string is returned if skipped levels exceed stack height

    Source: https://gist.github.com/techtonik/2151727
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return ""
    parentframe = stack[start][0]

    name = []
    if include_lineno is True:
        try:
            lineno = inspect.getframeinfo(parentframe).lineno
        except:  # pylint: disable=bare-except
            lineno = None
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    # TODO(techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if "self" in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals["self"].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != "<module>":  # top level usually
        name.append(codename)  # function or a method
    del parentframe
    fullname = ".".join(name)
    if include_lineno and lineno:
        fullname += ":{}".format(lineno)
    return fullname
