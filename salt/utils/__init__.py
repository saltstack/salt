'''
Some of the utils used by salt
'''

import logging
import os
import sys

log = logging.getLogger(__name__)

# Do not use these color declarations, use get_colors()
# These color declarations will be removed in the future
BLACK = '\033[0;30m'
DARK_GRAY = '\033[1;30m'
LIGHT_GRAY = '\033[0;37m'
BLUE = '\033[0;34m'
LIGHT_BLUE = '\033[1;34m'
GREEN = '\033[0;32m'
LIGHT_GREEN = '\033[1;32m'
CYAN = '\033[0;36m'
LIGHT_CYAN = '\033[1;36m'
RED = '\033[0;31m'
LIGHT_RED = '\033[1;31m'
PURPLE = '\033[0;35m'
LIGHT_PURPLE = '\033[1;35m'
BROWN = '\033[0;33m'
YELLOW = '\033[1;33m'
WHITE = '\033[1;37m'
DEFAULT_COLOR = '\033[00m'
RED_BOLD = '\033[01;31m'
ENDC = '\033[0m'


def get_colors(use=True):
    '''
    Return the colors as an easy to use dict, pass False to return the colors
    as empty strings so that they will not be applied
    '''
    colors = {
            'BLACK': '\033[0;30m',
            'DARK_GRAY': '\033[1;30m',
            'LIGHT_GRAY': '\033[0;37m',
            'BLUE': '\033[0;34m',
            'LIGHT_BLUE': '\033[1;34m',
            'GREEN': '\033[0;32m',
            'LIGHT_GREEN': '\033[1;32m',
            'CYAN': '\033[0;36m',
            'LIGHT_CYAN': '\033[1;36m',
            'RED': '\033[0;31m',
            'LIGHT_RED': '\033[1;31m',
            'PURPLE': '\033[0;35m',
            'LIGHT_PURPLE': '\033[1;35m',
            'BROWN': '\033[0;33m',
            'YELLOW': '\033[1;33m',
            'WHITE': '\033[1;37m',
            'DEFAULT_COLOR': '\033[00m',
            'RED_BOLD': '\033[01;31m',
            'ENDC': '\033[0m',
            }

    if not use:
        for color in colors:
            colors[color] = ''

    return colors


def daemonize():
    '''
    Daemonize a process
    '''
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError, e:
        print >> sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(022)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # print "Daemon PID %d" % pid
            sys.exit(0)
    except OSError, e:
        print >> sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    dev_null = open('/dev/null', 'rw')
    os.dup2(dev_null.fileno(), sys.stdin.fileno())
    os.dup2(dev_null.fileno(), sys.stdout.fileno())
    os.dup2(dev_null.fileno(), sys.stderr.fileno())

def profile_func(filename=None):
    '''
    Decorator for adding profiling to a nested function in Salt
    '''
    def proffunc(fun):
        def profiled_func(*args, **kwargs):
            import cProfile
            logging.info('Profiling function {0}'.format(fun.__name__))
            try:
                profiler = cProfile.Profile()
                retval = profiler.runcall(fun, *args, **kwargs)
                profiler.dump_stats((filename or '{0}_func.profile'
                                     .format(fun.__name__)))
            except IOError:
                logging.exception(('Could not open profile file {0}'
                                   .format(filename)))

            return retval
        return profiled_func
    return proffunc
