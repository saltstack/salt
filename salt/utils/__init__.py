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
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                import win32api
                executablepath = sys.executable
                pypath = executablepath.split('\\')
                win32api.ShellExecute(
                    0,
                    'runas',
                    executablepath, 
                    os.path.join(pypath[0], os.sep, pypath[1], 'Lib\\site-packages\\salt\\utils\\saltminionservice.py'),
                    os.path.join(pypath[0], os.sep, pypath[1]),
                    0 )
                sys.exit(0)
            else:
                import saltminionservice
                import win32serviceutil
                import win32service
                import winerror
                servicename = 'salt-minion'
                try:
                    status = win32serviceutil.QueryServiceStatus(servicename)
                except win32service.error, details:
                    if details[0]==winerror.ERROR_SERVICE_DOES_NOT_EXIST:
                        saltminionservice.instart(saltminionservice.MinionService, servicename, 'Salt Minion')
                        sys.exit(0)
                if status[1] == win32service.SERVICE_RUNNING:
                    win32serviceutil.StopServiceWithDeps(servicename)
                    win32serviceutil.StartService(servicename)
                else:
                    win32serviceutil.StartService(servicename)
                sys.exit(0)
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

def which(exe=None):
    '''
    Python clone of POSIX's /usr/bin/which
    '''
    if exe:
        (path, name) = os.path.split(exe)
        if os.access(exe, os.X_OK):
            return exe
        for path in os.environ.get('PATH').split(os.pathsep):
            full_path = os.path.join(path, exe)
            if os.access(full_path, os.X_OK):
                return full_path
    return None

def list_files(directory):
    '''
    Return a list of all files found under directory
    '''
    ret = set()
    ret.add(directory)
    for root, dirs, files in os.walk(directory):
        for name in files:
            ret.add(os.path.join(root, name))
        for name in dirs:
            ret.add(os.path.join(root, name))

    return list(ret)

