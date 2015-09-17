# -*- coding: utf-8 -*-
'''
A few checks to make sure the environment is sane
'''
from __future__ import absolute_import

# Original Author: Jeff Schroeder <jeffschroeder@computer.org>

# Import python libs
import os
import re
import sys
import stat
import errno
import socket
import logging

# Import third party libs
if sys.platform.startswith('win'):
    import win32file
else:
    import resource

# Import salt libs
from salt.log import is_console_configured
from salt.exceptions import SaltClientError
import salt.defaults.exitcodes
import salt.utils

log = logging.getLogger(__name__)


def zmq_version():
    '''
    ZeroMQ python bindings >= 2.1.9 are required
    '''
    try:
        import zmq
    except Exception:
        # Return True for local mode
        return True
    ver = zmq.__version__
    # The last matched group can be None if the version
    # is something like 3.1 and that will work properly
    match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?', ver)

    # Fallthrough and hope for the best
    if not match:
        msg = "Using untested zmq python bindings version: '{0}'".format(ver)
        if is_console_configured():
            log.warn(msg)
        else:
            sys.stderr.write("WARNING {0}\n".format(msg))
        return True

    major, minor, point = match.groups()

    if major.isdigit():
        major = int(major)
    if minor.isdigit():
        minor = int(minor)

    # point very well could be None
    if point and point.isdigit():
        point = int(point)

    if major == 2 and minor == 1:
        # zmq 2.1dev could be built against a newer libzmq
        if "dev" in ver and not point:
            msg = 'Using dev zmq module, please report unexpected results'
            if is_console_configured():
                log.warn(msg)
            else:
                sys.stderr.write("WARNING: {0}\n".format(msg))
            return True
        elif point and point >= 9:
            return True
    elif major > 2 or (major == 2 and minor > 1):
        return True

    # If all else fails, gracefully croak and warn the user
    log.critical('ZeroMQ python bindings >= 2.1.9 are required')
    if 'salt-master' in sys.argv[0]:
        msg = ('The Salt Master is unstable using a ZeroMQ version '
               'lower than 2.1.11 and requires this fix: http://lists.zeromq.'
               'org/pipermail/zeromq-dev/2011-June/012094.html')
        if is_console_configured():
            log.critical(msg)
        else:
            sys.stderr.write('CRITICAL {0}\n'.format(msg))
    return False


def lookup_family(hostname):
    '''
    Lookup a hostname and determine its address family. The first address returned
    will be AF_INET6 if the system is IPv6-enabled, and AF_INET otherwise.
    '''
    # If lookups fail, fall back to AF_INET sockets (and v4 addresses).
    fallback = socket.AF_INET
    try:
        hostnames = socket.getaddrinfo(
            hostname or None, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        if not hostnames:
            return fallback
        h = hostnames[0]
        return h[0]
    except socket.gaierror:
        return fallback


def verify_socket(interface, pub_port, ret_port):
    '''
    Attempt to bind to the sockets to verify that they are available
    '''

    addr_family = lookup_family(interface)
    pubsock = socket.socket(addr_family, socket.SOCK_STREAM)
    retsock = socket.socket(addr_family, socket.SOCK_STREAM)
    try:
        pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        pubsock.bind((interface, int(pub_port)))
        pubsock.close()
        retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        retsock.bind((interface, int(ret_port)))
        retsock.close()
        result = True
    except Exception as exc:
        if exc.args:
            msg = ('Unable to bind socket, error: {0}'.format(str(exc)))
        else:
            msg = ('Unable to bind socket, this might not be a problem.'
                   ' Is there another salt-master running?')
        if is_console_configured():
            log.warn(msg)
        else:
            sys.stderr.write('WARNING: {0}\n'.format(msg))
        result = False
    finally:
        pubsock.close()
        retsock.close()

    return result


def verify_files(files, user):
    '''
    Verify that the named files exist and are owned by the named user
    '''
    if salt.utils.is_windows():
        return True
    import pwd  # after confirming not running Windows
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]

    except KeyError:
        err = ('Failed to prepare the Salt environment for user '
               '{0}. The user is not available.\n').format(user)
        sys.stderr.write(err)
        sys.exit(salt.defaults.exitcodes.EX_NOUSER)
    for fn_ in files:
        dirname = os.path.dirname(fn_)
        try:
            try:
                os.makedirs(dirname)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise
            if not os.path.isfile(fn_):
                with salt.utils.fopen(fn_, 'w+') as fp_:
                    fp_.write('')
        except OSError as err:
            msg = 'Failed to create path "{0}" - {1}\n'
            sys.stderr.write(msg.format(fn_, err))
            sys.exit(err.errno)

        stats = os.stat(fn_)
        if uid != stats.st_uid:
            try:
                os.chown(fn_, uid, -1)
            except OSError:
                pass
    return True


def verify_env(dirs, user, permissive=False, pki_dir=''):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    if salt.utils.is_windows():
        return True
    import pwd  # after confirming not running Windows
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
        groups = salt.utils.get_gid_list(user, include_default=False)

    except KeyError:
        err = ('Failed to prepare the Salt environment for user '
               '{0}. The user is not available.\n').format(user)
        sys.stderr.write(err)
        sys.exit(salt.defaults.exitcodes.EX_NOUSER)
    for dir_ in dirs:
        if not dir_:
            continue
        if not os.path.isdir(dir_):
            try:
                cumask = os.umask(18)  # 077
                os.makedirs(dir_)
                # If starting the process as root, chown the new dirs
                if os.getuid() == 0:
                    os.chown(dir_, uid, gid)
                os.umask(cumask)
            except OSError as err:
                msg = 'Failed to create directory path "{0}" - {1}\n'
                sys.stderr.write(msg.format(dir_, err))
                sys.exit(err.errno)

        mode = os.stat(dir_)
        # If starting the process as root, chown the new dirs
        if os.getuid() == 0:
            fmode = os.stat(dir_)
            if fmode.st_uid != uid or fmode.st_gid != gid:
                if permissive and fmode.st_gid in groups:
                    # Allow the directory to be owned by any group root
                    # belongs to if we say it's ok to be permissive
                    pass
                else:
                    # chown the file for the new user
                    os.chown(dir_, uid, gid)
            for subdir in [a for a in os.listdir(dir_) if 'jobs' not in a]:
                fsubdir = os.path.join(dir_, subdir)
                if '{0}jobs'.format(os.path.sep) in fsubdir:
                    continue
                for root, dirs, files in os.walk(fsubdir):
                    for name in files:
                        if name.startswith('.'):
                            continue
                        path = os.path.join(root, name)
                        try:
                            fmode = os.stat(path)
                        except (IOError, OSError):
                            pass
                        if fmode.st_uid != uid or fmode.st_gid != gid:
                            if permissive and fmode.st_gid in groups:
                                pass
                            else:
                                # chown the file for the new user
                                os.chown(path, uid, gid)
                    for name in dirs:
                        path = os.path.join(root, name)
                        fmode = os.stat(path)
                        if fmode.st_uid != uid or fmode.st_gid != gid:
                            if permissive and fmode.st_gid in groups:
                                pass
                            else:
                                # chown the file for the new user
                                os.chown(path, uid, gid)
        # Allow the pki dir to be 700 or 750, but nothing else.
        # This prevents other users from writing out keys, while
        # allowing the use-case of 3rd-party software (like django)
        # to read in what it needs to integrate.
        #
        # If the permissions aren't correct, default to the more secure 700.
        # If acls are enabled, the pki_dir needs to remain readable, this
        # is still secure because the private keys are still only readbale
        # by the user running the master
        if dir_ == pki_dir:
            smode = stat.S_IMODE(mode.st_mode)
            if smode != 448 and smode != 488:
                if os.access(dir_, os.W_OK):
                    os.chmod(dir_, 448)
                else:
                    msg = 'Unable to securely set the permissions of "{0}".'
                    msg = msg.format(dir_)
                    if is_console_configured():
                        log.critical(msg)
                    else:
                        sys.stderr.write("CRITICAL: {0}\n".format(msg))
    # Run the extra verification checks
    zmq_version()


def check_user(user):
    '''
    Check user and assign process uid/gid.
    '''
    if salt.utils.is_windows():
        return True
    if user == salt.utils.get_user():
        return True
    import pwd  # after confirming not running Windows
    try:
        pwuser = pwd.getpwnam(user)
        try:
            if hasattr(os, 'initgroups'):
                os.initgroups(user, pwuser.pw_gid)  # pylint: disable=minimum-python-version
            else:
                os.setgroups(salt.utils.get_gid_list(user, include_default=False))
            os.setgid(pwuser.pw_gid)
            os.setuid(pwuser.pw_uid)

            # We could just reset the whole environment but let's just override
            # the variables we can get from pwuser
            if 'HOME' in os.environ:
                os.environ['HOME'] = pwuser.pw_dir

            if 'SHELL' in os.environ:
                os.environ['SHELL'] = pwuser.pw_shell

            for envvar in ('USER', 'LOGNAME'):
                if envvar in os.environ:
                    os.environ[envvar] = pwuser.pw_name

        except OSError:
            msg = 'Salt configured to run as user "{0}" but unable to switch.'
            msg = msg.format(user)
            if is_console_configured():
                log.critical(msg)
            else:
                sys.stderr.write("CRITICAL: {0}\n".format(msg))
            return False
    except KeyError:
        msg = 'User not found: "{0}"'.format(user)
        if is_console_configured():
            log.critical(msg)
        else:
            sys.stderr.write("CRITICAL: {0}\n".format(msg))
        return False
    return True


def list_path_traversal(path):
    '''
    Returns a full list of directories leading up to, and including, a path.

    So list_path_traversal('/path/to/salt') would return:
        ['/', '/path', '/path/to', '/path/to/salt']
    in that order.

    This routine has been tested on Windows systems as well.
    list_path_traversal('c:\\path\\to\\salt') on Windows would return:
        ['c:\\', 'c:\\path', 'c:\\path\\to', 'c:\\path\\to\\salt']
    '''
    out = [path]
    (head, tail) = os.path.split(path)
    if tail == '':
        # paths with trailing separators will return an empty string
        out = [head]
        (head, tail) = os.path.split(head)
    while head != out[0]:
        # loop until head is the same two consecutive times
        out.insert(0, head)
        (head, tail) = os.path.split(head)
    return out


def check_path_traversal(path, user='root', skip_perm_errors=False):
    '''
    Walk from the root up to a directory and verify that the current
    user has access to read each directory. This is used for  making
    sure a user can read all parent directories of the minion's  key
    before trying to go and generate a new key and raising an IOError
    '''
    for tpath in list_path_traversal(path):
        if not os.access(tpath, os.R_OK):
            msg = 'Could not access {0}.'.format(tpath)
            if not os.path.exists(tpath):
                msg += ' Path does not exist.'
            else:
                current_user = salt.utils.get_user()
                # Make the error message more intelligent based on how
                # the user invokes salt-call or whatever other script.
                if user != current_user:
                    msg += ' Try running as user {0}.'.format(user)
                else:
                    msg += ' Please give {0} read permissions.'.format(user)

            # We don't need to bail on config file permission errors
            # if the CLI
            # process is run with the -a flag
            if skip_perm_errors:
                return
            # Propagate this exception up so there isn't a sys.exit()
            # in the middle of code that could be imported elsewhere.
            raise SaltClientError(msg)


def check_max_open_files(opts):
    '''
    Check the number of max allowed open files and adjust if needed
    '''
    mof_c = opts.get('max_open_files', 100000)
    if sys.platform.startswith('win'):
        # Check the Windows API for more detail on this
        # http://msdn.microsoft.com/en-us/library/xt874334(v=vs.71).aspx
        # and the python binding http://timgolden.me.uk/pywin32-docs/win32file.html
        mof_s = mof_h = win32file._getmaxstdio()
    else:
        mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)

    accepted_keys_dir = os.path.join(opts.get('pki_dir'), 'minions')
    accepted_count = len(os.listdir(accepted_keys_dir))

    log.debug(
        'This salt-master instance has accepted {0} minion keys.'.format(
            accepted_count
        )
    )

    level = logging.INFO

    if (accepted_count * 4) <= mof_s:
        # We check for the soft value of max open files here because that's the
        # value the user chose to raise to.
        #
        # The number of accepted keys multiplied by four(4) is lower than the
        # soft value, everything should be OK
        return

    msg = (
        'The number of accepted minion keys({0}) should be lower than 1/4 '
        'of the max open files soft setting({1}). '.format(
            accepted_count, mof_s
        )
    )

    if accepted_count >= mof_s:
        # This should never occur, it might have already crashed
        msg += 'salt-master will crash pretty soon! '
        level = logging.CRITICAL
    elif (accepted_count * 2) >= mof_s:
        # This is way too low, CRITICAL
        level = logging.CRITICAL
    elif (accepted_count * 3) >= mof_s:
        level = logging.WARNING
        # The accepted count is more than 3 time, WARN
    elif (accepted_count * 4) >= mof_s:
        level = logging.INFO

    if mof_c < mof_h:
        msg += ('According to the system\'s hard limit, there\'s still a '
                'margin of {0} to raise the salt\'s max_open_files '
                'setting. ').format(mof_h - mof_c)

    msg += 'Please consider raising this value.'
    log.log(level=level, msg=msg)


def clean_path(root, path, subdir=False):
    '''
    Accepts the root the path needs to be under and verifies that the path is
    under said root. Pass in subdir=True if the path can result in a
    subdirectory of the root instead of having to reside directly in the root
    '''
    if not os.path.isabs(root):
        return ''
    if not os.path.isabs(path):
        path = os.path.join(root, path)
    path = os.path.normpath(path)
    if subdir:
        if path.startswith(root):
            return path
    else:
        if os.path.dirname(path) == os.path.normpath(root):
            return path
    return ''


def valid_id(opts, id_):
    '''
    Returns if the passed id is valid
    '''
    try:
        return bool(clean_path(opts['pki_dir'], id_))
    except (AttributeError, KeyError) as e:
        return False


def safe_py_code(code):
    '''
    Check a string to see if it has any potentially unsafe routines which
    could be executed via python, this routine is used to improve the
    safety of modules suct as virtualenv
    '''
    bads = (
            'import',
            ';',
            'subprocess',
            'eval',
            'open',
            'file',
            'exec',
            'input')
    for bad in bads:
        if code.count(bad):
            return False
    return True


def verify_log(opts):
    '''
    If an insecre logging configuration is found, show a warning
    '''
    if opts.get('log_level') in ('garbage', 'trace', 'debug'):
        log.warn('Insecure logging configuration detected! Sensitive data may be logged.')
