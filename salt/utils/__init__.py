'''
Some of the utils used by salt
'''
from __future__ import absolute_import

# Import Python libs
import os
import imp
import random
import sys
import socket
import logging
import hashlib
import datetime
from calendar import month_abbr as months

# Import Salt libs
import salt.minion
import salt.payload
from salt.exceptions import SaltClientError, CommandNotFoundError

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


def safe_rm(tgt):
    '''
    Safely remove a file
    '''
    try:
        os.remove(tgt)
    except (IOError, OSError):
        pass


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

    if not use or not os.isatty(sys.stdout.fileno()):
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
                    0)
                sys.exit(0)
            else:
                from . import saltminionservice
                import win32serviceutil
                import win32service
                import winerror
                servicename = 'salt-minion'
                try:
                    status = win32serviceutil.QueryServiceStatus(servicename)
                except win32service.error as details:
                    if details[0] == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
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
    os.umask(18)

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


def daemonize_if(opts, **kwargs):
    '''
    Daemonize a module function process if multiprocessing is True and the
    process is not being called by salt-call
    '''
    if 'salt-call' in sys.argv[0]:
        return
    if not opts['multiprocessing']:
        return
    # Daemonizing breaks the proc dir, so the proc needs to be rewritten
    data = {}
    for key, val in kwargs.items():
        if key.startswith('__pub_'):
            data[key[6:]] = val
    if not 'jid' in data:
        return
    serial = salt.payload.Serial(opts)
    proc_dir = salt.minion.get_proc_dir(opts['cachedir'])
    fn_ = os.path.join(proc_dir, data['jid'])
    daemonize()
    sdata = {'pid': os.getpid()}
    sdata.update(data)
    with open(fn_, 'w+') as f:
        f.write(serial.dumps(sdata))


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


def which_bin(exes):
    '''
    Scan over some possible executables and return the first one that is found
    '''
    if not isinstance(exes, (list, tuple)):
        return None
    for exe in exes:
        path = which(exe)
        if not path:
            continue
        return path


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
    src = ['1', '2', '3', '4', '5', '6', '7', '8',
            '9', '0', 'a', 'b', 'c', 'd', 'e', 'f']
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
            err = ('This master address: \'{0}\' was previously resolvable but '
                  'now fails to resolve! The previously resolved ip addr '
                  'will continue to be used').format(addr)
            if safe:
                import salt.log
                if salt.log.is_console_configured():
                    # If logging is not configured it also means that either
                    # the master or minion instance calling this hasn't even
                    # started running
                    log.error(err)
                raise SaltClientError
            else:
                err = err.format(addr)
                sys.stderr.write(err)
                sys.exit(42)
    return addr


def required_module_list(docstring=None):
    '''
    Return a list of python modules required by a salt module that aren't
    in stdlib and don't exist on the current pythonpath.

    NOTE: this function expects docstring to include something like:
    Required python modules: win32api, win32con, win32security, ntsecuritycon
    '''
    ret = []
    txt = 'Required python modules: '
    data = docstring.split('\n') if docstring else []
    mod_list = list(x for x in data if x.startswith(txt))
    if not mod_list:
        return []
    modules = mod_list[0].replace(txt, '').split(', ')
    for mod in modules:
        try:
            imp.find_module(mod)
        except ImportError:
            ret.append(mod)
    return ret


def required_modules_error(name, docstring):
    '''
    Pretty print error messages in critical salt modules which are
    missing deps not always in stdlib such as win32api on windows.
    '''
    modules = required_module_list(docstring)
    if not modules:
        return ''
    filename = os.path.basename(name).split('.')[0]
    msg = '\'{0}\' requires these python modules: {1}'
    return msg.format(filename, ', '.join(modules))


def prep_jid(cachedir, sum_type):
    '''
    Return a job id and prepare the job id directory
    '''
    jid = "{0:%Y%m%d%H%M%S%f}".format(datetime.datetime.now())

    jid_dir_ = jid_dir(jid, cachedir, sum_type)
    if not os.path.isdir(jid_dir_):
        os.makedirs(jid_dir_)
        with open(os.path.join(jid_dir_, 'jid'), 'w+') as fn_:
            fn_.write(jid)
    else:
        return prep_jid(cachedir, sum_type)
    return jid


def jid_dir(jid, cachedir, sum_type):
    '''
    Return the jid_dir for the given job id
    '''
    jhash = getattr(hashlib, sum_type)(jid).hexdigest()
    return os.path.join(cachedir, 'jobs', jhash[:2], jhash[2:])


def check_or_die(command):
    '''
    Simple convienence function for modules to  use
    for gracefully blowing up if a required tool is
    not available in the system path.

    Lazily import salt.modules.cmdmod to avoid any
    sort of circular dependencies.
    '''
    import salt.modules.cmdmod
    __salt__ = {'cmd.has_exec': salt.modules.cmdmod.has_exec}

    if not __salt__['cmd.has_exec'](command):
        raise CommandNotFoundError(command)
