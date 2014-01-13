# -*- coding: utf-8 -*-
'''
Print a stacktrace when sent a SIGUSR1 for debugging
'''

# Import python libs
import os
import sys
import time
import signal
import tempfile
import traceback
import inspect

# Import salt libs
import salt.utils


def _makepretty(printout, stack):
    '''
    Pretty print the stack trace and environment information
    for debugging those hard to reproduce user problems.  :)
    '''
    printout.write('======== Salt Debug Stack Trace =========\n')
    traceback.print_stack(stack, file=printout)
    printout.write('=========================================\n')


def _handle_sigusr1(sig, stack):
    '''
    Signal handler for SIGUSR1, only available on Unix-like systems
    '''
    # When running in the foreground, do the right  thing
    # and spit out the debug info straight to the console
    if sys.stderr.isatty():
        output = sys.stderr
        _makepretty(output, stack)
    else:
        filename = 'salt-debug-{0}.log'.format(int(time.time()))
        destfile = os.path.join(tempfile.gettempdir(), filename)
        with salt.utils.fopen(destfile, 'w') as output:
            _makepretty(output, stack)


def enable_sig_handler(signal_name, handler):
    '''
    Add signal handler for signal name if it exists on given platform
    '''
    if hasattr(signal, signal_name):
        signal.signal(getattr(signal, signal_name), handler)


def enable_sigusr1_handler():
    '''
    Pretty print a stack trace to the console or a debug log under /tmp
    when any of the salt daemons such as salt-master are sent a SIGUSR1
    '''
    enable_sig_handler('SIGUSR1', _handle_sigusr1)
    # Also canonical BSD-way of printing profress is SIGINFO
    # which on BSD-deriviatives can be sent via Ctrl+T
    enable_sig_handler('SIGINFO', _handle_sigusr1)


def inspect_stack():
    '''
    Return a string of which function we are currently in.
    '''
    return {'co_name': inspect.stack()[1][3]}
