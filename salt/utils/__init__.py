'''
Some of the utils used by salt
'''

from calendar import month_abbr as months
import logging
import os
import socket
import sys

from salt.exceptions import SaltClientError


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


def is_empty(filename):
    '''
    Is a file empty?
    '''
    try:
        return os.stat(filename).st_size == 0
    except OSError:
        # Non-existant file or permission denied to the parent dir
        return False


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


def append_pid(pidfile):
    '''
    Save the pidfile
    '''
    try:
        open(pidfile, 'a').write('\n{0}'.format(str(os.getpid())))
    except IOError:
        err = ('Failed to commit the pid to location {0}, please verify'
              ' that the location is available').format(pidfile)
        log.error(err)


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
    except OSError as exc:
        msg = 'fork #1 failed: {0} ({1})'.format(exc.errno, exc.strerror)
        log.error(msg)
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(022)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as exc:
        msg = 'fork #2 failed: {0} ({1})'
        log.error(msg.format(exc.errno, exc.strerror))
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


def jid_to_time(jid):
    '''
    Convert a salt job id into the time when the job was invoked
    '''
    jid = str(jid)
    if not len(jid) == 20:
        return ''
    year = jid[:4]
    month = jid[4:6]
    day = jid[6:8]
    hour = jid[8:10]
    minute = jid[10:12]
    second = jid[12:14]
    micro = jid[14:]

    ret = '{0}, {1} {2} {3}:{4}:{5}.{6}'.format(
            year,
            months[int(month)],
            day,
            hour,
            minute,
            second,
            micro
            )
    return ret


def gen_mac(prefix='52:54:'):
    '''
    Generates a mac addr with the defined prefix
    '''
    src = ['1','2','3','4','5','6','7','8','9','0','a','b','c','d','e','f']
    mac = prefix
    while len(mac) < 18:
        if len(mac) < 3:
            mac = random.choice(src) + random.choice(src) + ':'
        if mac.endswith(':'):
            mac += random.choice(src) + random.choice(src) + ':'
    return mac[:-1]


def dns_check(addr, safe=False):
    '''
    Return the ip resolved by dns, but do not exit on failure, only raise an
    exception.
    '''
    try:
        socket.inet_aton(addr)
    except socket.error:
        # Not a valid ip adder, check DNS
        try:
            addr = socket.gethostbyname(addr)
        except socket.gaierror:
            err = ('This master address: {0} was previously resolvable but '
                  'now fails to resolve! The previously resolved ip addr '
                  'will continue to be used').format(addr)
            if safe:
                log.error(err)
                raise SaltClientError
            else:
                err = err.format(addr)
                sys.stderr.write(err)
                sys.exit(42)
    return addr
