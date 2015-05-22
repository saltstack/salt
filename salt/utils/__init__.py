# -*- coding: utf-8 -*-
'''
Some of the utils used by salt
'''

# Import python libs
from __future__ import absolute_import, print_function
import contextlib
import copy
import collections
import datetime
import distutils.version  # pylint: disable=import-error,no-name-in-module
import errno
import fnmatch
import hashlib
import imp
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
import sys
import tempfile
import time
import types
import warnings
import string

# Import 3rd-party libs
import salt.ext.six as six
# pylint: disable=import-error
from salt.ext.six.moves.urllib.parse import urlparse  # pylint: disable=no-name-in-module
# pylint: disable=redefined-builtin
from salt.ext.six.moves import range
from salt.ext.six.moves import zip
from salt.ext.six.moves import map
from stat import S_IMODE
# pylint: enable=import-error,redefined-builtin

# Try to load pwd, fallback to getpass if unsuccessful
# Import 3rd-party libs
try:
    import Crypto.Random
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import pwd
except ImportError:
    import getpass
    pwd = None

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
    import grp
    HAS_GRP = True
except ImportError:
    # grp is not available on windows
    HAS_GRP = False

try:
    import pwd
    HAS_PWD = True
except ImportError:
    # pwd is not available on windows
    HAS_PWD = False

try:
    import setproctitle
    HAS_SETPROCTITLE = True
except ImportError:
    HAS_SETPROCTITLE = False

try:
    import ctypes
    import ctypes.util
    libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("c"))
    res_init = libc.__res_init
    HAS_RESINIT = True
except (ImportError, OSError, AttributeError):
    HAS_RESINIT = False

# Import salt libs
from salt.defaults import DEFAULT_TARGET_DELIM
import salt.defaults.exitcodes
import salt.log
import salt.version
from salt.utils.decorators import memoize as real_memoize
from salt.textformat import TextFormat
from salt.exceptions import (
    CommandExecutionError, SaltClientError,
    CommandNotFoundError, SaltSystemExit,
    SaltInvocationError
)


log = logging.getLogger(__name__)
_empty = object()


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


def get_color_theme(theme):
    '''
    Return the color theme to use
    '''
    # Keep the heavy lifting out of the module space
    import yaml
    if not os.path.isfile(theme):
        log.warning('The named theme {0} if not available'.format(theme))
    try:
        with fopen(theme, 'rb') as fp_:
            colors = yaml.safe_load(fp_.read())
            ret = {}
            for color in colors:
                ret[color] = '\033[{0}m'.format(colors[color])
            if not isinstance(colors, dict):
                log.warning('The theme file {0} is not a dict'.format(theme))
                return {}
            return ret
    except Exception:
        log.warning('Failed to read the color theme {0}'.format(theme))
        return {}


def get_colors(use=True, theme=None):
    '''
    Return the colors as an easy to use dict.  Pass `False` to deactivate all
    colors by setting them to empty strings.  Pass a string containing only the
    name of a single color to be used in place of all colors.  Examples:

    .. code-block:: python

        colors = get_colors()  # enable all colors
        no_colors = get_colors(False)  # disable all colors
        red_colors = get_colors('RED')  # set all colors to red
    '''

    colors = {
        'BLACK': TextFormat('black'),
        'DARK_GRAY': TextFormat('bold', 'black'),
        'RED': TextFormat('red'),
        'LIGHT_RED': TextFormat('bold', 'red'),
        'GREEN': TextFormat('green'),
        'LIGHT_GREEN': TextFormat('bold', 'green'),
        'YELLOW': TextFormat('yellow'),
        'LIGHT_YELLOW': TextFormat('bold', 'yellow'),
        'BLUE': TextFormat('blue'),
        'LIGHT_BLUE': TextFormat('bold', 'blue'),
        'MAGENTA': TextFormat('magenta'),
        'LIGHT_MAGENTA': TextFormat('bold', 'magenta'),
        'CYAN': TextFormat('cyan'),
        'LIGHT_CYAN': TextFormat('bold', 'cyan'),
        'LIGHT_GRAY': TextFormat('white'),
        'WHITE': TextFormat('bold', 'white'),
        'DEFAULT_COLOR': TextFormat('default'),
        'ENDC': TextFormat('reset'),
    }
    if theme:
        colors.update(get_color_theme(theme))

    if not use:
        for color in colors:
            colors[color] = ''
    if isinstance(use, str):
        # Try to set all of the colors to the passed color
        if use in colors:
            for color in colors:
                # except for color reset
                if color == 'ENDC':
                    continue
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
    buf = [i.encode('UTF-8') if isinstance(i, six.text_type) else i for i in buf]

    return '---\n{0}\n---'.format('\n'.join(buf))


def get_user():
    '''
    Get the current user
    '''
    if pwd is not None:
        return pwd.getpwuid(os.geteuid()).pw_name
    else:
        return getpass.getuser()


def get_uid(user=None):
    """
    Get the uid for a given user name. If no user given,
    the current euid will be returned. If the user
    does not exist, None will be returned. On
    systems which do not support pwd or os.geteuid
    it will return None.
    """
    if pwd is None:
        result = None
    elif user is None:
        try:
            result = os.geteuid()
        except AttributeError:
            result = None
    else:
        try:
            u_struct = pwd.getpwnam(user)
        except KeyError:
            result = None
        else:
            result = u_struct.pw_uid
    return result


def get_gid(group=None):
    """
    Get the gid for a given group name. If no group given,
    the current egid will be returned. If the group
    does not exist, None will be returned. On
    systems which do not support grp or os.getegid
    it will return None.
    """
    if grp is None:
        result = None
    elif group is None:
        try:
            result = os.getegid()
        except AttributeError:
            result = None
    else:
        try:
            g_struct = grp.getgrnam(group)
        except KeyError:
            result = None
        else:
            result = g_struct.gr_gid
    return result


def get_specific_user():
    '''
    Get a user name for publishing. If you find the user is "root" attempt to be
    more specific
    '''
    user = get_user()
    env_vars = ('SUDO_USER',)
    if user == 'root':
        for evar in env_vars:
            if evar in os.environ:
                return 'sudo_{0}'.format(os.environ[evar])
    return user


def reinit_crypto():
    '''
    When a fork arrises, pycrypto needs to reinit
    From its doc::

        Caveat: For the random number generator to work correctly,
        you must call Random.atfork() in both the parent and
        child processes after using os.fork()

    '''
    if HAS_CRYPTO:
        Crypto.Random.atfork()


def daemonize(redirect_out=True):
    '''
    Daemonize a process
    '''
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            reinit_crypto()
            sys.exit(salt.defaults.exitcodes.EX_OK)
    except OSError as exc:
        log.error(
            'fork #1 failed: {0} ({1})'.format(exc.errno, exc.strerror)
        )
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    # decouple from parent environment
    os.chdir('/')
    # noinspection PyArgumentList
    os.setsid()
    os.umask(18)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            reinit_crypto()
            sys.exit(salt.defaults.exitcodes.EX_OK)
    except OSError as exc:
        log.error(
            'fork #2 failed: {0} ({1})'.format(
                exc.errno, exc.strerror
            )
        )
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    reinit_crypto()

    # A normal daemonization redirects the process output to /dev/null.
    # Unfortunately when a python multiprocess is called the output is
    # not cleanly redirected and the parent process dies when the
    # multiprocessing process attempts to access stdout or err.
    if redirect_out:
        with fopen('/dev/null', 'r+') as dev_null:
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
    def _is_executable_file_or_link(exe):
        # check for os.X_OK doesn't suffice because directory may executable
        return (os.access(exe, os.X_OK) and
                (os.path.isfile(exe) or os.path.islink(exe)))

    if exe:
        if _is_executable_file_or_link(exe):
            # executable in cwd or fullpath
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
            if _is_executable_file_or_link(full_path):
                return full_path
            elif is_windows() and not _exe_has_ext():
                # On Windows, check for any extensions in PATHEXT.
                # Allows both 'cmd' and 'cmd.exe' to be matched.
                for ext in ext_list:
                    # Windows filesystem is case insensitive so we
                    # safely rely on that behavior
                    if _is_executable_file_or_link(full_path + ext):
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
    if not isinstance(exes, collections.Iterable):
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
    return '{0}:{1:02X}:{2:02X}:{3:02X}'.format(prefix,
                                                random.randint(0, 0xff),
                                                random.randint(0, 0xff),
                                                random.randint(0, 0xff))


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
        # issue #21397: force glibc to re-read resolv.conf
        if HAS_RESINIT:
            res_init()
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
    except TypeError:
        err = ('Attempt to resolve address \'{0}\' failed. Invalid or unresolveable address').format(addr)
        raise SaltSystemExit(code=42, msg=err)
    except socket.error:
        error = True

    if error:
        err = ('DNS lookup of \'{0}\' failed.').format(addr)
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


def get_accumulator_dir(cachedir):
    '''
    Return the directory that accumulator data is stored in, creating it if it
    doesn't exist.
    '''
    fn_ = os.path.join(cachedir, 'accumulator')
    if not os.path.isdir(fn_):
        # accumulator_dir is not present, create it
        os.makedirs(fn_)
    return fn_


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


def backup_minion(path, bkroot):
    '''
    Backup a file on the minion
    '''
    dname, bname = os.path.split(path)
    if salt.utils.is_windows():
        src_dir = dname.replace(':', '_')
    else:
        src_dir = dname[1:]
    if not salt.utils.is_windows():
        fstat = os.stat(path)
    msecs = str(int(time.time() * 1000000))[-6:]
    if salt.utils.is_windows():
        # ':' is an illegal filesystem path character on Windows
        stamp = time.strftime('%a_%b_%d_%H-%M-%S_%Y')
    else:
        stamp = time.strftime('%a_%b_%d_%H:%M:%S_%Y')
    stamp = '{0}{1}_{2}'.format(stamp[:-4], msecs, stamp[-4:])
    bkpath = os.path.join(bkroot,
                          src_dir,
                          '{0}_{1}'.format(bname, stamp))
    if not os.path.isdir(os.path.dirname(bkpath)):
        os.makedirs(os.path.dirname(bkpath))
    shutil.copyfile(path, bkpath)
    if not salt.utils.is_windows():
        os.chown(bkpath, fstat.st_uid, fstat.st_gid)
        os.chmod(bkpath, fstat.st_mode)


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


def pem_finger(path=None, key=None, sum_type='md5'):
    '''
    Pass in either a raw pem string, or the path on disk to the location of a
    pem file, and the type of cryptographic hash to use. The default is md5.
    The fingerprint of the pem will be returned.

    If neither a key nor a path are passed in, a blank string will be returned.
    '''
    if not key:
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

    Example:

    .. code-block:: yaml

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

    aspec = salt.utils.args.get_function_argspec(fun)

    arg_data = arg_lookup(fun)
    args = arg_data['args']
    kwargs = arg_data['kwargs']

    # Since we WILL be changing the data dictionary, let's change a copy of it
    data = data.copy()

    missing_args = []

    for key in kwargs:
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
        for key, value in six.iteritems(data):
            if key in expected_extra_kws:
                continue
            ret['kwargs'][key] = value

        # No need to check for extra keyword arguments since they are all
        # **kwargs now. Return
        return ret

    # Did not return yet? Lets gather any remaining and unexpected keyword
    # arguments
    extra = {}
    for key, value in six.iteritems(data):
        if key in expected_extra_kws:
            continue
        extra[key] = copy.deepcopy(value)

    # We'll be showing errors to the users until Salt Carbon comes out, after
    # which, errors will be raised instead.
    warn_until(
        'Carbon',
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
                list(extra.keys()),
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )
        else:
            msg = '{0} and {1!r} are invalid keyword arguments for {2!r}'.format(
                ', '.join(['{0!r}'.format(e) for e in extra][:-1]),
                list(extra.keys())[-1],
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
            '\'key: value\' pairs. Your approach will work until Salt '
            'Carbon is out.{1}'.format(
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
    aspec = salt.utils.args.get_function_argspec(fun)
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
    When a file descriptor is allocated (as with open or dup), this bit is
    initially cleared on the new file descriptor, meaning that descriptor will
    survive into the new program after exec.

    NB! We still have small race condition between open and fcntl.

    '''
    # Remove lock from kwargs if present
    lock = kwargs.pop('lock', False)

    if lock is True:
        warn_until(
            'Beryllium',
            'The \'lock\' keyword argument is deprecated and will be '
            'removed in Salt Beryllium. Please use '
            '\'salt.utils.flopen()\' for file locking while calling '
            '\'salt.utils.fopen()\'.'
        )
        return flopen(*args, **kwargs)

    # ensure 'binary' mode is always used on windows
    if is_windows():
        if len(args) > 1:
            args = list(args)
            if 'b' not in args[1]:
                args[1] += 'b'
        elif kwargs.get('mode', None):
            if 'b' not in kwargs['mode']:
                kwargs['mode'] += 'b'
        else:
            # the default is to read
            kwargs['mode'] = 'rb'

    fhandle = open(*args, **kwargs)
    if is_fcntl_available():
        # modify the file descriptor on systems with fcntl
        # unix and unix-like systems only
        try:
            FD_CLOEXEC = fcntl.FD_CLOEXEC   # pylint: disable=C0103
        except AttributeError:
            FD_CLOEXEC = 1                  # pylint: disable=C0103
        old_flags = fcntl.fcntl(fhandle.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(fhandle.fileno(), fcntl.F_SETFD, old_flags | FD_CLOEXEC)

    return fhandle


@contextlib.contextmanager
def flopen(*args, **kwargs):
    '''
    Shortcut for fopen with lock and context manager
    '''
    with fopen(*args, **kwargs) as fhandle:
        try:
            if is_fcntl_available(check_sunos=True):
                fcntl.flock(fhandle.fileno(), fcntl.LOCK_SH)
            yield fhandle
        finally:
            if is_fcntl_available(check_sunos=True):
                fcntl.flock(fhandle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def fpopen(*args, **kwargs):
    '''
    Shortcut for fopen with extra uid, gid and mode options.

    Supported optional Keyword Arguments:

      mode: explicit mode to set. Mode is anything os.chmod
            would accept as input for mode. Works only on unix/unix
            like systems.

      uid: the uid to set, if not set, or it is None or -1 no changes are
           made. Same applies if the path is already owned by this
           uid. Must be int. Works only on unix/unix like systems.

      gid: the gid to set, if not set, or it is None or -1 no changes are
           made. Same applies if the path is already owned by this
           gid. Must be int. Works only on unix/unix like systems.

    '''
    # Remove uid, gid and mode from kwargs if present
    uid = kwargs.pop('uid', -1)  # -1 means no change to current uid
    gid = kwargs.pop('gid', -1)  # -1 means no change to current gid
    mode = kwargs.pop('mode', None)
    with fopen(*args, **kwargs) as fhandle:
        path = args[0]
        d_stat = os.stat(path)

        if hasattr(os, 'chown'):
            # if uid and gid are both -1 then go ahead with
            # no changes at all
            if (d_stat.st_uid != uid or d_stat.st_gid != gid) and \
                    [i for i in (uid, gid) if i != -1]:
                os.chown(path, uid, gid)

        if mode is not None:
            mode_part = S_IMODE(d_stat.st_mode)
            if mode_part != mode:
                os.chmod(path, (d_stat.st_mode ^ mode_part) | mode)

        yield fhandle


def expr_match(line, expr):
    '''
    Evaluate a line of text against an expression. First try a full-string
    match, next try globbing, and then try to match assuming expr is a regular
    expression. Originally designed to match minion IDs for
    whitelists/blacklists.
    '''
    if line == expr:
        return True
    if fnmatch.fnmatch(line, expr):
        return True
    try:
        if re.match(r'\A{0}\Z'.format(expr), line):
            return True
    except re.error:
        pass
    return False


def check_whitelist_blacklist(value, whitelist=None, blacklist=None):
    '''
    Check a whitelist and/or blacklist to see if the value matches it.
    '''
    if not any((whitelist, blacklist)):
        return True
    in_whitelist = False
    in_blacklist = False
    if whitelist:
        try:
            for expr in whitelist:
                if expr_match(value, expr):
                    in_whitelist = True
                    break
        except TypeError:
            log.error('Non-iterable whitelist {0}'.format(whitelist))
            whitelist = None
    else:
        whitelist = None

    if blacklist:
        try:
            for expr in blacklist:
                if expr_match(value, expr):
                    in_blacklist = True
                    break
        except TypeError:
            log.error('Non-iterable blacklist {0}'.format(whitelist))
            blacklist = None
    else:
        blacklist = None

    if whitelist and not blacklist:
        ret = in_whitelist
    elif blacklist and not whitelist:
        ret = not in_blacklist
    elif whitelist and blacklist:
        ret = in_whitelist and not in_blacklist
    else:
        ret = True

    return ret


def subdict_match(data,
                  expr,
                  delimiter=DEFAULT_TARGET_DELIM,
                  regex_match=False,
                  exact_match=False):
    '''
    Check for a match in a dictionary using a delimiter character to denote
    levels of subdicts, and also allowing the delimiter character to be
    matched. Thus, 'foo:bar:baz' will match data['foo'] == 'bar:baz' and
    data['foo']['bar'] == 'baz'. The former would take priority over the
    latter.
    '''
    def _match(target, pattern, regex_match=False, exact_match=False):
        if regex_match:
            try:
                return re.match(pattern.lower(), str(target).lower())
            except Exception:
                log.error('Invalid regex {0!r} in match'.format(pattern))
                return False
        elif exact_match:
            return str(target).lower() == pattern.lower()
        else:
            return fnmatch.fnmatch(str(target).lower(), pattern.lower())

    def _dict_match(target, pattern, regex_match=False, exact_match=False):
        if pattern.startswith('*:'):
            pattern = pattern[2:]

        if pattern == '*':
            # We are just checking that the key exists
            return True
        elif pattern in target:
            # We might want to search for a key
            return True
        elif subdict_match(target,
                         pattern,
                         regex_match=regex_match,
                         exact_match=exact_match):
            return True
        for key in target.keys():
            if _match(key,
                      pattern,
                      regex_match=regex_match,
                      exact_match=exact_match):
                return True
            if isinstance(target[key], dict):
                if _dict_match(target[key],
                               pattern,
                               regex_match=regex_match,
                               exact_match=exact_match):
                    return True
            elif isinstance(target[key], list):
                for item in target[key]:
                    if _match(item,
                              pattern,
                              regex_match=regex_match,
                              exact_match=exact_match):
                        return True
        return False

    for idx in range(1, expr.count(delimiter) + 1):
        splits = expr.split(delimiter)
        key = delimiter.join(splits[:idx])
        matchstr = delimiter.join(splits[idx:])
        log.debug('Attempting to match {0!r} in {1!r} using delimiter '
                  '{2!r}'.format(matchstr, key, delimiter))
        match = traverse_dict_and_list(data, key, {}, delimiter=delimiter)
        if match == {}:
            continue
        if isinstance(match, dict):
            if _dict_match(match,
                           matchstr,
                           regex_match=regex_match,
                           exact_match=exact_match):
                return True
            continue
        if isinstance(match, list):
            # We are matching a single component to a single list member
            for member in match:
                if isinstance(member, dict):
                    if _dict_match(member,
                                   matchstr,
                                   regex_match=regex_match,
                                   exact_match=exact_match):
                        return True
                if _match(member,
                          matchstr,
                          regex_match=regex_match,
                          exact_match=exact_match):
                    return True
            continue
        if _match(match,
                  matchstr,
                  regex_match=regex_match,
                  exact_match=exact_match):
            return True
    return False


def traverse_dict(data, key, default, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Traverse a dict using a colon-delimited (or otherwise delimited, using the
    'delimiter' param) target string. The target 'foo:bar:baz' will return
    data['foo']['bar']['baz'] if this value exists, and will otherwise return
    the dict in the default argument.
    '''
    try:
        for each in key.split(delimiter):
            data = data[each]
    except (KeyError, IndexError, TypeError):
        # Encountered a non-indexable value in the middle of traversing
        return default
    return data


def traverse_dict_and_list(data, key, default, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Traverse a dict or list using a colon-delimited (or otherwise delimited,
    using the 'delimiter' param) target string. The target 'foo:bar:0' will
    return data['foo']['bar'][0] if this value exists, and will otherwise
    return the dict in the default argument.
    Function will automatically determine the target type.
    The target 'foo:bar:0' will return data['foo']['bar'][0] if data like
    {'foo':{'bar':['baz']}} , if data like {'foo':{'bar':{'0':'baz'}}}
    then return data['foo']['bar']['0']
    '''
    for each in key.split(delimiter):
        if isinstance(data, list):
            try:
                idx = int(each)
            except ValueError:
                embed_match = False
                # Index was not numeric, lets look at any embedded dicts
                for embedded in (x for x in data if isinstance(x, dict)):
                    try:
                        data = embedded[each]
                        embed_match = True
                        break
                    except KeyError:
                        pass
                if not embed_match:
                    # No embedded dicts matched, return the default
                    return default
            else:
                try:
                    data = data[idx]
                except IndexError:
                    return default
        else:
            try:
                data = data[each]
            except (KeyError, TypeError):
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
    Return a dict without any of the __pub* keys (or any other keys starting
    with a dunder) from the kwargs dict passed into the execution module
    functions. These keys are useful for tracking what was used to invoke
    the function call, but they may not be desierable to have if passing the
    kwargs forward wholesale.
    '''
    ret = {}
    for key, val in six.iteritems(kwargs):
        if not key.startswith('__'):
            ret[key] = val
    return ret


@real_memoize
def is_windows():
    '''
    Simple function to return if a host is Windows or not
    '''
    return sys.platform.startswith('win')


def sanitize_win_path_string(winpath):
    '''
    Remove illegal path characters for windows
    '''
    intab = '<>:|?*'
    outtab = '_' * len(intab)
    trantab = string.maketrans(intab, outtab)
    if isinstance(winpath, str):
        winpath = winpath.translate(trantab)
    elif isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), u'_') for c in intab))
    return winpath


@real_memoize
def is_linux():
    '''
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    '''
    import __main__ as main
    # This is a hack.  If a proxy minion is started by other
    # means, e.g. a custom script that creates the minion objects
    # then this will fail.
    is_proxy = False
    try:
        if 'salt-proxy-minion' in main.__file__:
            is_proxy = True
    except AttributeError:
        pass
    if is_proxy:
        return False
    else:
        return sys.platform.startswith('linux')


@real_memoize
def is_darwin():
    '''
    Simple function to return if a host is Darwin (OS X) or not
    '''
    return sys.platform.startswith('darwin')


@real_memoize
def is_sunos():
    '''
    Simple function to return if host is SunOS or not
    '''
    return sys.platform.startswith('sunos')


@real_memoize
def is_freebsd():
    '''
    Simple function to return if host is FreeBSD or not
    '''
    return sys.platform.startswith('freebsd')


def is_fcntl_available(check_sunos=False):
    '''
    Simple function to check if the `fcntl` module is available or not.

    If `check_sunos` is passed as `True` an additional check to see if host is
    SunOS is also made. For additional information see: http://goo.gl/159FF8
    '''
    if check_sunos and is_sunos():
        return False
    return HAS_FCNTL


def check_include_exclude(path_str, include_pat=None, exclude_pat=None):
    '''
    Check for glob or regexp patterns for include_pat and exclude_pat in the
    'path_str' string and return True/False conditions as follows.
      - Default: return 'True' if no include_pat or exclude_pat patterns are
        supplied
      - If only include_pat or exclude_pat is supplied: return 'True' if string
        passes the include_pat test or fails exclude_pat test respectively
      - If both include_pat and exclude_pat are supplied: return 'True' if
        include_pat matches AND exclude_pat does not match
    '''
    ret = True  # -- default true
    # Before pattern match, check if it is regexp (E@'') or glob(default)
    if include_pat:
        if re.match('E@', include_pat):
            retchk_include = True if re.search(
                include_pat[2:],
                path_str
            ) else False
        else:
            retchk_include = True if fnmatch.fnmatch(
                path_str,
                include_pat
            ) else False

    if exclude_pat:
        if re.match('E@', exclude_pat):
            retchk_exclude = False if re.search(
                exclude_pat[2:],
                path_str
            ) else True
        else:
            retchk_exclude = False if fnmatch.fnmatch(
                path_str,
                exclude_pat
            ) else True

    # Now apply include/exclude conditions
    if include_pat and not exclude_pat:
        ret = retchk_include
    elif exclude_pat and not include_pat:
        ret = retchk_exclude
    elif include_pat and exclude_pat:
        ret = retchk_include and retchk_exclude
    else:
        ret = True

    return ret


def gen_state_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return '{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def check_state_result(running):
    '''
    Check the total return value of the run and determine if the running
    dict has any issues
    '''
    if not isinstance(running, dict):
        return False

    if not running:
        return False

    ret = True
    for state_result in six.itervalues(running):
        if not isinstance(state_result, dict):
            # return false when hosts return a list instead of a dict
            ret = False
        if ret:
            result = state_result.get('result', _empty)
            if result is False:
                ret = False
            # only override return value if we are not already failed
            elif (
                result is _empty
                and isinstance(state_result, dict)
                and ret
            ):
                ret = check_state_result(state_result)
        # return as soon as we got a failure
        if not ret:
            break
    return ret


def test_mode(**kwargs):
    '''
    Examines the kwargs passed and returns True if any kwarg which matching
    "Test" in any variation on capitalization (i.e. "TEST", "Test", "TeSt",
    etc) contains a True value (as determined by salt.utils.is_true).
    '''
    for arg, value in six.iteritems(kwargs):
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
    elif isinstance(value, six.string_types):
        return str(value).lower() == 'true'
    else:
        return bool(value)


def exactly_n(l, n=1):
    '''
    Tests that exactly N items in an iterable are "truthy" (neither None,
    False, nor 0).
    '''
    i = iter(l)
    return all(any(i) for j in range(n)) and not any(i)


def exactly_one(l):
    return exactly_n(l)


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
    sources = (
        (opts, value),
        (pillar, 'master:{0}'.format(value)),
        (pillar, value),
    )
    for source, val in sources:
        out = traverse_dict_and_list(source, val, default)
        if out is not default:
            return out
    return default


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


def print_cli(msg):
    '''
    Wrapper around print() that suppresses tracebacks on broken pipes (i.e.
    when salt output is piped to less and less is stopped prematurely).
    '''
    try:
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('utf-8'))
    except IOError as exc:
        if exc.errno != errno.EPIPE:
            raise


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


def get_hash(path, form='md5', chunk_size=65536):
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
        if isinstance(date, six.string_types):
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
    except Exception:
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
    '2002-12-25'
    >>> src = '2002/12/25'
    >>> date_format(src)
    '2002-12-25'
    >>> src = 1040814000
    >>> date_format(src)
    '2002-12-25'
    >>> src = '1040814000'
    >>> date_format(src)
    '2002-12-25'
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
                                six.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, six.string_types):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until()
        stacklevel = 2

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if _version_ >= version:
        import inspect
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        raise RuntimeError(
            'The warning triggered on filename {filename!r}, line number '
            '{lineno}, is supposed to be shown until version '
            '{until_version} is released. Current version is now '
            '{salt_version}. Please remove the warning.'.format(
                filename=caller.filename,
                lineno=caller.lineno,
                until_version=version.formatted_version,
                salt_version=_version_.formatted_version
            ),
        )

    if _dont_call_warnings is False:
        def _formatwarning(message,
                           category,
                           filename,
                           lineno,
                           line=None):  # pylint: disable=W0613
            '''
            Replacement for warnings.formatwarning that disables the echoing of
            the 'line' parameter.
            '''
            return '{0}:{1}: {2}: {3}'.format(
                filename, lineno, category.__name__, message
            )
        saved = warnings.formatwarning
        warnings.formatwarning = _formatwarning
        warnings.warn(
            message.format(version=version.formatted_version),
            category,
            stacklevel=stacklevel
        )
        warnings.formatwarning = saved


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
                                six.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, six.string_types):
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
        # pylint: disable=no-member
        if distutils.version.LooseVersion(pkg1) < \
                distutils.version.LooseVersion(pkg2):
            return -1
        elif distutils.version.LooseVersion(pkg1) == \
                distutils.version.LooseVersion(pkg2):
            return 0
        elif distutils.version.LooseVersion(pkg1) > \
                distutils.version.LooseVersion(pkg2):
            return 1
        # pylint: disable=no-member
    except Exception as exc:
        log.exception(exc)
    return None


def compare_versions(ver1='', oper='==', ver2='', cmp_func=None):
    '''
    Compares two version numbers. Accepts a custom function to perform the
    cmp-style version comparison, otherwise uses version_cmp().
    '''
    cmp_map = {'<': (-1,), '<=': (-1, 0), '==': (0,),
               '>=': (0, 1), '>': (1,)}
    if oper not in ['!='] and oper not in cmp_map:
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
    for key in set((new or {})).union((old or {})):
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
    argspec function signatures
    '''
    ret = {}
    # TODO: cp.get_file will also match cp.get_file_str. this is the
    # same logic as sys.doc, and it is not working as expected, see
    # issue #3614
    _use_fnmatch = False
    if '*' in module:
        target_mod = module
        _use_fnmatch = True
    elif module:
        # allow both "sys" and "sys." to match sys, without also matching
        # sysctl
        target_module = module + '.' if not module.endswith('.') else module
    else:
        target_module = ''
    if _use_fnmatch:
        for fun in fnmatch.filter(functions, target_mod):
            try:
                aspec = salt.utils.args.get_function_argspec(functions[fun])
            except TypeError:
                # this happens if not callable
                continue

            args, varargs, kwargs, defaults = aspec

            ret[fun] = {}
            ret[fun]['args'] = args if args else None
            ret[fun]['defaults'] = defaults if defaults else None
            ret[fun]['varargs'] = True if varargs else None
            ret[fun]['kwargs'] = True if kwargs else None

    else:
        for fun in functions:
            if fun == module or fun.startswith(target_module):
                try:
                    aspec = salt.utils.args.get_function_argspec(functions[fun])
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


def decode_list(data):
    '''
    JSON decodes as unicode, Jinja needs bytes...
    '''
    rv = []
    for item in data:
        if isinstance(item, six.text_type) and six.PY2:
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
    for key, value in six.iteritems(data):
        if isinstance(key, six.text_type) and six.PY2:
            key = key.encode('utf-8')
        if isinstance(value, six.text_type) and six.PY2:
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
        with fopen(path, 'r') as fp_:
            return is_bin_str(fp_.read(2048))
    except os.error:
        return None


def is_bin_str(data):
    '''
    Detects if the passed string of data is bin or text
    '''
    if '\0' in data:
        return True
    if not data:
        return False

    text_characters = ''.join(list(map(chr, list(range(32, 127)))) + list('\n\r\t\b'))
    _null_trans = string.maketrans('', '')
    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    text = data.translate(_null_trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(text) / len(data) > 0.30:
        return True
    return False


def is_dictlist(data):
    '''
    Returns True if data is a list of one-element dicts (as found in many SLS
    schemas), otherwise returns False
    '''
    if isinstance(data, list):
        for element in data:
            if isinstance(element, dict):
                if len(element) != 1:
                    return False
            else:
                return False
        return True
    return False


def repack_dictlist(data):
    '''
    Takes a list of one-element dicts (as found in many SLS schemas) and
    repacks into a single dictionary.
    '''
    if isinstance(data, six.string_types):
        try:
            import yaml
            data = yaml.safe_load(data)
        except yaml.parser.ParserError as err:
            log.error(err)
            return {}
    if not isinstance(data, list) \
            or [x for x in data
                if not isinstance(x, (six.string_types, int, float, dict))]:
        log.error('Invalid input: {0}'.format(pprint.pformat(data)))
        log.error('Input must be a list of strings/dicts')
        return {}
    ret = {}
    for element in data:
        if isinstance(element, (six.string_types, int, float)):
            ret[element] = None
        else:
            if len(element) != 1:
                log.error('Invalid input: key/value pairs must contain '
                          'only one element (data passed: {0}).'
                          .format(element))
                return {}
            ret.update(element)
    return ret


def get_group_list(user=None, include_default=True):
    '''
    Returns a list of all of the system group names of which the user
    is a member.
    '''
    if HAS_GRP is False or HAS_PWD is False:
        # We don't work on platforms that don't have grp and pwd
        # Just return an empty list
        return []
    group_names = None
    ugroups = set()
    if not isinstance(user, six.string_types):
        raise Exception
    if hasattr(os, 'getgrouplist'):
        # Try os.getgrouplist, available in python >= 3.3
        log.trace('Trying os.getgrouplist for {0!r}'.format(user))
        try:
            group_names = [
                grp.getgrgid(grpid).gr_name for grpid in
                os.getgrouplist(user, pwd.getpwnam(user).pw_gid)
            ]
        except Exception:
            pass
    else:
        # Try pysss.getgrouplist
        log.trace('Trying pysss.getgrouplist for {0!r}'.format(user))
        try:
            import pysss  # pylint: disable=import-error
            group_names = list(pysss.getgrouplist(user))
        except Exception:
            pass
    if group_names is None:
        # Fall back to generic code
        # Include the user's default group to behave like
        # os.getgrouplist() and pysss.getgrouplist() do
        log.trace('Trying generic group list for {0!r}'.format(user))
        group_names = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
        try:
            default_group = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
            if default_group not in group_names:
                group_names.append(default_group)
        except KeyError:
            # If for some reason the user does not have a default group
            pass
    ugroups.update(group_names)
    if include_default is False:
        # Historically, saltstack code for getting group lists did not
        # include the default group. Some things may only want
        # supplemental groups, so include_default=False omits the users
        # default group.
        try:
            default_group = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
            ugroups.remove(default_group)
        except KeyError:
            # If for some reason the user does not have a default group
            pass
    log.trace('Group list for user {0!r}: {1!r}'.format(user, sorted(ugroups)))
    return sorted(ugroups)


def get_group_dict(user=None, include_default=True):
    '''
    Returns a dict of all of the system groups as keys, and group ids
    as values, of which the user is a member.
    E.g.: {'staff': 501, 'sudo': 27}
    '''
    if HAS_GRP is False or HAS_PWD is False:
        # We don't work on platforms that don't have grp and pwd
        # Just return an empty dict
        return {}
    group_dict = {}
    group_names = get_group_list(user, include_default=include_default)
    for group in group_names:
        group_dict.update({group: grp.getgrnam(group).gr_gid})
    return group_dict


def get_gid_list(user=None, include_default=True):
    '''
    Returns a list of all of the system group IDs of which the user
    is a member.
    '''
    if HAS_GRP is False or HAS_PWD is False:
        # We don't work on platforms that don't have grp and pwd
        # Just return an empty list
        return []
    gid_list = [
            gid for (group, gid) in
            six.iteritems(salt.utils.get_group_dict(user, include_default=include_default))
    ]
    return sorted(set(gid_list))


def total_seconds(td):
    '''
    Takes a timedelta and returns the total number of seconds
    represented by the object. Wrapper for the total_seconds()
    method which does not exist in versions of Python < 2.7.
    '''
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def import_json():
    '''
    Import a json module, starting with the quick ones and going down the list)
    '''
    for fast_json in ('ujson', 'yajl', 'json'):
        try:
            mod = __import__(fast_json)
            log.trace('loaded {0} json lib'.format(fast_json))
            return mod
        except ImportError:
            continue


def appendproctitle(name):
    '''
    Append "name" to the current process title
    '''
    if HAS_SETPROCTITLE:
        setproctitle.setproctitle(setproctitle.getproctitle() + ' ' + name)


def chugid(runas):
    '''
    Change the current process to belong to
    the imputed user (and the groups he belongs to)
    '''
    uinfo = pwd.getpwnam(runas)
    supgroups = []
    supgroups_seen = set()

    # The line below used to exclude the current user's primary gid.
    # However, when root belongs to more than one group
    # this causes root's primary group of '0' to be dropped from
    # his grouplist.  On FreeBSD, at least, this makes some
    # command executions fail with 'access denied'.
    #
    # The Python documentation says that os.setgroups sets only
    # the supplemental groups for a running process.  On FreeBSD
    # this does not appear to be strictly true.
    group_list = get_group_dict(runas, include_default=True)
    if sys.platform == 'darwin':
        group_list = dict((k, v) for k, v in six.iteritems(group_list)
                          if not k.startswith('_'))
    for group_name in group_list:
        gid = group_list[group_name]
        if (gid not in supgroups_seen
           and not supgroups_seen.add(gid)):
            supgroups.append(gid)

    if os.getgid() != uinfo.pw_gid:
        try:
            os.setgid(uinfo.pw_gid)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to change from gid {0} to {1}. Error: {2}'.format(
                    os.getgid(), uinfo.pw_gid, err
                )
            )

    # Set supplemental groups
    if sorted(os.getgroups()) != sorted(supgroups):
        try:
            os.setgroups(supgroups)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to set supplemental groups to {0}. Error: {1}'.format(
                    supgroups, err
                )
            )

    if os.getuid() != uinfo.pw_uid:
        try:
            os.setuid(uinfo.pw_uid)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to change from uid {0} to {1}. Error: {2}'.format(
                    os.getuid(), uinfo.pw_uid, err
                )
            )


def chugid_and_umask(runas, umask):
    '''
    Helper method for for subprocess.Popen to initialise uid/gid and umask
    for the new process.
    '''
    if runas is not None:
        chugid(runas)
    if umask is not None:
        os.umask(umask)


def rand_string(size=32):
    key = os.urandom(size)
    return key.encode('base64').replace('\n', '')


def relpath(path, start='.'):
    '''
    Work around Python bug #5117, which is not (and will not be) patched in
    Python 2.6 (http://bugs.python.org/issue5117)
    '''
    if sys.version_info < (2, 7) and 'posix' in sys.builtin_module_names:
        # The below code block is based on posixpath.relpath from Python 2.7,
        # which has the fix for this bug.
        if not path:
            raise ValueError('no path specified')

        start_list = [
            x for x in os.path.abspath(start).split(os.path.sep) if x
        ]
        path_list = [
            x for x in os.path.abspath(path).split(os.path.sep) if x
        ]

        # work out how much of the filepath is shared by start and path.
        i = len(os.path.commonprefix([start_list, path_list]))

        rel_list = [os.path.pardir] * (len(start_list)-i) + path_list[i:]
        if not rel_list:
            return os.path.curdir
        return os.path.join(*rel_list)

    return os.path.relpath(path, start=start)


def human_size_to_bytes(human_size):
    '''
    Convert human-readable units to bytes
    '''
    size_exp_map = {'K': 1, 'M': 2, 'G': 3, 'T': 4, 'P': 5}
    human_size_str = str(human_size)
    match = re.match(r'^(\d+)([KMGTP])?$', human_size_str)
    if not match:
        raise ValueError(
            'Size must be all digits, with an optional unit type '
            '(K, M, G, T, or P)'
        )
    size_num = int(match.group(1))
    unit_multiplier = 1024 ** size_exp_map.get(match.group(2), 0)
    return size_num * unit_multiplier
