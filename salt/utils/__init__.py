'''
Some of the utils used by salt
'''
from __future__ import absolute_import

# Import Python libs
import os
import re
import imp
import random
import sys
import socket
import logging
import inspect
import hashlib
import datetime
import tempfile
import shlex
import shutil
import subprocess
import time
import platform
from calendar import month_abbr as months

# Import Salt libs
import salt.minion
import salt.payload
from salt.exceptions import SaltClientError, CommandNotFoundError


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


def _getargs(func):
    '''
    A small wrapper around getargspec that also supports callable classes
    '''
    if not callable(func):
        raise TypeError('{0} is not a callable'.format(func))

    if inspect.isfunction(func):
        aspec = inspect.getargspec(func)
    elif inspect.ismethod(func):
        aspec = inspect.getargspec(func)
        del aspec.args[0] # self
    elif isinstance(func, object):
        aspec = inspect.getargspec(func.__call__)
        del aspec.args[0]  # self
    else:
        raise TypeError("Cannot inspect argument list for '{0}'".format(func))

    return aspec


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
        # Non-existent file or permission denied to the parent dir
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

    try:
        fileno = sys.stdout.fileno()
    except AttributeError:
        fileno = -1  # sys.stdout is StringIO or fake

    if not use or not os.isatty(fileno):
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
    except OSError as exc:
        msg = 'fork #1 failed: {0} ({1})'.format(exc.errno, exc.strerror)
        logging.getLogger(__name__).error(msg)
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
        logging.getLogger(__name__).error(msg.format(exc.errno, exc.strerror))
        sys.exit(1)

    # A normal daemonization redirects the process output to /dev/null.
    # Unfortunately when a python multiprocess is called the output is
    # not cleanly redirected and the parent process dies when the
    # multiprocessing process attempts to access stdout or err.
    #dev_null = open('/dev/null', 'rw')
    #os.dup2(dev_null.fileno(), sys.stdin.fileno())
    #os.dup2(dev_null.fileno(), sys.stdout.fileno())
    #os.dup2(dev_null.fileno(), sys.stderr.fileno())


def daemonize_if(opts, **kwargs):
    '''
    Daemonize a module function process if multiprocessing is True and the
    process is not being called by salt-call
    '''
    if 'salt-call' in sys.argv[0]:
        return
    if not opts['multiprocessing']:
        return
    if sys.platform.startswith('win'):
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

        # default path based on busybox's default
        default_path = "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin"

        for path in os.environ.get('PATH', default_path).split(os.pathsep):
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
                    logging.getLogger(__name__).error(err)
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


def prep_jid(cachedir, sum_type, user='root'):
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
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    '''
    if command is None:
        raise CommandNotFoundError("'None' is not a valid command.")

    import salt.modules.cmdmod
    __salt__ = {'cmd.has_exec': salt.modules.cmdmod.has_exec}

    if not __salt__['cmd.has_exec'](command):
        raise CommandNotFoundError(command)


def copyfile(source, dest, backup_mode='', cachedir=''):
    '''
    Copy files from a source to a destination in an atomic way, and if
    specified cache the file.
    '''
    if not os.path.isfile(source):
        raise IOError(
                '[Errno 2] No such file or directory: {0}'.format(source)
                )
    if not os.path.isdir(os.path.dirname(dest)):
        raise IOError(
                '[Errno 2] No such file or directory: {0}'.format(source)
                )
    bname = os.path.basename(dest)
    dname = os.path.dirname(os.path.abspath(dest))
    fd_, tgt = tempfile.mkstemp(prefix=bname, dir=dname)
    os.close(fd_)
    shutil.copyfile(source, tgt)
    mask = os.umask(0)
    os.umask(mask)
    os.chmod(tgt, 0666 - mask)
    bkroot = ''
    if cachedir:
        bkroot = os.path.join(cachedir, 'file_backup')
    if backup_mode == 'minion' or backup_mode == 'both' and bkroot:
        if os.path.exists(dest):
            fstat = os.stat(dest)
            msecs = str(int(time.time() * 1000000))[-6:]
            stamp = time.asctime().replace(' ', '_')
            stamp = '{0}{1}_{2}'.format(stamp[:-4], msecs, stamp[-4:])
            bkpath = os.path.join(
                    bkroot,
                    dname[1:],
                    '{0}_{1}'.format(bname, stamp)
                    )
            if not os.path.isdir(os.path.dirname(bkpath)):
                os.makedirs(os.path.dirname(bkpath))
            shutil.copyfile(dest, bkpath)
            os.chown(bkpath, fstat.st_uid, fstat.st_gid)
    if backup_mode == 'master' or backup_mode == 'both' and bkroot:
        # TODO, backup to master
        pass
    try:
        shutil.move(tgt, dest)
        # If SELINUX is available run a restorecon on the file
        rcon = which('restorecon')
        if rcon:
            cmd = [rcon, dest]
            subprocess.call(cmd)
    except Exception:
        pass
    if os.path.isfile(tgt):
        # The temp file failed to move
        try:
            os.remove(tgt)
        except Exception:
            pass


def path_join(*parts):
    '''
    This functions tries to solve some issues when joining multiple absolute
    paths on both *nix and windows platforms.

    See tests/unit/utils/path_join_test.py for some examples on what's being
    talked about here.
    '''
    # Normalize path converting any os.sep as needed
    parts = [os.path.normpath(p) for p in parts]

    root = parts.pop(0)
    if not parts:
        return root

    if platform.system().lower() == 'windows':
        if len(root) == 1:
            root += ':'
        root = root.rstrip(os.sep) + os.sep

    return os.path.normpath(os.path.join(
        root, *[p.lstrip(os.sep) for p in parts]
    ))


def pem_finger(path, sum_type='md5'):
    '''
    Pass in the location of a pem file and the type of cryptographic hash to
    use. The default is md5.
    '''
    if not os.path.isfile(path):
        return ''
    with open(path, 'rb') as fp_:
        key = ''.join(fp_.readlines()[1:-1])
    pre = getattr(hashlib, sum_type)(key).hexdigest()
    finger = ''
    for ind in range(len(pre)):
        if ind % 2:
            # Is odd
            finger += '{0}:'.format(pre[ind])
        else:
            finger += pre[ind]
    return finger.rstrip(':')


def build_whitepace_splited_regex(text):
    '''
    Create a regular expression at runtime which should match ignoring the
    addition or deletion of white space or line breaks, unless between commas

    Example::

    >>> import re
    >>> from salt.utils import *
    >>> regex = build_whitepace_splited_regex(
    ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
    ... )

    >>> regex
    '(?:[\\s]+)?if(?:[\\s]+)?\\[(?:[\\s]+)?\\-z(?:[\\s]+)?\\"\\$debian'
    '\\_chroot\\"(?:[\\s]+)?\\](?:[\\s]+)?\\&\\&(?:[\\s]+)?\\[(?:[\\s]+)?'
    '\\-r(?:[\\s]+)?\\/etc\\/debian\\_chroot(?:[\\s]+)?\\]\\;(?:[\\s]+)?'
    'then(?:[\\s]+)?'
    >>> re.search(
    ...     regex,
    ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
    ... )

    <_sre.SRE_Match object at 0xb70639c0>
    >>>

    '''
    def __build_parts(text):
        lexer = shlex.shlex(text)
        lexer.whitespace_split = True
        lexer.commenters = ''
        if '\'' in text:
            lexer.quotes = '"'
        elif '"' in text:
            lexer.quotes = '\''
        return list(lexer)

    regex = r''
    for line in text.splitlines():
        parts = [re.escape(s) for s in __build_parts(line)]
        regex += r'(?:[\s]+)?{0}(?:[\s]+)?'.format(r'(?:[\s]+)?'.join(parts))
    return regex


def format_call(fun, data):
    '''
    Pass in a function and a dict containing arguments to the function.

    A dict with the keys args and kwargs is returned
    '''
    ret = {}
    ret['args'] = []
    aspec = _getargs(fun)
    arglen = 0
    deflen = 0
    if isinstance(aspec.args, list):
        arglen = len(aspec.args)
    if isinstance(aspec.defaults, tuple):
        deflen = len(aspec.defaults)
    if aspec.keywords:
        # This state accepts kwargs
        ret['kwargs'] = {}
        for key in data:
            # Passing kwargs the conflict with args == stack trace
            if key in aspec.args:
                continue
            ret['kwargs'][key] = data[key]
    kwargs = {}
    for ind in range(arglen - 1, 0, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            kwargs[aspec.args[ind]] = aspec.defaults[-minus]
    for arg in kwargs:
        if arg in data:
            kwargs[arg] = data[arg]
    for arg in aspec.args:
        if arg in kwargs:
            ret['args'].append(kwargs[arg])
        else:
            ret['args'].append(data[arg])
    return ret


def arg_lookup(fun):
    '''
    Return a dict containing the arguments and default arguments to the function
    '''
    ret = {'args': [],
           'kwargs': {}}
    aspec = _getargs(fun)
    arglen = 0
    deflen = 0
    if isinstance(aspec[0], list):
        arglen = len(aspec[0])
    if isinstance(aspec[3], tuple):
        deflen = len(aspec[3])
    for ind in range(arglen - 1, 0, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            ret['kwargs'][aspec[0][ind]] = aspec[3][-minus]
    for arg in aspec[0]:
        if arg in ret:
            continue
        else:
            ret['args'].append(arg)
    return ret

