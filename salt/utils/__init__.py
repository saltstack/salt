# -*- coding: utf-8 -*-
'''
Some of the utils used by salt

NOTE: The dev team is working on splitting up this file for the Oxygen release.
Please do not add any new functions to this file. New functions should be
organized in other files under salt/utils/. Please consult the dev team if you
are unsure where a new function should go.
'''

# Import python libs
from __future__ import absolute_import, division, print_function
import contextlib
import copy
import collections
import datetime
import errno
import fnmatch
import hashlib
import json
import logging
import numbers
import os
import posixpath
import random
import re
import shlex
import shutil
import socket
import stat
import sys
import pstats
import tempfile
import time
import types
import warnings
import string
import subprocess
import getpass

# Import 3rd-party libs
from salt.ext import six
# pylint: disable=import-error
from salt.ext.six.moves.urllib.parse import urlparse  # pylint: disable=no-name-in-module
# pylint: disable=redefined-builtin
from salt.ext.six.moves import range
from salt.ext.six.moves import zip
from stat import S_IMODE
# pylint: enable=import-error,redefined-builtin

if six.PY3:
    import importlib.util  # pylint: disable=no-name-in-module,import-error
else:
    import imp

try:
    import cProfile
    HAS_CPROFILE = True
except ImportError:
    HAS_CPROFILE = False

# Import 3rd-party libs
try:
    import Crypto.Random
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

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
    import salt.utils.win_functions
    HAS_WIN_FUNCTIONS = True
except ImportError:
    HAS_WIN_FUNCTIONS = False

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
except (ImportError, OSError, AttributeError, TypeError):
    HAS_RESINIT = False

# Import salt libs
from salt.defaults import DEFAULT_TARGET_DELIM
import salt.defaults.exitcodes
import salt.log
import salt.utils.dictupdate
import salt.version
from salt.utils.decorators import memoize as real_memoize
from salt.utils.versions import LooseVersion as _LooseVersion
from salt.textformat import TextFormat
from salt.exceptions import (
    CommandExecutionError, SaltClientError,
    CommandNotFoundError, SaltSystemExit,
    SaltInvocationError, SaltException
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


def is_hex(value):
    '''
    Returns True if value is a hexidecimal string, otherwise returns False
    '''
    try:
        int(value, 16)
        return True
    except (TypeError, ValueError):
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
    buf = [to_str(i) if isinstance(i, six.text_type) else i for i in buf]

    return '---\n{0}\n---'.format('\n'.join(buf))


def get_user():
    '''
    Get the current user
    '''
    if HAS_PWD:
        return pwd.getpwuid(os.geteuid()).pw_name
    elif HAS_WIN_FUNCTIONS and salt.utils.win_functions.HAS_WIN32:
        return salt.utils.win_functions.get_current_user()
    else:
        raise CommandExecutionError("Required external libraries not found. Need 'pwd' or 'win32api")


def get_uid(user=None):
    """
    Get the uid for a given user name. If no user given,
    the current euid will be returned. If the user
    does not exist, None will be returned. On
    systems which do not support pwd or os.geteuid
    it will return None.
    """
    if not HAS_PWD:
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


def _win_user_token_is_admin(user_token):
    '''
    Using the win32 api, determine if the user with token 'user_token' has
    administrator rights.

    See MSDN entry here:
        http://msdn.microsoft.com/en-us/library/aa376389(VS.85).aspx
    '''
    class SID_IDENTIFIER_AUTHORITY(ctypes.Structure):
        _fields_ = [
            ("byte0", ctypes.c_byte),
            ("byte1", ctypes.c_byte),
            ("byte2", ctypes.c_byte),
            ("byte3", ctypes.c_byte),
            ("byte4", ctypes.c_byte),
            ("byte5", ctypes.c_byte),
        ]
    nt_authority = SID_IDENTIFIER_AUTHORITY()
    nt_authority.byte5 = 5

    SECURITY_BUILTIN_DOMAIN_RID = 0x20
    DOMAIN_ALIAS_RID_ADMINS = 0x220
    administrators_group = ctypes.c_void_p()
    if ctypes.windll.advapi32.AllocateAndInitializeSid(
            ctypes.byref(nt_authority),
            2,
            SECURITY_BUILTIN_DOMAIN_RID,
            DOMAIN_ALIAS_RID_ADMINS,
            0, 0, 0, 0, 0, 0,
            ctypes.byref(administrators_group)) == 0:
        raise Exception("AllocateAndInitializeSid failed")

    try:
        is_admin = ctypes.wintypes.BOOL()
        if ctypes.windll.advapi32.CheckTokenMembership(
                user_token,
                administrators_group,
                ctypes.byref(is_admin)) == 0:
            raise Exception("CheckTokenMembership failed")
        return is_admin.value != 0

    finally:
        ctypes.windll.advapi32.FreeSid(administrators_group)


def _win_current_user_is_admin():
    '''
    ctypes.windll.shell32.IsUserAnAdmin() is intentionally avoided due to this
    function being deprecated.
    '''
    return _win_user_token_is_admin(0)


def get_specific_user():
    '''
    Get a user name for publishing. If you find the user is "root" attempt to be
    more specific
    '''
    user = get_user()
    if is_windows():
        if _win_current_user_is_admin():
            return 'sudo_{0}'.format(user)
    else:
        env_vars = ('SUDO_USER',)
        if user == 'root':
            for evar in env_vars:
                if evar in os.environ:
                    return 'sudo_{0}'.format(os.environ[evar])
    return user


def get_master_key(key_user, opts, skip_perm_errors=False):
    if key_user == 'root':
        if opts.get('user', 'root') != 'root':
            key_user = opts.get('user', 'root')
    if key_user.startswith('sudo_'):
        key_user = opts.get('user', 'root')
    if salt.utils.is_windows():
        # The username may contain '\' if it is in Windows
        # 'DOMAIN\username' format. Fix this for the keyfile path.
        key_user = key_user.replace('\\', '_')
    keyfile = os.path.join(opts['cachedir'],
                           '.{0}_key'.format(key_user))
    # Make sure all key parent directories are accessible
    salt.utils.verify.check_path_traversal(opts['cachedir'],
                                           key_user,
                                           skip_perm_errors)

    try:
        with salt.utils.fopen(keyfile, 'r') as key:
            return key.read()
    except (OSError, IOError):
        # Fall back to eauth
        return ''


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
    os.umask(0o022)  # pylint: disable=blacklisted-function

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
            # Redirect python stdin/out/err
            # and the os stdin/out/err which can be different
            os.dup2(dev_null.fileno(), sys.stdin.fileno())
            os.dup2(dev_null.fileno(), sys.stdout.fileno())
            os.dup2(dev_null.fileno(), sys.stderr.fileno())
            os.dup2(dev_null.fileno(), 0)
            os.dup2(dev_null.fileno(), 1)
            os.dup2(dev_null.fileno(), 2)


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


def rand_str(size=9999999999, hash_type=None):
    '''
    Return a random string
    '''
    if not hash_type:
        hash_type = 'md5'
    hasher = getattr(hashlib, hash_type)
    return hasher(to_bytes(str(random.SystemRandom().randint(0, size)))).hexdigest()


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

        ext_list = os.environ.get('PATHEXT', '.EXE').split(';')

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

        # Enhance POSIX path for the reliability at some environments, when $PATH is changing
        # This also keeps order, where 'first came, first win' for cases to find optional alternatives
        search_path = os.environ.get('PATH') and os.environ['PATH'].split(os.pathsep) or list()
        for default_path in ['/bin', '/sbin', '/usr/bin', '/usr/sbin', '/usr/local/bin']:
            if default_path not in search_path:
                search_path.append(default_path)
        os.environ['PATH'] = os.pathsep.join(search_path)
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
        log.trace('\'{0}\' could not be found in the following search path: \'{1}\''.format(exe, search_path))
    else:
        log.error('No executable was passed to be searched by salt.utils.which()')

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


def activate_profile(test=True):
    pr = None
    if test:
        if HAS_CPROFILE:
            pr = cProfile.Profile()
            pr.enable()
        else:
            log.error('cProfile is not available on your platform')
    return pr


def output_profile(pr, stats_path='/tmp/stats', stop=False, id_=None):
    if pr is not None and HAS_CPROFILE:
        try:
            pr.disable()
            if not os.path.isdir(stats_path):
                os.makedirs(stats_path)
            date = datetime.datetime.now().isoformat()
            if id_ is None:
                id_ = rand_str(size=32)
            ficp = os.path.join(stats_path, '{0}.{1}.pstats'.format(id_, date))
            fico = os.path.join(stats_path, '{0}.{1}.dot'.format(id_, date))
            ficn = os.path.join(stats_path, '{0}.{1}.stats'.format(id_, date))
            if not os.path.exists(ficp):
                pr.dump_stats(ficp)
                with fopen(ficn, 'w') as fic:
                    pstats.Stats(pr, stream=fic).sort_stats('cumulative')
            log.info('PROFILING: {0} generated'.format(ficp))
            log.info('PROFILING (cumulative): {0} generated'.format(ficn))
            pyprof = which('pyprof2calltree')
            cmd = [pyprof, '-i', ficp, '-o', fico]
            if pyprof:
                failed = False
                try:
                    pro = subprocess.Popen(
                        cmd, shell=False,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except OSError:
                    failed = True
                if pro.returncode:
                    failed = True
                if failed:
                    log.error('PROFILING (dot problem')
                else:
                    log.info('PROFILING (dot): {0} generated'.format(fico))
                log.trace('pyprof2calltree output:')
                log.trace(to_str(pro.stdout.read()).strip() +
                          to_str(pro.stderr.read()).strip())
            else:
                log.info('You can run {0} for additional stats.'.format(cmd))
        finally:
            if not stop:
                pr.enable()
    return pr


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


def mac_str_to_bytes(mac_str):
    '''
    Convert a MAC address string into bytes. Works with or without separators:

    b1 = mac_str_to_bytes('08:00:27:13:69:77')
    b2 = mac_str_to_bytes('080027136977')
    assert b1 == b2
    assert isinstance(b1, bytes)
    '''
    if len(mac_str) == 12:
        pass
    elif len(mac_str) == 17:
        sep = mac_str[2]
        mac_str = mac_str.replace(sep, '')
    else:
        raise ValueError('Invalid MAC address')
    if six.PY3:
        mac_bytes = bytes(int(mac_str[s:s+2], 16) for s in range(0, 12, 2))
    else:
        mac_bytes = ''.join(chr(int(mac_str[s:s+2], 16)) for s in range(0, 12, 2))
    return mac_bytes


def ip_bracket(addr):
    '''
    Convert IP address representation to ZMQ (URL) format. ZMQ expects
    brackets around IPv6 literals, since they are used in URLs.
    '''
    if addr and ':' in addr and not addr.startswith('['):
        return '[{0}]'.format(addr)
    return addr


def dns_check(addr, port, safe=False, ipv6=None):
    '''
    Return the ip resolved by dns, but do not exit on failure, only raise an
    exception. Obeys system preference for IPv4/6 address resolution.
    Tries to connect to the address before considering it useful. If no address
    can be reached, the first one resolved is used as a fallback.
    '''
    error = False
    lookup = addr
    seen_ipv6 = False
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
            resolved = False
            candidates = []
            for h in hostnames:
                # It's an IP address, just return it
                if h[4][0] == addr:
                    resolved = addr
                    break

                if h[0] == socket.AF_INET and ipv6 is True:
                    continue
                if h[0] == socket.AF_INET6 and ipv6 is False:
                    continue

                candidate_addr = ip_bracket(h[4][0])

                if h[0] != socket.AF_INET6 or ipv6 is not None:
                    candidates.append(candidate_addr)

                try:
                    s = socket.socket(h[0], socket.SOCK_STREAM)
                    s.connect((candidate_addr.strip('[]'), port))
                    s.close()

                    resolved = candidate_addr
                    break
                except socket.error:
                    pass
            if not resolved:
                if len(candidates) > 0:
                    resolved = candidates[0]
                else:
                    error = True
    except TypeError:
        err = ('Attempt to resolve address \'{0}\' failed. Invalid or unresolveable address').format(lookup)
        raise SaltSystemExit(code=42, msg=err)
    except socket.error:
        error = True

    if error:
        err = ('DNS lookup or connection check of \'{0}\' failed.').format(addr)
        if safe:
            if salt.log.is_console_configured():
                # If logging is not configured it also means that either
                # the master or minion instance calling this hasn't even
                # started running
                log.error(err)
            raise SaltClientError()
        raise SaltSystemExit(code=42, msg=err)
    return resolved


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
            if six.PY3:
                if importlib.util.find_spec(mod) is None:  # pylint: disable=no-member
                    ret.append(mod)
            else:
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
        raise CommandNotFoundError('\'{0}\' is not in the path'.format(command))


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


def path_join(*parts, **kwargs):
    '''
    This functions tries to solve some issues when joining multiple absolute
    paths on both *nix and windows platforms.

    See tests/unit/utils/path_join_test.py for some examples on what's being
    talked about here.

    The "use_posixpath" kwarg can be be used to force joining using poxixpath,
    which is useful for Salt fileserver paths on Windows masters.
    '''
    if six.PY3:
        new_parts = []
        for part in parts:
            new_parts.append(to_str(part))
        parts = new_parts

    kwargs = salt.utils.clean_kwargs(**kwargs)
    use_posixpath = kwargs.pop('use_posixpath', False)
    if kwargs:
        invalid_kwargs(kwargs)

    pathlib = posixpath if use_posixpath else os.path

    # Normalize path converting any os.sep as needed
    parts = [pathlib.normpath(p) for p in parts]

    try:
        root = parts.pop(0)
    except IndexError:
        # No args passed to func
        return ''

    if not parts:
        ret = root
    else:
        stripped = [p.lstrip(os.sep) for p in parts]
        try:
            ret = pathlib.join(root, *stripped)
        except UnicodeDecodeError:
            # This is probably Python 2 and one of the parts contains unicode
            # characters in a bytestring. First try to decode to the system
            # encoding.
            try:
                enc = __salt_system_encoding__
            except NameError:
                enc = sys.stdin.encoding or sys.getdefaultencoding()
            try:
                ret = pathlib.join(root.decode(enc),
                                   *[x.decode(enc) for x in stripped])
            except UnicodeDecodeError:
                # Last resort, try UTF-8
                ret = pathlib.join(root.decode('UTF-8'),
                                   *[x.decode('UTF-8') for x in stripped])
    return pathlib.normpath(ret)


def pem_finger(path=None, key=None, sum_type='sha256'):
    '''
    Pass in either a raw pem string, or the path on disk to the location of a
    pem file, and the type of cryptographic hash to use. The default is SHA256.
    The fingerprint of the pem will be returned.

    If neither a key nor a path are passed in, a blank string will be returned.
    '''
    if not key:
        if not os.path.isfile(path):
            return ''

        with fopen(path, 'rb') as fp_:
            key = b''.join([x for x in fp_.readlines() if x.strip()][1:-1])

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
                expected_extra_kws=(),
                is_class_method=None):
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
    :param is_class_method: Pass True if you are sure that the function being passed
                            is a class method. The reason for this is that on Python 3
                            ``inspect.ismethod`` only returns ``True`` for bound methods,
                            while on Python 2, it returns ``True`` for bound and unbound
                            methods. So, on Python 3, in case of a class method, you'd
                            need the class to which the function belongs to be instantiated
                            and this is not always wanted.
    :returns: A dictionary with the function required arguments and keyword
              arguments.
    '''
    ret = initial_ret is not None and initial_ret or {}

    ret['args'] = []
    ret['kwargs'] = {}

    aspec = salt.utils.args.get_function_argspec(fun, is_class_method=is_class_method)

    arg_data = arg_lookup(fun, aspec)
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

    # We'll be showing errors to the users until Salt Fluorine comes out, after
    # which, errors will be raised instead.
    warn_until(
        'Fluorine',
        'It\'s time to start raising `SaltInvocationError` instead of '
        'returning warnings',
        # Let's not show the deprecation warning on the console, there's no
        # need.
        _dont_call_warnings=True
    )

    if extra:
        # Found unexpected keyword arguments, raise an error to the user
        if len(extra) == 1:
            msg = '\'{0[0]}\' is an invalid keyword argument for \'{1}\''.format(
                list(extra.keys()),
                ret.get(
                    # In case this is being called for a state module
                    'full',
                    # Not a state module, build the name
                    '{0}.{1}'.format(fun.__module__, fun.__name__)
                )
            )
        else:
            msg = '{0} and \'{1}\' are invalid keyword arguments for \'{2}\''.format(
                ', '.join(['\'{0}\''.format(e) for e in extra][:-1]),
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
            'Fluorine is out.{1}'.format(
                msg,
                '' if 'full' not in ret else ' Please update your state files.'
            )
        )

        # Lets pack the current extra kwargs as template context
        ret.setdefault('context', {}).update(extra)
    return ret


def arg_lookup(fun, aspec=None):
    '''
    Return a dict containing the arguments and default arguments to the
    function.
    '''
    ret = {'kwargs': {}}
    if aspec is None:
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
    int2byte = (lambda x: bytes((x,))) if six.PY3 else chr
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
    try:
        block.decode('utf-8')
        return True
    except UnicodeDecodeError:
        pass

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
    # ensure 'binary' mode is always used on Windows in Python 2
    if ((six.PY2 and is_windows() and 'binary' not in kwargs) or
            kwargs.pop('binary', False)):
        if len(args) > 1:
            args = list(args)
            if 'b' not in args[1]:
                args[1] = args[1].replace('t', 'b')
                if 'b' not in args[1]:
                    args[1] += 'b'
        elif kwargs.get('mode'):
            if 'b' not in kwargs['mode']:
                kwargs['mode'] = kwargs['mode'].replace('t', 'b')
                if 'b' not in kwargs['mode']:
                    kwargs['mode'] += 'b'
        else:
            # the default is to read
            kwargs['mode'] = 'rb'
    elif six.PY3 and 'encoding' not in kwargs:
        # In Python 3, if text mode is used and the encoding
        # is not specified, set the encoding to 'utf-8'.
        binary = False
        if len(args) > 1:
            args = list(args)
            if 'b' in args[1]:
                binary = True
        if kwargs.get('mode', None):
            if 'b' in kwargs['mode']:
                binary = True
        if not binary:
            kwargs['encoding'] = __salt_system_encoding__

    if six.PY3 and not binary and not kwargs.get('newline', None):
        kwargs['newline'] = ''

    fhandle = open(*args, **kwargs)  # pylint: disable=resource-leakage

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

    value
        The item to check the whitelist and/or blacklist against.

    whitelist
        The list of items that are white-listed. If ``value`` is found
        in the whitelist, then the function returns ``True``. Otherwise,
        it returns ``False``.

    blacklist
        The list of items that are black-listed. If ``value`` is found
        in the blacklist, then the function returns ``False``. Otherwise,
        it returns ``True``.

    If both a whitelist and a blacklist are provided, value membership
    in the blacklist will be examined first. If the value is not found
    in the blacklist, then the whitelist is checked. If the value isn't
    found in the whitelist, the function returns ``False``.
    '''
    if blacklist is not None:
        if not hasattr(blacklist, '__iter__'):
            blacklist = [blacklist]
        try:
            for expr in blacklist:
                if expr_match(value, expr):
                    return False
        except TypeError:
            log.error('Non-iterable blacklist {0}'.format(blacklist))

    if whitelist:
        if not hasattr(whitelist, '__iter__'):
            whitelist = [whitelist]
        try:
            for expr in whitelist:
                if expr_match(value, expr):
                    return True
        except TypeError:
            log.error('Non-iterable whitelist {0}'.format(whitelist))
    else:
        return True

    return False


def get_values_of_matching_keys(pattern_dict, user_name):
    '''
    Check a whitelist and/or blacklist to see if the value matches it.
    '''
    ret = []
    for expr in pattern_dict:
        if expr_match(user_name, expr):
            ret.extend(pattern_dict[expr])
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
                log.error('Invalid regex \'{0}\' in match'.format(pattern))
                return False
        elif exact_match:
            return str(target).lower() == pattern.lower()
        else:
            return fnmatch.fnmatch(str(target).lower(), pattern.lower())

    def _dict_match(target, pattern, regex_match=False, exact_match=False):
        wildcard = pattern.startswith('*:')
        if wildcard:
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
        if wildcard:
            for key in target:
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
        log.debug('Attempting to match \'{0}\' in \'{1}\' using delimiter '
                  '\'{2}\''.format(matchstr, key, delimiter))
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


def traverse_dict(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
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


def traverse_dict_and_list(data, key, default=None, delimiter=DEFAULT_TARGET_DELIM):
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


def clean_kwargs(**kwargs):
    '''
    Return a dict without any of the __pub* keys (or any other keys starting
    with a dunder) from the kwargs dict passed into the execution module
    functions. These keys are useful for tracking what was used to invoke
    the function call, but they may not be desirable to have if passing the
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
    trantab = ''.maketrans(intab, outtab) if six.PY3 else string.maketrans(intab, outtab)  # pylint: disable=no-member
    if isinstance(winpath, str):
        winpath = winpath.translate(trantab)
    elif isinstance(winpath, six.text_type):
        winpath = winpath.translate(dict((ord(c), u'_') for c in intab))
    return winpath


@real_memoize
def is_proxy():
    '''
    Return True if this minion is a proxy minion.
    Leverages the fact that is_linux() and is_windows
    both return False for proxies.
    TODO: Need to extend this for proxies that might run on
    other Unices
    '''
    import __main__ as main
    # This is a hack.  If a proxy minion is started by other
    # means, e.g. a custom script that creates the minion objects
    # then this will fail.
    is_proxy = False
    try:
        # Changed this from 'salt-proxy in main...' to 'proxy in main...'
        # to support the testsuite's temp script that is called 'cli_salt_proxy'
        if 'proxy' in main.__file__:
            is_proxy = True
    except AttributeError:
        pass
    return is_proxy


@real_memoize
def is_linux():
    '''
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    '''
    return sys.platform.startswith('linux')


@real_memoize
def is_darwin():
    '''
    Simple function to return if a host is Darwin (macOS) or not
    '''
    return sys.platform.startswith('darwin')


@real_memoize
def is_sunos():
    '''
    Simple function to return if host is SunOS or not
    '''
    return sys.platform.startswith('sunos')


@real_memoize
def is_smartos():
    '''
    Simple function to return if host is SmartOS (Illumos) or not
    '''
    if not is_sunos():
        return False
    else:
        return os.uname()[3].startswith('joyent_')


@real_memoize
def is_smartos_globalzone():
    '''
    Function to return if host is SmartOS (Illumos) global zone or not
    '''
    if not is_smartos():
        return False
    else:
        cmd = ['zonename']
        try:
            zonename = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            return False
        if zonename.returncode:
            return False
        if zonename.stdout.read().strip() == 'global':
            return True

        return False


@real_memoize
def is_smartos_zone():
    '''
    Function to return if host is SmartOS (Illumos) and not the gz
    '''
    if not is_smartos():
        return False
    else:
        cmd = ['zonename']
        try:
            zonename = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            return False
        if zonename.returncode:
            return False
        if zonename.stdout.read().strip() == 'global':
            return False

        return True


@real_memoize
def is_freebsd():
    '''
    Simple function to return if host is FreeBSD or not
    '''
    return sys.platform.startswith('freebsd')


@real_memoize
def is_netbsd():
    '''
    Simple function to return if host is NetBSD or not
    '''
    return sys.platform.startswith('netbsd')


@real_memoize
def is_openbsd():
    '''
    Simple function to return if host is OpenBSD or not
    '''
    return sys.platform.startswith('openbsd')


@real_memoize
def is_aix():
    '''
    Simple function to return if host is AIX or not
    '''
    return sys.platform.startswith('aix')


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


def search_onfail_requisites(sid, highstate):
    """
    For a particular low chunk, search relevant onfail related
    states
    """
    onfails = []
    if '_|-' in sid:
        st = salt.state.split_low_tag(sid)
    else:
        st = {'__id__': sid}
    for fstate, fchunks in six.iteritems(highstate):
        if fstate == st['__id__']:
            continue
        else:
            for mod_, fchunk in six.iteritems(fchunks):
                if (
                    not isinstance(mod_, six.string_types) or
                    mod_.startswith('__')
                ):
                    continue
                else:
                    if not isinstance(fchunk, list):
                        continue
                    else:
                        for fdata in fchunk:
                            if not isinstance(fdata, dict):
                                continue
                            # bydefault onfail will fail, but you can
                            # set onfail_stop: False to prevent the highstate
                            # to stop if you handle it
                            if fdata.get('onfail_stop', True):
                                continue
                            for knob, fvalue in six.iteritems(fdata):
                                if knob != 'onfail':
                                    continue
                                for freqs in fvalue:
                                    for fmod, fid in six.iteritems(freqs):
                                        if not (
                                            fid == st['__id__'] and
                                            fmod == st.get('state', fmod)
                                        ):
                                            continue
                                        onfails.append((fstate, mod_, fchunk))
    return onfails


def check_onfail_requisites(state_id, state_result, running, highstate):
    '''
    When a state fail and is part of a highstate, check
    if there is onfail requisites.
    When we find onfail requisites, we will consider the state failed
    only if at least one of those onfail requisites also failed

    Returns:

        True: if onfail handlers suceeded
        False: if one on those handler failed
        None: if the state does not have onfail requisites

    '''
    nret = None
    if (
        state_id and state_result and
        highstate and isinstance(highstate, dict)
    ):
        onfails = search_onfail_requisites(state_id, highstate)
        if onfails:
            for handler in onfails:
                fstate, mod_, fchunk = handler
                ofresult = True
                for rstateid, rstate in six.iteritems(running):
                    if '_|-' in rstateid:
                        st = salt.state.split_low_tag(rstateid)
                    # in case of simple state, try to guess
                    else:
                        id_ = rstate.get('__id__', rstateid)
                        if not id_:
                            raise ValueError('no state id')
                        st = {'__id__': id_, 'state': mod_}
                    if mod_ == st['state'] and fstate == st['__id__']:
                        ofresult = rstate.get('result', _empty)
                        if ofresult in [False, True]:
                            nret = ofresult
                        if ofresult is False:
                            # as soon as we find an errored onfail, we stop
                            break
                # consider that if we parsed onfailes without changing
                # the ret, that we have failed
                if nret is None:
                    nret = False
    return nret


def check_state_result(running, recurse=False, highstate=None):
    '''
    Check the total return value of the run and determine if the running
    dict has any issues
    '''
    if not isinstance(running, dict):
        return False

    if not running:
        return False

    ret = True
    for state_id, state_result in six.iteritems(running):
        expected_type = dict
        # The __extend__ state is a list
        if "__extend__" == state_id:
            expected_type = list
        if not recurse and not isinstance(state_result, expected_type):
            ret = False
        if ret and isinstance(state_result, dict):
            result = state_result.get('result', _empty)
            if result is False:
                ret = False
            # only override return value if we are not already failed
            elif result is _empty and isinstance(state_result, dict) and ret:
                ret = check_state_result(
                    state_result, recurse=True, highstate=highstate)
        # if we detect a fail, check for onfail requisites
        if not ret:
            # ret can be None in case of no onfail reqs, recast it to bool
            ret = bool(check_onfail_requisites(state_id, state_result,
                                               running, highstate))
        # return as soon as we got a failure
        if not ret:
            break
    return ret


def st_mode_to_octal(mode):
    '''
    Convert the st_mode value from a stat(2) call (as returned from os.stat())
    to an octal mode.
    '''
    try:
        return oct(mode)[-4:]
    except (TypeError, IndexError):
        return ''


def normalize_mode(mode):
    '''
    Return a mode value, normalized to a string and containing a leading zero
    if it does not have one.

    Allow "keep" as a valid mode (used by file state/module to preserve mode
    from the Salt fileserver in file states).
    '''
    if mode is None:
        return None
    if not isinstance(mode, six.string_types):
        mode = str(mode)
    if six.PY3:
        mode = mode.replace('0o', '0')
    # Strip any quotes any initial zeroes, then though zero-pad it up to 4.
    # This ensures that somethign like '00644' is normalized to '0644'
    return mode.strip('"').strip('\'').lstrip('0').zfill(4)


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
    if isinstance(value, (six.integer_types, float)):
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
    '''
    Check if only one item is not None, False, or 0 in an iterable.
    '''
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
            raise  # pylint: disable=E0704
    if os.path.islink(path) or not os.path.isdir(path):
        os.remove(path)
    else:
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


def print_cli(msg, retries=10, step=0.01):
    '''
    Wrapper around print() that suppresses tracebacks on broken pipes (i.e.
    when salt output is piped to less and less is stopped prematurely).
    '''
    while retries:
        try:
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode('utf-8'))
        except IOError as exc:
            err = "{0}".format(exc)
            if exc.errno != errno.EPIPE:
                if (
                    ("temporarily unavailable" in err or
                     exc.errno in (errno.EAGAIN,)) and
                    retries
                ):
                    time.sleep(step)
                    retries -= 1
                    continue
                else:
                    raise
        break


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


def get_hash(path, form='sha256', chunk_size=65536):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``
    '''
    hash_type = hasattr(hashlib, form) and getattr(hashlib, form) or None
    if hash_type is None:
        raise ValueError('Invalid hash type: {0}'.format(form))

    with salt.utils.fopen(path, 'rb') as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b''):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


def namespaced_function(function, global_dict, defaults=None, preserve_context=False):
    '''
    Redefine (clone) a function under a different globals() namespace scope

        preserve_context:
            Allow keeping the context taken from orignal namespace,
            and extend it with globals() taken from
            new targetted namespace.
    '''
    if defaults is None:
        defaults = function.__defaults__

    if preserve_context:
        _global_dict = function.__globals__.copy()
        _global_dict.update(global_dict)
        global_dict = _global_dict
    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=defaults,
        closure=function.__closure__
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def alias_function(fun, name, doc=None):
    '''
    Copy a function
    '''
    alias_fun = types.FunctionType(fun.__code__,
                                   fun.__globals__,
                                   name,
                                   fun.__defaults__,
                                   fun.__closure__)
    alias_fun.__dict__.update(fun.__dict__)

    if doc and isinstance(doc, six.string_types):
        alias_fun.__doc__ = doc
    else:
        orig_name = fun.__name__
        alias_msg = ('\nThis function is an alias of '
                     '``{0}``.\n'.format(orig_name))
        alias_fun.__doc__ = alias_msg + fun.__doc__

    return alias_fun


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
                    # py3: yes, timelib.strtodatetime wants bytes, not str :/
                    return timelib.strtodatetime(to_bytes(date))
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

        raise RuntimeError(
                'Unable to parse {0}. Consider installing timelib'.format(date))


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
            'The warning triggered on filename \'{filename}\', line number '
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
            return '{0}:{1}: {2}: {3}\n'.format(
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
    :ref:`the deprecation development docs <deprecations>`
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
        arg_names = ', '.join('\'{0}\''.format(key) for key in kwargs)
        warn_until(
            version,
            message='The following parameter(s) have been deprecated and '
                    'will be removed in \'{0}\': {1}.'.format(version.string,
                                                              arg_names),
            category=category,
            stacklevel=stacklevel,
            _version_info_=_version_.info,
            _dont_call_warnings=_dont_call_warnings
        )


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    '''
    Compares two version strings using salt.utils.versions.LooseVersion. This is
    a fallback for providers which don't have a version comparison utility
    built into them.  Return -1 if version1 < version2, 0 if version1 ==
    version2, and 1 if version1 > version2. Return None if there was a problem
    making the comparison.
    '''
    normalize = lambda x: str(x).split(':', 1)[-1] if ignore_epoch else str(x)
    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    try:
        # pylint: disable=no-member
        if _LooseVersion(pkg1) < _LooseVersion(pkg2):
            return -1
        elif _LooseVersion(pkg1) == _LooseVersion(pkg2):
            return 0
        elif _LooseVersion(pkg1) > _LooseVersion(pkg2):
            return 1
    except Exception as exc:
        log.exception(exc)
    return None


def compare_versions(ver1='',
                     oper='==',
                     ver2='',
                     cmp_func=None,
                     ignore_epoch=False):
    '''
    Compares two version numbers. Accepts a custom function to perform the
    cmp-style version comparison, otherwise uses version_cmp().
    '''
    cmp_map = {'<': (-1,), '<=': (-1, 0), '==': (0,),
               '>=': (0, 1), '>': (1,)}
    if oper not in ('!=',) and oper not in cmp_map:
        log.error('Invalid operator \'%s\' for version comparison', oper)
        return False

    if cmp_func is None:
        cmp_func = version_cmp

    cmp_result = cmp_func(ver1, ver2, ignore_epoch=ignore_epoch)
    if cmp_result is None:
        return False

    # Check if integer/long
    if not isinstance(cmp_result, numbers.Integral):
        log.error('The version comparison function did not return an '
                  'integer/long.')
        return False

    if oper == '!=':
        return cmp_result not in cmp_map['==']
    else:
        # Gracefully handle cmp_result not in (-1, 0, 1).
        if cmp_result < -1:
            cmp_result = -1
        elif cmp_result > 1:
            cmp_result = 1

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


def compare_lists(old=None, new=None):
    '''
    Compare before and after results from various salt functions, returning a
    dict describing the changes that were made
    '''
    ret = dict()
    for item in new:
        if item not in old:
            ret['new'] = item
    for item in old:
        if item not in new:
            ret['old'] = item
    return ret


def argspec_report(functions, module=''):
    '''
    Pass in a functions dict as it is returned from the loader and return the
    argspec function signatures
    '''
    ret = {}
    if '*' in module or '.' in module:
        for fun in fnmatch.filter(functions, module):
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
        # "sys" should just match sys without also matching sysctl
        moduledot = module + '.'

        for fun in functions:
            if fun.startswith(moduledot):
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
        return False
    try:
        with fopen(path, 'rb') as fp_:
            try:
                data = fp_.read(2048)
                if six.PY3:
                    data = data.decode(__salt_system_encoding__)
                return is_bin_str(data)
            except UnicodeDecodeError:
                return True
    except os.error:
        return False


def is_bin_str(data):
    '''
    Detects if the passed string of data is bin or text
    '''
    if '\0' in data:
        return True
    if not data:
        return False

    text_characters = ''.join([chr(x) for x in range(32, 127)] + list('\n\r\t\b'))
    # Get the non-text characters (map each character to itself then use the
    # 'remove' option to get rid of the text characters.)
    if six.PY3:
        trans = ''.maketrans('', '', text_characters)
        nontext = data.translate(trans)
    else:
        trans = string.maketrans('', '')  # pylint: disable=no-member
        nontext = data.translate(trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(nontext) / len(data) > 0.30:
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


def repack_dictlist(data,
                    strict=False,
                    recurse=False,
                    key_cb=None,
                    val_cb=None):
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

    if key_cb is None:
        key_cb = lambda x: x
    if val_cb is None:
        val_cb = lambda x, y: y

    valid_non_dict = (six.string_types, six.integer_types, float)
    if isinstance(data, list):
        for element in data:
            if isinstance(element, valid_non_dict):
                continue
            elif isinstance(element, dict):
                if len(element) != 1:
                    log.error(
                        'Invalid input for repack_dictlist: key/value pairs '
                        'must contain only one element (data passed: %s).',
                        element
                    )
                    return {}
            else:
                log.error(
                    'Invalid input for repack_dictlist: element %s is '
                    'not a string/dict/numeric value', element
                )
                return {}
    else:
        log.error(
            'Invalid input for repack_dictlist, data passed is not a list '
            '(%s)', data
        )
        return {}

    ret = {}
    for element in data:
        if isinstance(element, valid_non_dict):
            ret[key_cb(element)] = None
        else:
            key = next(iter(element))
            val = element[key]
            if is_dictlist(val):
                if recurse:
                    ret[key_cb(key)] = repack_dictlist(val, recurse=recurse)
                elif strict:
                    log.error(
                        'Invalid input for repack_dictlist: nested dictlist '
                        'found, but recurse is set to False'
                    )
                    return {}
                else:
                    ret[key_cb(key)] = val_cb(key, val)
            else:
                ret[key_cb(key)] = val_cb(key, val)
    return ret


def get_default_group(user):
    if HAS_GRP is False or HAS_PWD is False:
        # We don't work on platforms that don't have grp and pwd
        # Just return an empty list
        return None
    return grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name


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
        log.trace('Trying os.getgrouplist for \'{0}\''.format(user))
        try:
            group_names = [
                grp.getgrgid(grpid).gr_name for grpid in
                os.getgrouplist(user, pwd.getpwnam(user).pw_gid)
            ]
        except Exception:
            pass
    else:
        # Try pysss.getgrouplist
        log.trace('Trying pysss.getgrouplist for \'{0}\''.format(user))
        try:
            import pysss  # pylint: disable=import-error
            group_names = list(pysss.getgrouplist(user))
        except Exception:
            pass
    if group_names is None:
        # Fall back to generic code
        # Include the user's default group to behave like
        # os.getgrouplist() and pysss.getgrouplist() do
        log.trace('Trying generic group list for \'{0}\''.format(user))
        group_names = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
        try:
            default_group = get_default_group(user)
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
    log.trace('Group list for user \'{0}\': \'{1}\''.format(user, sorted(ugroups)))
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
    if runas is not None and runas != getpass.getuser():
        chugid(runas)
    if umask is not None:
        os.umask(umask)  # pylint: disable=blacklisted-function


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


def to_str(s, encoding=None):
    '''
    Given str, bytes, bytearray, or unicode (py2), return str
    '''
    if isinstance(s, str):
        return s
    if six.PY3:
        if isinstance(s, (bytes, bytearray)):
            # https://docs.python.org/3/howto/unicode.html#the-unicode-type
            # replace error with U+FFFD, REPLACEMENT CHARACTER
            return s.decode(encoding or __salt_system_encoding__, "replace")
        raise TypeError('expected str, bytes, or bytearray not {}'.format(type(s)))
    else:
        if isinstance(s, bytearray):
            return str(s)
        if isinstance(s, unicode):  # pylint: disable=incompatible-py3-code,undefined-variable
            return s.encode(encoding or __salt_system_encoding__)
        raise TypeError('expected str, bytearray, or unicode')


def to_bytes(s, encoding=None):
    '''
    Given bytes, bytearray, str, or unicode (python 2), return bytes (str for
    python 2)
    '''
    if six.PY3:
        if isinstance(s, bytes):
            return s
        if isinstance(s, bytearray):
            return bytes(s)
        if isinstance(s, str):
            return s.encode(encoding or __salt_system_encoding__)
        raise TypeError('expected bytes, bytearray, or str')
    else:
        return to_str(s, encoding)


def to_unicode(s, encoding=None):
    '''
    Given str or unicode, return unicode (str for python 3)
    '''
    if not isinstance(s, (bytes, bytearray, six.string_types)):
        return s
    if six.PY3:
        if isinstance(s, (bytes, bytearray)):
            return to_str(s, encoding)
    else:
        if isinstance(s, str):
            return s.decode(encoding or __salt_system_encoding__)
    return s


def is_list(value):
    '''
    Check if a variable is a list.
    '''
    return isinstance(value, list)


def is_iter(y, ignore=six.string_types):
    '''
    Test if an object is iterable, but not a string type.

    Test if an object is an iterator or is iterable itself. By default this
    does not return True for string objects.

    The `ignore` argument defaults to a list of string types that are not
    considered iterable. This can be used to also exclude things like
    dictionaries or named tuples.

    Based on https://bitbucket.org/petershinners/yter
    '''

    if ignore and isinstance(y, ignore):
        return False
    try:
        iter(y)
        return True
    except TypeError:
        return False


def invalid_kwargs(invalid_kwargs, raise_exc=True):
    '''
    Raise a SaltInvocationError if invalid_kwargs is non-empty
    '''
    if invalid_kwargs:
        if isinstance(invalid_kwargs, dict):
            new_invalid = [
                '{0}={1}'.format(x, y)
                for x, y in six.iteritems(invalid_kwargs)
            ]
            invalid_kwargs = new_invalid
    msg = (
        'The following keyword arguments are not valid: {0}'
        .format(', '.join(invalid_kwargs))
    )
    if raise_exc:
        raise SaltInvocationError(msg)
    else:
        return msg


def shlex_split(s, **kwargs):
    '''
    Only split if variable is a string
    '''
    if isinstance(s, six.string_types):
        return shlex.split(s, **kwargs)
    else:
        return s


def split_input(val):
    '''
    Take an input value and split it into a list, returning the resulting list
    '''
    if isinstance(val, list):
        return val
    try:
        return [x.strip() for x in val.split(',')]
    except AttributeError:
        return [x.strip() for x in str(val).split(',')]


def str_version_to_evr(verstring):
    '''
    Split the package version string into epoch, version and release.
    Return this as tuple.

    The epoch is always not empty. The version and the release can be an empty
    string if such a component could not be found in the version string.

    "2:1.0-1.2" => ('2', '1.0', '1.2)
    "1.0" => ('0', '1.0', '')
    "" => ('0', '', '')
    '''
    if verstring in [None, '']:
        return '0', '', ''

    idx_e = verstring.find(':')
    if idx_e != -1:
        try:
            epoch = str(int(verstring[:idx_e]))
        except ValueError:
            # look, garbage in the epoch field, how fun, kill it
            epoch = '0'  # this is our fallback, deal
    else:
        epoch = '0'
    idx_r = verstring.find('-')
    if idx_r != -1:
        version = verstring[idx_e + 1:idx_r]
        release = verstring[idx_r + 1:]
    else:
        version = verstring[idx_e + 1:]
        release = ''

    return epoch, version, release


def simple_types_filter(data):
    '''
    Convert the data list, dictionary into simple types, i.e., int, float, string,
    bool, etc.
    '''
    if data is None:
        return data

    simpletypes_keys = (six.string_types, six.text_type, six.integer_types, float, bool)
    simpletypes_values = tuple(list(simpletypes_keys) + [list, tuple])

    if isinstance(data, (list, tuple)):
        simplearray = []
        for value in data:
            if value is not None:
                if isinstance(value, (dict, list)):
                    value = simple_types_filter(value)
                elif not isinstance(value, simpletypes_values):
                    value = repr(value)
            simplearray.append(value)
        return simplearray

    if isinstance(data, dict):
        simpledict = {}
        for key, value in six.iteritems(data):
            if key is not None and not isinstance(key, simpletypes_keys):
                key = repr(key)
            if value is not None and isinstance(value, (dict, list, tuple)):
                value = simple_types_filter(value)
            elif value is not None and not isinstance(value, simpletypes_values):
                value = repr(value)
            simpledict[key] = value
        return simpledict

    return data


def substr_in_list(string_to_search_for, list_to_search):
    '''
    Return a boolean value that indicates whether or not a given
    string is present in any of the strings which comprise a list
    '''
    return any(string_to_search_for in s for s in list_to_search)


def filter_by(lookup_dict,
              lookup,
              traverse,
              merge=None,
              default='default',
              base=None):
    '''
    '''
    ret = None
    # Default value would be an empty list if lookup not found
    val = traverse_dict_and_list(traverse, lookup, [])

    # Iterate over the list of values to match against patterns in the
    # lookup_dict keys
    for each in val if isinstance(val, list) else [val]:
        for key in lookup_dict:
            test_key = key if isinstance(key, six.string_types) else str(key)
            test_each = each if isinstance(each, six.string_types) else str(each)
            if fnmatch.fnmatchcase(test_each, test_key):
                ret = lookup_dict[key]
                break
        if ret is not None:
            break

    if ret is None:
        ret = lookup_dict.get(default, None)

    if base and base in lookup_dict:
        base_values = lookup_dict[base]
        if ret is None:
            ret = base_values

        elif isinstance(base_values, collections.Mapping):
            if not isinstance(ret, collections.Mapping):
                raise SaltException(
                    'filter_by default and look-up values must both be '
                    'dictionaries.')
            ret = salt.utils.dictupdate.update(copy.deepcopy(base_values), ret)

    if merge:
        if not isinstance(merge, collections.Mapping):
            raise SaltException(
                'filter_by merge argument must be a dictionary.')

        if ret is None:
            ret = merge
        else:
            salt.utils.dictupdate.update(ret, copy.deepcopy(merge))

    return ret


def fnmatch_multiple(candidates, pattern):
    '''
    Convenience function which runs fnmatch.fnmatch() on each element of passed
    iterable. The first matching candidate is returned, or None if there is no
    matching candidate.
    '''
    # Make sure that candidates is iterable to avoid a TypeError when we try to
    # iterate over its items.
    try:
        candidates_iter = iter(candidates)
    except TypeError:
        return None

    for candidate in candidates_iter:
        try:
            if fnmatch.fnmatch(candidate, pattern):
                return candidate
        except TypeError:
            pass
    return None


def is_quoted(val):
    '''
    Return a single or double quote, if a string is wrapped in extra quotes.
    Otherwise return an empty string.
    '''
    ret = ''
    if (
        isinstance(val, six.string_types) and val[0] == val[-1] and
        val.startswith(('\'', '"'))
    ):
        ret = val[0]
    return ret


def dequote(val):
    '''
    Remove extra quotes around a string.
    '''
    if is_quoted(val):
        return val[1:-1]
    return val


def mkstemp(*args, **kwargs):
    '''
    Helper function which does exactly what `tempfile.mkstemp()` does but
    accepts another argument, `close_fd`, which, by default, is true and closes
    the fd before returning the file path. Something commonly done throughout
    Salt's code.
    '''
    if 'prefix' not in kwargs:
        kwargs['prefix'] = '__salt.tmp.'
    close_fd = kwargs.pop('close_fd', True)
    fd_, fpath = tempfile.mkstemp(*args, **kwargs)
    if close_fd is False:
        return (fd_, fpath)
    os.close(fd_)
    del fd_
    return fpath
