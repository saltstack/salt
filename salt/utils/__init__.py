# -*- coding: utf-8 -*-
'''
Some of the utils used by salt
'''
from __future__ import absolute_import

# Import python libs
import copy
import datetime
import distutils.version  # pylint: disable=E0611
import fnmatch
import hashlib
import imp
import inspect
import json
import logging
import os
import pprint
import random
import re
import shlex
import shutil
import socket
import stat
import string
import subprocess
import sys
import tempfile
import time
import types
import warnings
import yaml
from calendar import month_abbr as months

try:
    import timelib
    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

try:
    import parsedatetime

    HAS_PARSEDATETIME = True
except ImportError:
    HAS_PARSEDATETIME = False

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on windows
    HAS_FCNTL = False

try:
    import win32api
    HAS_WIN32API = True
except ImportError:
    HAS_WIN32API = False

try:
    import zmq
except ImportError:
    # Running as purely local
    pass

# Import salt libs
import salt._compat
import salt.log
import salt.minion
import salt.payload
import salt.version
from salt._compat import string_types
from salt.utils.decorators import memoize as real_memoize
from salt.exceptions import (
    SaltClientError, CommandNotFoundError, SaltSystemExit, SaltInvocationError
)


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

#KWARG_REGEX = re.compile(r'^([^\d\W][\w-]*)=(?!=)(.*)$', re.UNICODE)  # python 3
KWARG_REGEX = re.compile(r'^([^\d\W][\w-]*)=(?!=)(.*)$')

log = logging.getLogger(__name__)


def get_function_argspec(func):
    '''
    A small wrapper around getargspec that also supports callable classes
    '''
    if not callable(func):
        raise TypeError('{0} is not a callable'.format(func))

    if inspect.isfunction(func):
        aspec = inspect.getargspec(func)
    elif inspect.ismethod(func):
        aspec = inspect.getargspec(func)
        del aspec.args[0]  # self
    elif isinstance(func, object):
        aspec = inspect.getargspec(func.__call__)
        del aspec.args[0]  # self
    else:
        raise TypeError('Cannot inspect argument list for {0!r}'.format(func))

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

    if not use:
        for color in colors:
            colors[color] = ''
    if isinstance(use, str):
        # Try to set all of the colors to the passed color
        if use in colors:
            for color in colors:
                colors[color] = colors[use]

    return colors


def get_context(template, line, num_lines=5, marker=None):
    '''
    Returns debugging context around a line in a given string

    Returns:: string
    '''
    template_lines = template.splitlines()
    num_template_lines = len(template_lines)

    # in test, a single line template would return a crazy line number like,
    # 357.  do this sanity check and if the given line is obviously wrong, just
    # return the entire template
    if line > num_template_lines:
        return template

    context_start = max(0, line - num_lines - 1)  # subt 1 for 0-based indexing
    context_end = min(num_template_lines, line + num_lines)
    error_line_in_context = line - context_start - 1  # subtr 1 for 0-based idx

    buf = []
    if context_start > 0:
        buf.append('[...]')
        error_line_in_context += 1

    buf.extend(template_lines[context_start:context_end])

    if context_end < num_template_lines:
        buf.append('[...]')

    if marker:
        buf[error_line_in_context] += marker

    # warning: jinja content may contain unicode strings
    # instead of utf-8.
    buf = [i.encode('UTF-8') if isinstance(i, unicode) else i for i in buf]

    return '---\n{0}\n---'.format('\n'.join(buf))


def daemonize(redirect_out=True):
    '''
    Daemonize a process
    '''
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as exc:
        log.error(
            'fork #1 failed: {0} ({1})'.format(exc.errno, exc.strerror)
        )
        sys.exit(1)

    # decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(18)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as exc:
        log.error(
            'fork #2 failed: {0} ({1})'.format(
                exc.errno, exc.strerror
            )
        )
        sys.exit(1)

    # A normal daemonization redirects the process output to /dev/null.
    # Unfortunately when a python multiprocess is called the output is
    # not cleanly redirected and the parent process dies when the
    # multiprocessing process attempts to access stdout or err.
    if redirect_out:
        dev_null = open('/dev/null', 'r+')
        os.dup2(dev_null.fileno(), sys.stdin.fileno())
        os.dup2(dev_null.fileno(), sys.stdout.fileno())
        os.dup2(dev_null.fileno(), sys.stderr.fileno())


def daemonize_if(opts):
    '''
    Daemonize a module function process if multiprocessing is True and the
    process is not being called by salt-call
    '''
    if 'salt-call' in sys.argv[0]:
        return
    if not opts.get('multiprocessing', True):
        return
    if sys.platform.startswith('win'):
        return
    daemonize(False)


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
                logging.exception(
                    'Could not open profile file {0}'.format(filename)
                )

            return retval
        return profiled_func
    return proffunc


def which(exe=None):
    '''
    Python clone of /usr/bin/which
    '''
    if exe:
        if os.access(exe, os.X_OK):
            return exe

        # default path based on busybox's default
        default_path = '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin'
        search_path = os.environ.get('PATH', default_path)
        path_ext = os.environ.get('PATHEXT', '.EXE')
        ext_list = path_ext.split(';')

        @real_memoize
        def _exe_has_ext():
            '''
            Do a case insensitive test if exe has a file extension match in
            PATHEXT
            '''
            for ext in ext_list:
                try:
                    pattern = r'.*\.' + ext.lstrip('.') + r'$'
                    re.match(pattern, exe, re.I).groups()
                    return True
                except AttributeError:
                    continue
            return False

        search_path = search_path.split(os.pathsep)
        if not is_windows():
            # Add any dirs in the default_path which are not in search_path. If
            # there was no PATH variable found in os.environ, then this will be
            # a no-op. This ensures that all dirs in the default_path are
            # searched, which lets salt.utils.which() work well when invoked by
            # salt-call running from cron (which, depending on platform, may
            # have a severely limited PATH).
            search_path.extend(
                [
                    x for x in default_path.split(os.pathsep)
                    if x not in search_path
                ]
            )
        for path in search_path:
            full_path = os.path.join(path, exe)
            if os.access(full_path, os.X_OK):
                return full_path
            elif is_windows() and not _exe_has_ext():
                # On Windows, check for any extensions in PATHEXT.
                # Allows both 'cmd' and 'cmd.exe' to be matched.
                for ext in ext_list:
                    # Windows filesystem is case insensitive so we
                    # safely rely on that behaviour
                    if os.access(full_path + ext, os.X_OK):
                        return full_path + ext
        log.trace(
            '{0!r} could not be found in the following search '
            'path: {1!r}'.format(
                exe, search_path
            )
        )
    else:
        log.error(
            'No executable was passed to be searched by salt.utils.which()'
        )
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
    return None


def list_files(directory):
    '''
    Return a list of all files found under directory
    '''
    ret = set()
    ret.add(directory)
    for root, dirs, files in safe_walk(directory):
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
    if len(jid) != 20:
        return ''
    year = jid[:4]
    month = jid[4:6]
    day = jid[6:8]
    hour = jid[8:10]
    minute = jid[10:12]
    second = jid[12:14]
    micro = jid[14:]

    ret = '{0}, {1} {2} {3}:{4}:{5}.{6}'.format(year,
                                                months[int(month)],
                                                day,
                                                hour,
                                                minute,
                                                second,
                                                micro)
    return ret


def gen_mac(prefix='AC:DE:48'):
    '''
    Generates a MAC address with the defined OUI prefix.

    Common prefixes:

     - ``00:16:3E`` -- Xen
     - ``00:18:51`` -- OpenVZ
     - ``00:50:56`` -- VMware (manually generated)
     - ``52:54:00`` -- QEMU/KVM
     - ``AC:DE:48`` -- PRIVATE

    References:

     - http://standards.ieee.org/develop/regauth/oui/oui.txt
     - https://www.wireshark.org/tools/oui-lookup.html
     - https://en.wikipedia.org/wiki/MAC_address
    '''
    r = random.randint
    return '%s:%02X:%02X:%02X' % (prefix, r(0, 0xff), r(0, 0xff), r(0, 0xff))


def ip_bracket(addr):
    '''
    Convert IP address representation to ZMQ (URL) format. ZMQ expects
    brackets around IPv6 literals, since they are used in URLs.
    '''
    if addr and ':' in addr and not addr.startswith('['):
        return '[{0}]'.format(addr)
    return addr


def dns_check(addr, safe=False, ipv6=False):
    '''
    Return the ip resolved by dns, but do not exit on failure, only raise an
    exception. Obeys system preference for IPv4/6 address resolution.
    '''
    error = False
    try:
        hostnames = socket.getaddrinfo(
            addr, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        if not hostnames:
            error = True
        else:
            addr = False
            for h in hostnames:
                if h[0] == socket.AF_INET or (h[0] == socket.AF_INET6 and ipv6):
                    addr = ip_bracket(h[4][0])
                    break
            if not addr:
                error = True
    except socket.error:
        error = True

    if error:
        err = ('This master address: \'{0}\' was previously resolvable '
               'but now fails to resolve! The previously resolved ip addr '
               'will continue to be used').format(addr)
        if safe:
            if salt.log.is_console_configured():
                # If logging is not configured it also means that either
                # the master or minion instance calling this hasn't even
                # started running
                log.error(err)
            raise SaltClientError()
        raise SaltSystemExit(code=42, msg=err)
    return addr


def required_module_list(docstring=None):
    '''
    Return a list of python modules required by a salt module that aren't
    in stdlib and don't exist on the current pythonpath.
    '''
    if not docstring:
        return []
    ret = []
    modules = parse_docstring(docstring).get('deps', [])
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


def gen_jid():
    '''
    Generate a jid
    '''
    return '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())


def prep_jid(cachedir, sum_type, user='root', nocache=False):
    '''
    Return a job id and prepare the job id directory
    '''
    jid = gen_jid()

    jid_dir_ = jid_dir(jid, cachedir, sum_type)
    if not os.path.isdir(jid_dir_):
        if os.path.exists(jid_dir_):
            # Somehow we ended up with a file at our jid destination.
            # Delete it.
            os.remove(jid_dir_)
        os.makedirs(jid_dir_)
        with fopen(os.path.join(jid_dir_, 'jid'), 'w+') as fn_:
            fn_.write(jid)
        if nocache:
            with fopen(os.path.join(jid_dir_, 'nocache'), 'w+') as fn_:
                fn_.write('')
    else:
        return prep_jid(cachedir, sum_type, user=user, nocache=nocache)
    return jid


def jid_dir(jid, cachedir, sum_type):
    '''
    Return the jid_dir for the given job id
    '''
    jid = str(jid)
    jhash = getattr(hashlib, sum_type)(jid).hexdigest()
    return os.path.join(cachedir, 'jobs', jhash[:2], jhash[2:])


def jid_load(jid, cachedir, sum_type, serial='msgpack'):
    '''
    Return the load data for a given job id
    '''
    _dir = jid_dir(jid, cachedir, sum_type)
    load_fn = os.path.join(_dir, '.load.p')
    if not os.path.isfile(load_fn):
        return {}
    serial = salt.payload.Serial(serial)
    with fopen(load_fn) as fp_:
        return serial.load(fp_)


def is_jid(jid):
    '''
    Returns True if the passed in value is a job id
    '''
    if not isinstance(jid, string_types):
        return False
    if len(jid) != 20:
        return False
    try:
        int(jid)
        return True
    except ValueError:
        return False
    return False


def check_or_die(command):
    '''
    Simple convenience function for modules to use for gracefully blowing up
    if a required tool is not available in the system path.

    Lazily import `salt.modules.cmdmod` to avoid any sort of circular
    dependencies.
    '''
    if command is None:
        raise CommandNotFoundError('\'None\' is not a valid command.')

    if not which(command):
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
    tgt = mkstemp(prefix=bname, dir=dname)
    shutil.copyfile(source, tgt)
    bkroot = ''
    if cachedir:
        bkroot = os.path.join(cachedir, 'file_backup')
    if backup_mode == 'minion' or backup_mode == 'both' and bkroot:
        if os.path.exists(dest):
            backup_minion(dest, bkroot)
    if backup_mode == 'master' or backup_mode == 'both' and bkroot:
        # TODO, backup to master
        pass
    shutil.move(tgt, dest)
    # If SELINUX is available run a restorecon on the file
    rcon = which('restorecon')
    if rcon:
        with fopen(os.devnull, 'w') as dev_null:
            cmd = [rcon, dest]
            subprocess.call(cmd, stdout=dev_null, stderr=dev_null)
    if os.path.isfile(tgt):
        # The temp file failed to move
        try:
            os.remove(tgt)
        except Exception:
            pass


def backup_minion(path, bkroot):
    '''
    Backup a file on the minion
    '''
    dname, bname = os.path.split(path)
    fstat = os.stat(path)
    msecs = str(int(time.time() * 1000000))[-6:]
    stamp = time.asctime().replace(' ', '_')
    stamp = '{0}{1}_{2}'.format(stamp[:-4], msecs, stamp[-4:])
    bkpath = os.path.join(bkroot,
                          dname[1:],
                          '{0}_{1}'.format(bname, stamp))
    if not os.path.isdir(os.path.dirname(bkpath)):
        os.makedirs(os.path.dirname(bkpath))
    shutil.copyfile(path, bkpath)
    os.chown(bkpath, fstat.st_uid, fstat.st_gid)


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

    if is_windows():
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
    with fopen(path, 'rb') as fp_:
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


def build_whitespace_split_regex(text):
    '''
    Create a regular expression at runtime which should match ignoring the
    addition or deletion of white space or line breaks, unless between commas

    Example::

    >>> import re
    >>> from salt.utils import *
    >>> regex = build_whitespace_split_regex(
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
    return r'(?m)^{0}$'.format(regex)


def build_whitepace_splited_regex(text):
    warnings.warn('The build_whitepace_splited_regex function is deprecated,'
                  ' please use build_whitespace_split_regex instead.',
                  DeprecationWarning)
    build_whitespace_split_regex(text)


def format_call(fun,
                data,
                initial_ret=None,
                expected_extra_kws=()):
    '''
    Build the required arguments and keyword arguments required for the passed
    function.

    :param fun: The function to get the argspec from
    :param data: A dictionary containing the required data to build the
                 arguments and keyword arguments.
    :param initial_ret: The initial return data pre-populated as dictionary or
                        None
    :param expected_extra_kws: Any expected extra keyword argument names which
                               should not trigger a :ref:`SaltInvocationError`
    :returns: A dictionary with the function required arguments and keyword
              arguments.
    '''
    ret = initial_ret is not None and initial_ret or {}

    ret['args'] = []
    ret['kwargs'] = {}

    aspec = get_function_argspec(fun)

    args, kwargs = arg_lookup(fun).values()

    # Since we WILL be changing the data dictionary, let's change a copy of it
    data = data.copy()

    missing_args = []

    for key in kwargs.keys():
        try:
            kwargs[key] = data.pop(key)
        except KeyError:
            # Let's leave the default value in place
            pass

    while args:
        arg = args.pop(0)
        try:
            ret['args'].append(data.pop(arg))
        except KeyError:
            missing_args.append(arg)

    if missing_args:
        used_args_count = len(ret['args']) + len(args)
        args_count = used_args_count + len(missing_args)
        raise SaltInvocationError(
            '{0} takes at least {1} argument{2} ({3} given)'.format(
                fun.__name__,
                args_count,
                args_count > 1 and 's' or '',
                used_args_count
            )
        )

    ret['kwargs'].update(kwargs)

    if aspec.keywords:
        # The function accepts **kwargs, any non expected extra keyword
        # arguments will made available.
        for key, value in data.iteritems():
            if key in expected_extra_kws:
                continue
            ret['kwargs'][key] = value

        # No need to check for extra keyword arguments since they are all
        # **kwargs now. Return
        return ret

    # Did not return yet? Lets gather any remaining and unexpected keyword
    # arguments
    extra = {}
    for key, value in data.iteritems():
        if key in expected_extra_kws:
            continue
        extra[key] = copy.deepcopy(value)

    # We'll be showing errors to the users until Salt Lithium comes out, after
    # which, errors will be raised instead.
    warn_until(
        'Lithium',
        'It\'s time to start raising `SaltInvocationError` instead of '
        'returning warnings',
        # Let's not show the deprecation warning on the console, there's no
        # need.
        _dont_call_warnings=True
    )

    if extra:
        # Found unexpected keyword arguments, raise an error to the user
        if len(extra) == 1:
            msg = '{0[0]!r} is an invalid keyword argument for {1!r}'.format(
                extra.keys(),
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )
        else:
            msg = '{0} and {1!r} are invalid keyword arguments for {2}'.format(
                ', '.join(['{0!r}'.format(e) for e in extra][:-1]),
                extra.keys()[-1],
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )

        # Return a warning to the user explaining what's going on
        ret.setdefault('warnings', []).append(
            '{0}. If you were trying to pass additional data to be used '
            'in a template context, please populate \'context\' with '
            '\'key: value\' pairs. Your approach will work until Salt Lithium '
            'is out.{1}'.format(
                msg,
                '' if 'full' not in ret else ' Please update your state files.'
            )
        )

        # Lets pack the current extra kwargs as template context
        ret.setdefault('context', {}).update(extra)
    return ret


def arg_lookup(fun):
    '''
    Return a dict containing the arguments and default arguments to the
    function.
    '''
    ret = {'kwargs': {}}
    aspec = get_function_argspec(fun)
    if aspec.defaults:
        ret['kwargs'] = dict(zip(aspec.args[::-1], aspec.defaults[::-1]))
    ret['args'] = [arg for arg in aspec.args if arg not in ret['kwargs']]
    return ret


def istextfile(fp_, blocksize=512):
    '''
    Uses heuristics to guess whether the given file is text or binary,
    by reading a single block of bytes from the file.
    If more than 30% of the chars in the block are non-text, or there
    are NUL ('\x00') bytes in the block, assume this is a binary file.
    '''
    PY3 = sys.version_info[0] == 3  # pylint: disable=C0103
    int2byte = (lambda x: bytes((x,))) if PY3 else chr
    text_characters = (
        b''.join(int2byte(i) for i in range(32, 127)) +
        b'\n\r\t\f\b')
    try:
        block = fp_.read(blocksize)
    except AttributeError:
        # This wasn't an open filehandle, so treat it as a file path and try to
        # open the file
        try:
            with fopen(fp_, 'rb') as fp2_:
                block = fp2_.read(blocksize)
        except IOError:
            # Unable to open file, bail out and return false
            return False
    if b'\x00' in block:
        # Files with null bytes are binary
        return False
    elif not block:
        # An empty file is considered a valid text file
        return True

    nontext = block.translate(None, text_characters)
    return float(len(nontext)) / len(block) <= 0.30


def isorted(to_sort):
    '''
    Sort a list of strings ignoring case.

    >>> L = ['foo', 'Foo', 'bar', 'Bar']
    >>> sorted(L)
    ['Bar', 'Foo', 'bar', 'foo']
    >>> sorted(L, key=lambda x: x.lower())
    ['bar', 'Bar', 'foo', 'Foo']
    >>>
    '''
    return sorted(to_sort, key=lambda x: x.lower())


def mysql_to_dict(data, key):
    '''
    Convert MySQL-style output to a python dictionary
    '''
    ret = {}
    headers = ['']
    for line in data:
        if not line:
            continue
        if line.startswith('+'):
            continue
        comps = line.split('|')
        for comp in range(len(comps)):
            comps[comp] = comps[comp].strip()
        if len(headers) > 1:
            index = len(headers) - 1
            row = {}
            for field in range(index):
                if field < 1:
                    continue
                else:
                    row[headers[field]] = str_to_num(comps[field])
            ret[row[key]] = row
        else:
            headers = comps
    return ret


def contains_whitespace(text):
    '''
    Returns True if there are any whitespace characters in the string
    '''
    return any(x.isspace() for x in text)


def str_to_num(text):
    '''
    Convert a string to a number.
    Returns an integer if the string represents an integer, a floating
    point number if the string is a real number, or the string unchanged
    otherwise.
    '''
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def fopen(*args, **kwargs):
    '''
    Wrapper around open() built-in to set CLOEXEC on the fd.

    This flag specifies that the file descriptor should be closed when an exec
    function is invoked;
    When a file descriptor is allocated (as with open or dup ), this bit is
    initially cleared on the new file descriptor, meaning that descriptor will
    survive into the new program after exec.
    '''
    fhandle = open(*args, **kwargs)
    if HAS_FCNTL:
        # modify the file descriptor on systems with fcntl
        # unix and unix-like systems only
        try:
            FD_CLOEXEC = fcntl.FD_CLOEXEC   # pylint: disable=C0103
        except AttributeError:
            FD_CLOEXEC = 1                  # pylint: disable=C0103
        old_flags = fcntl.fcntl(fhandle.fileno(), fcntl.F_GETFD)
        if 'lock' in kwargs:
            fcntl.flock(fhandle.fileno(), fcntl.LOCK_SH)
        fcntl.fcntl(fhandle.fileno(), fcntl.F_SETFD, old_flags | FD_CLOEXEC)
    return fhandle


def flopen(*args, **kwargs):
    fhandle = open(*args, **kwargs)
    if HAS_FCNTL:
        # modify the file descriptor on systems with fcntl
        # unix and unix-like systems only
        try:
            FD_CLOEXEC = fcntl.FD_CLOEXEC   # pylint: disable=C0103
        except AttributeError:
            FD_CLOEXEC = 1                  # pylint: disable=C0103
        old_flags = fcntl.fcntl(fhandle.fileno(), fcntl.F_GETFD)
        fcntl.flock(fhandle.fileno(), fcntl.LOCK_SH)
        fcntl.fcntl(fhandle.fileno(), fcntl.F_SETFD, old_flags | FD_CLOEXEC)
    return fhandle


def subdict_match(data, expr, delim=':', regex_match=False):
    '''
    Check for a match in a dictionary using a delimiter character to denote
    levels of subdicts, and also allowing the delimiter character to be
    matched. Thus, 'foo:bar:baz' will match data['foo'] == 'bar:baz' and
    data['foo']['bar'] == 'baz'. The former would take priority over the
    latter.
    '''
    def _match(target, pattern, regex_match=False):
        if regex_match:
            try:
                return re.match(pattern.lower(), str(target).lower())
            except Exception:
                log.error('Invalid regex {0!r} in match'.format(pattern))
                return False
        else:
            return fnmatch.fnmatch(str(target).lower(), pattern.lower())

    for idx in range(1, expr.count(delim) + 1):
        splits = expr.split(delim)
        key = delim.join(splits[:idx])
        matchstr = delim.join(splits[idx:])
        log.debug('Attempting to match {0!r} in {1!r} using delimiter '
                  '{2!r}'.format(matchstr, key, delim))
        match = traverse_dict(data, key, {}, delim=delim)
        if match == {}:
            continue
        if isinstance(match, dict):
            if matchstr == '*':
                # We are just checking that the key exists
                return True
            continue
        if isinstance(match, list):
            # We are matching a single component to a single list member
            for member in match:
                if _match(member, matchstr, regex_match=regex_match):
                    return True
            continue
        if _match(match, matchstr, regex_match=regex_match):
            return True
    return False


def traverse_dict(data, key, default, delim=':'):
    '''
    Traverse a dict using a colon-delimited (or otherwise delimited, using
    the "delim" param) target string. The target 'foo:bar:baz' will return
    data['foo']['bar']['baz'] if this value exists, and will otherwise
    return an empty dict.
    '''
    try:
        for each in key.split(delim):
            data = data[each]
    except (KeyError, IndexError, TypeError):
        # Encountered a non-indexable value in the middle of traversing
        return default
    return data


def mkstemp(*args, **kwargs):
    '''
    Helper function which does exactly what `tempfile.mkstemp()` does but
    accepts another argument, `close_fd`, which, by default, is true and closes
    the fd before returning the file path. Something commonly done throughout
    Salt's code.
    '''
    close_fd = kwargs.pop('close_fd', True)
    fd_, fpath = tempfile.mkstemp(*args, **kwargs)
    if close_fd is False:
        return (fd_, fpath)
    os.close(fd_)
    del fd_
    return fpath


def clean_kwargs(**kwargs):
    '''
    Clean out the __pub* keys from the kwargs dict passed into the execution
    module functions. The __pub* keys are useful for tracking what was used to
    invoke the function call, but they may not be desierable to have if
    passing the kwargs forward wholesale.
    '''
    ret = {}
    for key, val in kwargs.items():
        if not key.startswith('__pub'):
            ret[key] = val
    return ret


@real_memoize
def is_windows():
    '''
    Simple function to return if a host is Windows or not
    '''
    return sys.platform.startswith('win')


@real_memoize
def is_linux():
    '''
    Simple function to return if a host is Linux or not
    '''
    return sys.platform.startswith('linux')


@real_memoize
def is_darwin():
    '''
    Simple function to return if a host is Darwin (OS X) or not
    '''
    return sys.platform.startswith('darwin')


def check_ipc_path_max_len(uri):
    # The socket path is limited to 107 characters on Solaris and
    # Linux, and 103 characters on BSD-based systems.
    ipc_path_max_len = getattr(zmq, 'IPC_PATH_MAX_LEN', 103)
    if ipc_path_max_len and len(uri) > ipc_path_max_len:
        raise SaltSystemExit(
            'The socket path is longer than allowed by OS. '
            '{0!r} is longer than {1} characters. '
            'Either try to reduce the length of this setting\'s '
            'path or switch to TCP; in the configuration file, '
            'set "ipc_mode: tcp".'.format(
                uri, ipc_path_max_len
            )
        )


def check_state_result(running):
    '''
    Check the total return value of the run and determine if the running
    dict has any issues
    '''
    if not isinstance(running, dict):
        return False
    if not running:
        return False
    for host in running:
        if not isinstance(running[host], dict):
            return False

        if host.find('_|-') == 4:
            # This is a single ret, no host associated
            rets = running[host]
        else:
            rets = running[host].values()

        if isinstance(rets, dict) and 'result' in rets:
            if rets['result'] is False:
                return False
            return True

        for ret in rets:
            if not isinstance(ret, dict):
                return False
            if 'result' not in ret:
                return False
            if ret['result'] is False:
                return False
    return True


def test_mode(**kwargs):
    '''
    Examines the kwargs passed and returns True if any kwarg which matching
    "Test" in any variation on capitalization (i.e. "TEST", "Test", "TeSt",
    etc) contains a True value (as determined by salt.utils.is_true).
    '''
    for arg, value in kwargs.iteritems():
        try:
            if arg.lower() == 'test' and is_true(value):
                return True
        except AttributeError:
            continue
    return False


def is_true(value=None):
    '''
    Returns a boolean value representing the "truth" of the value passed. The
    rules for what is a "True" value are:

        1. Integer/float values greater than 0
        2. The string values "True" and "true"
        3. Any object for which bool(obj) returns True
    '''
    # First, try int/float conversion
    try:
        value = int(value)
    except (ValueError, TypeError):
        pass
    try:
        value = float(value)
    except (ValueError, TypeError):
        pass

    # Now check for truthiness
    if isinstance(value, (int, float)):
        return value > 0
    elif isinstance(value, string_types):
        return str(value).lower() == 'true'
    else:
        return bool(value)


def rm_rf(path):
    '''
    Platform-independent recursive delete. Includes code from
    http://stackoverflow.com/a/2656405
    '''
    def _onerror(func, path, exc_info):
        '''
        Error handler for `shutil.rmtree`.

        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.

        If the error is for another reason it re-raises the error.

        Usage : `shutil.rmtree(path, onerror=onerror)`
        '''
        if is_windows() and not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

    shutil.rmtree(path, onerror=_onerror)


def option(value, default='', opts=None, pillar=None):
    '''
    Pass in a generic option and receive the value that will be assigned
    '''
    if opts is None:
        opts = {}
    if pillar is None:
        pillar = {}
    if value in opts:
        return opts[value]
    if value in pillar.get('master', {}):
        return pillar['master'][value]
    if value in pillar:
        return pillar[value]
    return default


def valid_url(url, protos):
    '''
    Return true if the passed URL is in the list of accepted protos
    '''
    if salt._compat.urlparse(url).scheme in protos:
        return True
    return False


def parse_docstring(docstring):
    '''
    Parse a docstring into its parts.

    Currently only parses dependencies, can be extended to parse whatever is
    needed.

    Parses into a dictionary:
        {
            'full': full docstring,
            'deps': list of dependencies (empty list if none)
        }
    '''
    # First try with regex search for :depends:
    ret = {}
    ret['full'] = docstring
    regex = r'([ \t]*):depends:[ \t]+- (\w+)[^\n]*\n(\1[ \t]+- (\w+)[^\n]*\n)*'
    match = re.search(regex, docstring, re.M)
    if match:
        deps = []
        regex = r'- (\w+)'
        for line in match.group(0).strip().splitlines():
            deps.append(re.search(regex, line).group(1))
        ret['deps'] = deps
        return ret
    # Try searching for a one-liner instead
    else:
        txt = 'Required python modules: '
        data = docstring.splitlines()
        dep_list = list(x for x in data if x.strip().startswith(txt))
        if not dep_list:
            ret['deps'] = []
            return ret
        deps = dep_list[0].replace(txt, '').strip().split(', ')
        ret['deps'] = deps
        return ret


def safe_walk(top, topdown=True, onerror=None, followlinks=True, _seen=None):
    '''
    A clone of the python os.walk function with some checks for recursive
    symlinks. Unlike os.walk this follows symlinks by default.
    '''
    islink, join, isdir = os.path.islink, os.path.join, os.path.isdir
    if _seen is None:
        _seen = set()

    # We may not have read permission for top, in which case we can't
    # get a list of the files the directory contains.  os.path.walk
    # always suppressed the exception then, rather than blow up for a
    # minor reason when (say) a thousand readable directories are still
    # left to visit.  That logic is copied here.
    try:
        # Note that listdir and error are globals in this module due
        # to earlier import-*.
        names = os.listdir(top)
    except os.error as err:
        if onerror is not None:
            onerror(err)
        return

    if followlinks:
        status = os.stat(top)
        # st_ino is always 0 on some filesystems (FAT, NTFS); ignore them
        if status.st_ino != 0:
            node = (status.st_dev, status.st_ino)
            if node in _seen:
                return
            _seen.add(node)

    dirs, nondirs = [], []
    for name in names:
        full_path = join(top, name)
        if isdir(full_path):
            dirs.append(name)
        else:
            nondirs.append(name)

    if topdown:
        yield top, dirs, nondirs
    for name in dirs:
        new_path = join(top, name)
        if followlinks or not islink(new_path):
            for x in safe_walk(new_path, topdown, onerror, followlinks, _seen):
                yield x
    if not topdown:
        yield top, dirs, nondirs


def get_hash(path, form='md5', chunk_size=4096):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``
    '''
    try:
        hash_type = getattr(hashlib, form)
    except AttributeError:
        raise ValueError('Invalid hash type: {0}'.format(form))
    with salt.utils.fopen(path, 'rb') as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b''):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


def namespaced_function(function, global_dict, defaults=None):
    '''
    Redefine(clone) a function under a different globals() namespace scope
    '''
    if defaults is None:
        defaults = function.__defaults__

    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=defaults
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def parse_kwarg(string_):
    '''
    Parses the string and looks for the kwarg format:
    "{argument name}={argument value}"
    For example:
    "my_message=Hello world"
    The argument name must have a valid python identifier format (it should
    match the following regular expression: [^\\d\\W]\\w*).
    If the string matches, then this function returns the following tuple:
    ({argument name}, {value})
    Or else it returns:
    (None, None)
    '''
    match = KWARG_REGEX.match(string_)
    if match:
        return match.groups()
    else:
        return None, None


def _win_console_event_handler(event):
    if event == 5:
        # Do nothing on CTRL_LOGOFF_EVENT
        return True
    return False


def enable_ctrl_logoff_handler():
    if HAS_WIN32API:
        win32api.SetConsoleCtrlHandler(_win_console_event_handler, 1)


def date_cast(date):
    '''
    Casts any object into a datetime.datetime object

    date
      any datetime, time string representation...
    '''
    if date is None:
        return datetime.datetime.now()
    elif isinstance(date, datetime.datetime):
        return date

    # fuzzy date
    try:
        if isinstance(date, salt._compat.string_types):
            try:
                if HAS_TIMELIB:
                    return timelib.strtodatetime(date)
            except ValueError:
                pass

            # not parsed yet, obviously a timestamp?
            if date.isdigit():
                date = int(date)
            else:
                date = float(date)

        return datetime.datetime.fromtimestamp(date)
    except Exception as e:
        if HAS_TIMELIB:
            raise ValueError('Unable to parse {0}'.format(date))

        raise RuntimeError('Unable to parse {0}.'
            ' Consider installing timelib'.format(date))


def date_format(date=None, format="%Y-%m-%d"):
    '''
    Converts date into a time-based string

    date
      any datetime, time string representation...

    format
       :ref:`strftime<http://docs.python.org/2/library/datetime.html#datetime.datetime.strftime>` format

    >>> import datetime
    >>> src = datetime.datetime(2002, 12, 25, 12, 00, 00, 00)
    >>> date_format(src)
    'Dec 25, 2002'
    >>> src = '2002/12/25'
    >>> date_format(src)
    'Dec 25, 2002'
    >>> src = 1040814000
    >>> date_format(src)
    'Dec 25, 2002'
    >>> src = '1040814000'
    >>> date_format(src)
    'Dec 25, 2002'
    '''
    return date_cast(date).strftime(format)


def warn_until(version,
               message,
               category=DeprecationWarning,
               stacklevel=None,
               _version_info_=None,
               _dont_call_warnings=False):
    '''
    Helper function to raise a warning, by default, a ``DeprecationWarning``,
    until the provided ``version``, after which, a ``RuntimeError`` will
    be raised to remind the developers to remove the warning because the
    target version has been reached.

    :param version: The version info or name after which the warning becomes a
                    ``RuntimeError``. For example ``(0, 17)`` or ``Hydrogen``
                    or an instance of :class:`salt.version.SaltStackVersion`.
    :param message: The warning message to be displayed.
    :param category: The warning class to be thrown, by default
                     ``DeprecationWarning``
    :param stacklevel: There should be no need to set the value of
                       ``stacklevel``. Salt should be able to do the right thing.
    :param _version_info_: In order to reuse this function for other SaltStack
                           projects, they need to be able to provide the
                           version info to compare to.
    :param _dont_call_warnings: This parameter is used just to get the
                                functionality until the actual error is to be
                                issued. When we're only after the salt version
                                checks to raise a ``RuntimeError``.
    '''
    if not isinstance(version, (tuple,
                                salt._compat.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, salt._compat.string_types):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until()
        stacklevel = 2

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if _version_ >= version:
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        raise RuntimeError(
            'The warning triggered on filename {filename!r}, line number '
            '{lineno}, is supposed to be shown until version '
            '{until_version!r} is released. Current version is now '
            '{salt_version!r}. Please remove the warning.'.format(
                filename=caller.filename,
                lineno=caller.lineno,
                until_version=version.formatted_version,
                salt_version=_version_.formatted_version
            ),
        )

    if _dont_call_warnings is False:
        warnings.warn(
            message.format(version=version.formatted_version),
            category,
            stacklevel=stacklevel
        )


def kwargs_warn_until(kwargs,
                      version,
                      category=DeprecationWarning,
                      stacklevel=None,
                      _version_info_=None,
                      _dont_call_warnings=False):
    '''
    Helper function to raise a warning (by default, a ``DeprecationWarning``)
    when unhandled keyword arguments are passed to function, until the
    provided ``version_info``, after which, a ``RuntimeError`` will be raised
    to remind the developers to remove the ``**kwargs`` because the target
    version has been reached.
    This function is used to help deprecate unused legacy ``**kwargs`` that
    were added to function parameters lists to preserve backwards compatibility
    when removing a parameter. See
    :doc:`the deprecation development docs </topics/development/deprecations>`
    for the modern strategy for deprecating a function parameter.

    :param kwargs: The caller's ``**kwargs`` argument value (a ``dict``).
    :param version: The version info or name after which the warning becomes a
                    ``RuntimeError``. For example ``(0, 17)`` or ``Hydrogen``
                    or an instance of :class:`salt.version.SaltStackVersion`.
    :param category: The warning class to be thrown, by default
                     ``DeprecationWarning``
    :param stacklevel: There should be no need to set the value of
                       ``stacklevel``. Salt should be able to do the right thing.
    :param _version_info_: In order to reuse this function for other SaltStack
                           projects, they need to be able to provide the
                           version info to compare to.
    :param _dont_call_warnings: This parameter is used just to get the
                                functionality until the actual error is to be
                                issued. When we're only after the salt version
                                checks to raise a ``RuntimeError``.
    '''
    if not isinstance(version, (tuple,
                                salt._compat.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, salt._compat.string_types):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function,
        # not to kwargs_warn_until() or warn_until()
        stacklevel = 3

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if kwargs or _version_.info >= version.info:
        arg_names = ', '.join('{0!r}'.format(key) for key in kwargs)
        warn_until(
            version,
            message='The following parameter(s) have been deprecated and '
                    'will be removed in {0!r}: {1}.'.format(version.string,
                                                            arg_names),
            category=category,
            stacklevel=stacklevel,
            _version_info_=_version_.info,
            _dont_call_warnings=_dont_call_warnings
        )


def version_cmp(pkg1, pkg2):
    '''
    Compares two version strings using distutils.version.LooseVersion. This is
    a fallback for providers which don't have a version comparison utility
    built into them.  Return -1 if version1 < version2, 0 if version1 ==
    version2, and 1 if version1 > version2. Return None if there was a problem
    making the comparison.
    '''
    try:
        if distutils.version.LooseVersion(pkg1) < \
                distutils.version.LooseVersion(pkg2):
            return -1
        elif distutils.version.LooseVersion(pkg1) == \
                distutils.version.LooseVersion(pkg2):
            return 0
        elif distutils.version.LooseVersion(pkg1) > \
                distutils.version.LooseVersion(pkg2):
            return 1
    except Exception as e:
        log.exception(e)
    return None


def compare_versions(ver1='', oper='==', ver2='', cmp_func=None):
    '''
    Compares two version numbers. Accepts a custom function to perform the
    cmp-style version comparison, otherwise uses version_cmp().
    '''
    cmp_map = {'<': (-1,), '<=': (-1, 0), '==': (0,),
               '>=': (0, 1), '>': (1,)}
    if oper not in ['!='] + cmp_map.keys():
        log.error('Invalid operator "{0}" for version '
                  'comparison'.format(oper))
        return False

    if cmp_func is None:
        cmp_func = version_cmp

    cmp_result = cmp_func(ver1, ver2)
    if cmp_result is None:
        return False

    if oper == '!=':
        return cmp_result not in cmp_map['==']
    else:
        return cmp_result in cmp_map[oper]


def compare_dicts(old=None, new=None):
    '''
    Compare before and after results from various salt functions, returning a
    dict describing the changes that were made.
    '''
    ret = {}
    for key in set((new or {}).keys()).union((old or {}).keys()):
        if key not in old:
            # New key
            ret[key] = {'old': '',
                        'new': new[key]}
        elif key not in new:
            # Key removed
            ret[key] = {'new': '',
                        'old': old[key]}
        elif new[key] != old[key]:
            # Key modified
            ret[key] = {'old': old[key],
                        'new': new[key]}
    return ret


def argspec_report(functions, module=''):
    '''
    Pass in a functions dict as it is returned from the loader and return the
    argspec function sigs
    '''
    ret = {}
    # TODO: cp.get_file will also match cp.get_file_str. this is the
    # same logic as sys.doc, and it is not working as expected, see
    # issue #3614
    if module:
        # allow both "sys" and "sys." to match sys, without also matching
        # sysctl
        comps = module.split('.')
        comps = filter(None, comps)
        if len(comps) < 2:
            module = module + '.' if not module.endswith('.') else module
    for fun in functions:
        if fun.startswith(module):
            try:
                aspec = get_function_argspec(functions[fun])
            except TypeError:
                # this happens if not callable
                continue

            args, varargs, kwargs, defaults = aspec

            ret[fun] = {}
            ret[fun]['args'] = args if args else None
            ret[fun]['defaults'] = defaults if defaults else None
            ret[fun]['varargs'] = True if varargs else None
            ret[fun]['kwargs'] = True if kwargs else None

    return ret


def memoize(func):
    '''
    Deprecation warning wrapper since memoize is now on salt.utils.decorators
    '''
    warn_until(
        'Helium',
        'The \'memoize\' decorator was moved to \'salt.utils.decorators\', '
        'please start importing it from there. This warning and wrapper '
        'will be removed in Salt {version}.',
        stacklevel=3

    )
    return real_memoize(func)


def decode_list(data):
    '''
    JSON decodes as unicode, Jinja needs bytes...
    '''
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv


def decode_dict(data):
    '''
    JSON decodes as unicode, Jinja needs bytes...
    '''
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv


def find_json(raw):
    '''
    Pass in a raw string and load the json when is starts. This allows for a
    string to start with garbage and end with json but be cleanly loaded
    '''
    ret = {}
    for ind in range(len(raw)):
        working = '\n'.join(raw.splitlines()[ind:])
        try:
            ret = json.loads(working, object_hook=decode_dict)
        except ValueError:
            continue
        if ret:
            return ret
    if not ret:
        # Not json, raise an error
        raise ValueError


def is_bin_file(path):
    '''
    Detects if the file is a binary, returns bool. Returns True if the file is
    a bin, False if the file is not and None if the file is not available.
    '''
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r') as fp_:
            return(is_bin_str(fp_.read(2048)))
    except os.error:
        return None


def is_bin_str(data):
    '''
    Detects if the passed string of data is bin or text
    '''
    text_characters = ''.join(map(chr, range(32, 127)) + list('\n\r\t\b'))
    _null_trans = string.maketrans('', '')
    if '\0' in data:
        return True
    if not data:
        return False

    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    text = data.translate(_null_trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(text) / len(data) > 0.30:
        return True
    return False


def repack_dictlist(data):
    '''
    Takes a list of one-element dicts (as found in many SLS schemas) and
    repacks into a single dictionary.
    '''
    if isinstance(data, string_types):
        try:
            data = yaml.safe_load(data)
        except yaml.parser.ParserError as err:
            log.error(err)
            return {}
    if not isinstance(data, list) \
            or [x for x in data
                if not isinstance(x, (string_types, int, float, dict))]:
        log.error('Invalid input: {0}'.format(pprint.pformat(data)))
        log.error('Input must be a list of strings/dicts')
        return {}
    ret = {}
    for element in data:
        if isinstance(element, (string_types, int, float)):
            ret[element] = None
        else:
            if len(element) != 1:
                log.error('Invalid input: key/value pairs must contain '
                          'only one element (data passed: {0}).'
                          .format(element))
                return {}
            ret.update(element)
    return ret
