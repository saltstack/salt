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
import errno
import socket
import logging

# Import third party libs
try:
    import win32file
except ImportError:
    import resource

# Import salt libs
from salt.log import is_console_configured
from salt.log.setup import LOG_LEVELS
from salt.exceptions import SaltClientError, SaltSystemExit, CommandExecutionError
import salt.defaults.exitcodes

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
            log.warning(msg)
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
                log.warning(msg)
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
    for port in pub_port, ret_port:
        sock = socket.socket(addr_family, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((interface, int(port)))
        except Exception as exc:
            msg = 'Unable to bind socket {0}:{1}'.format(interface, port)
            if exc.args:
                msg = '{0}, error: {1}'.format(msg, str(exc))
            else:
                msg = '{0}, this might not be a problem.'.format(msg)
            msg += '; Is there another salt-master running?'
            if is_console_configured():
                log.warning(msg)
            else:
                sys.stderr.write('WARNING: {0}\n'.format(msg))
            return False
        finally:
            sock.close()

    return True


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
            if dirname:
                try:
                    os.makedirs(dirname)
                except OSError as err:
                    if err.errno != errno.EEXIST:
                        raise
            if not os.path.isfile(fn_):
                with salt.utils.fopen(fn_, 'w+') as fp_:
                    fp_.write('')

        except IOError as err:
            if os.path.isfile(dirname):
                msg = 'Failed to create path {0}, is {1} a file?'.format(fn_, dirname)
                raise SaltSystemExit(msg=msg)
            if err.errno != errno.EACCES:
                raise
            msg = 'No permissions to access "{0}", are you running as the correct user?'.format(fn_)
            raise SaltSystemExit(msg=msg)

        except OSError as err:
            msg = 'Failed to create path "{0}" - {1}'.format(fn_, err)
            raise SaltSystemExit(msg=msg)

        stats = os.stat(fn_)
        if uid != stats.st_uid:
            try:
                os.chown(fn_, uid, -1)
            except OSError:
                pass
    return True


def verify_env(dirs, user, default_mode=0o750,
               allow_nonprimary_gid=False, pki_dir='', skip_extra=False):
    '''
    Creates the directory trees specified if they do not exist, verifies the
    existing permissions, and attempts to correct them based on the options
    specified.

    * By default enforces that the group of each directory matches the primary \
         group of the user specified.
    * Currently "extra" checks consist of the version of ZMQ.
    * The behavior on Windows differs due to differences in the file permissions model.

    :param dirs: A list of pairs `V(directory, mode)` where the mode represents \
    the permissions that should be applied to the respective directory and its subtree.
    :type dirs: list[(str, int or None)]
    :param str user: The username of the appropriate path owner. \
        Typically this is the user specified in the salt config.
    :param int default_mode: The file mode that should be used for any paths that do not specify one.
    :param bool allow_nonprimary_gid: Allow ownership by any group the user is a member of.
    :param str pki_dir: The pki directory (this is required to apply restrictive permissions on Windows).
    :param bool skip_extra: Skips "extra" checks if true.

    :returns: None
    :rtype: None
    '''
    if salt.utils.is_windows():
        dirs_without_modes = [i[0] for i in dirs]
        return win_verify_env(
            dirs=dirs_without_modes,
            permissive=allow_nonprimary_gid,
            pki_dir=pki_dir,
            skip_extra=skip_extra
        )

    import pwd  # after confirming not running Windows
    try:
        pwnam = pwd.getpwnam(user)
        salt_user_uid = pwnam[2]
        salt_user_primary_gid = pwnam[3]
        salt_user_gids = salt.utils.get_gid_list(user, include_default=False)
    except KeyError:
        err = ('Failed to prepare the Salt environment for user '
               '{0}. The user is not available.\n').format(user)
        sys.stderr.write(err)
        sys.exit(salt.defaults.exitcodes.EX_NOUSER)

    if os.getuid() not in [0, salt_user_uid]:
        log.warning('Current user {uid} is neither root nor user "{salt_user}" specified in the config. '
                    'This may lead to unintended file permissions issues.'.format(uid=os.getuid(), salt_user=user))

    def _check_and_set_permissions(
            path, mode, salt_user_uid,
            salt_user_primary_gid, salt_user_gids, allow_nonprimary_gid):
        '''
        Checks and attempts to "correct" the permissions and ownership on the specified path.

        :param str path: Path to check and set permissions on.
        :param int mode: The mode the path should have.
        :param str salt_user_uid: The user id of the user that will be executing Salt.
        :param int salt_user_primary_gid: The primary GID of the salt user.
        :param list(int) salt_user_gids: A list of the group GIDs that the salt user belongs to.
        :param bool allow_nonprimary_gid: Allows the group on the path to match any user the group is a member of.
        :returns: None
        :rtype: None
        '''

        os.chmod(path, mode)
        log.debug('Setting mode {mode} on {path}.'.format(mode=oct(mode), path=path))

        path_status = os.stat(path)
        if path_status.st_uid != salt_user_uid:
            log.debug(
                'Changing owner of {path} from UID {old_uid} to UID {new_uid}'.format(
                    path=path, old_uid=path_status.st_uid, new_uid=salt_user_uid)
            )
            try:
                os.chown(path, salt_user_uid, -1)
            except OSError as err:
                log.exception('Unable to chown {path}'.format(path=path))
                if err.errno != errno.EPERM:
                    raise

        if allow_nonprimary_gid and path_status.st_gid != salt_user_primary_gid:
            if path_status.st_gid not in salt_user_gids:
                log.debug(
                    'UID {uid} not in group with GID {old_gid}. Changing'
                    'group of {path} from GID {old_gid} to GID {new_gid}'.format(
                        uid=salt_user_uid, old_gid=path_status.st_gid,
                        path=path, new_gid=salt_user_primary_gid)
                )
                try:
                    os.chown(path, -1, salt_user_primary_gid)
                except OSError as err:
                    log.exception('Unable to chown {path}'.format(path=path))
                    if err.errno != errno.EPERM:
                        raise
        else:
            try:
                os.chown(path, -1, salt_user_primary_gid)
            except OSError as err:
                log.exception('Unable to chown {path}'.format(path=path))
                if err.errno != errno.EPERM:
                    raise

    for directory, dir_mode in dirs:
        if not dir_mode:
            dir_mode = default_mode
        if not directory:
            continue

        if not os.path.isdir(directory):
            # create directory
            log.debug('Creating directory {path}'.format(path=directory))
            try:
                os.makedirs(directory, dir_mode)
            except (IOError, OSError):
                log.exception('Unable to create directory {path}'.format(path=directory))

        try:
            _check_and_set_permissions(
                directory,
                dir_mode,
                salt_user_uid,
                salt_user_primary_gid,
                salt_user_gids,
                allow_nonprimary_gid
            )
        except (IOError, OSError):
            log.exception('Unable to set permissions for path: {path}'.format(path=directory))

        for dirpath, dirnames, filenames in os.walk(directory):
            for dirname in dirnames:
                path = os.path.join(dirpath, dirname)
                try:
                    _check_and_set_permissions(
                        path,
                        dir_mode,
                        salt_user_uid,
                        salt_user_primary_gid,
                        salt_user_gids,
                        allow_nonprimary_gid
                    )
                except (IOError, OSError):
                    log.exception('Unable to set permissions for path {path}'.format(path=path))

            for filename in filenames:
                path = os.path.join(dirpath, filename)
                try:
                    _check_and_set_permissions(
                        path,
                        dir_mode,
                        salt_user_uid,
                        salt_user_primary_gid,
                        salt_user_gids,
                        allow_nonprimary_gid
                    )
                except (IOError, OSError):
                    log.exception('Unable to set permissions for path {path}'.format(path=path))


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
    except (AttributeError, KeyError, TypeError):
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
    level = LOG_LEVELS.get(str(opts.get('log_level')).lower(), logging.NOTSET)

    if level < logging.INFO:
        log.warning('Insecure logging configuration detected! Sensitive data may be logged.')


def win_verify_env(dirs, permissive=False, pki_dir='', skip_extra=False):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    import salt.utils.win_functions
    import salt.utils.win_dacl

    # Get the root path directory where salt is installed
    path = dirs[0]
    while os.path.basename(path) not in ['salt', 'salt-tests-tmpdir']:
        path, base = os.path.split(path)

    # Create the root path directory if missing
    if not os.path.isdir(path):
        os.makedirs(path)

    # Set permissions to the root path directory
    current_user = salt.utils.win_functions.get_current_user()
    if salt.utils.win_functions.is_admin(current_user):
        try:
            # Make the Administrators group owner
            # Use the SID to be locale agnostic
            salt.utils.win_dacl.set_owner(path, 'S-1-5-32-544')

        except CommandExecutionError:
            msg = 'Unable to securely set the owner of "{0}".'.format(path)
            if is_console_configured():
                log.critical(msg)
            else:
                sys.stderr.write("CRITICAL: {0}\n".format(msg))

        if not permissive:
            try:
                # Get a clean dacl by not passing an obj_name
                dacl = salt.utils.win_dacl.dacl()

                # Add aces to the dacl, use the GUID (locale non-specific)
                # Administrators Group
                dacl.add_ace('S-1-5-32-544', 'grant', 'full_control',
                             'this_folder_subfolders_files')
                # System
                dacl.add_ace('S-1-5-18', 'grant', 'full_control',
                             'this_folder_subfolders_files')
                # Owner
                dacl.add_ace('S-1-3-4', 'grant', 'full_control',
                             'this_folder_subfolders_files')

                # Save the dacl to the object
                dacl.save(path, True)

            except CommandExecutionError:
                msg = 'Unable to securely set the permissions of ' \
                      '"{0}".'.format(path)
                if is_console_configured():
                    log.critical(msg)
                else:
                    sys.stderr.write("CRITICAL: {0}\n".format(msg))

    # Create the directories
    for dir_ in dirs:
        if not dir_:
            continue
        if not os.path.isdir(dir_):
            try:
                os.makedirs(dir_)
            except OSError as err:
                msg = 'Failed to create directory path "{0}" - {1}\n'
                sys.stderr.write(msg.format(dir_, err))
                sys.exit(err.errno)

        # The PKI dir gets its own permissions
        if dir_ == pki_dir:
            try:
                # Make Administrators group the owner
                salt.utils.win_dacl.set_owner(path, 'S-1-5-32-544')

                # Give Admins, System and Owner permissions
                # Get a clean dacl by not passing an obj_name
                dacl = salt.utils.win_dacl.dacl()

                # Add aces to the dacl, use the GUID (locale non-specific)
                # Administrators Group
                dacl.add_ace('S-1-5-32-544', 'grant', 'full_control',
                             'this_folder_subfolders_files')
                # System
                dacl.add_ace('S-1-5-18', 'grant', 'full_control',
                             'this_folder_subfolders_files')
                # Owner
                dacl.add_ace('S-1-3-4', 'grant', 'full_control',
                             'this_folder_subfolders_files')

                # Save the dacl to the object
                dacl.save(dir_, True)

            except CommandExecutionError:
                msg = 'Unable to securely set the permissions of "{0}".'
                msg = msg.format(dir_)
                if is_console_configured():
                    log.critical(msg)
                else:
                    sys.stderr.write("CRITICAL: {0}\n".format(msg))

    if skip_extra is False:
        # Run the extra verification checks
        zmq_version()
