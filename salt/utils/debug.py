'''
Print a stacktrace when sent a SIGUSR1 for debugging
'''

import os
import sys
import time
import signal
import tempfile
import traceback


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
        with open(destfile, 'w') as output:
            _makepretty(output, stack)


def enable_sigusr1_handler():
    '''
    Pretty print a stack trace to the console or a debug log under /tmp
    when any of the salt daemons such as salt-master are sent a SIGUSR1
    '''
    #  Skip setting up this signal on Windows
    #  SIGUSR1 doesn't exist on Windows and causes the minion to crash
    if 'os' in os.environ and not os.environ['os'].startswith('Windows'):
        signal.signal(signal.SIGUSR1, _handle_sigusr1)
