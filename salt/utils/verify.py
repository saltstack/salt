'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>
import os
import re
import sys
import stat
import socket
import getpass
import logging
if sys.platform.startswith('win'):
    import win32file
else:
    import resource

from salt.log import is_console_configured
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)


def zmq_version():
    '''
    ZeroMQ python bindings >= 2.1.9 are required
    '''
    import zmq
    ver = zmq.__version__
    # The last matched group can be None if the version
    # is something like 3.1 and that will work properly
    match = re.match('^(\d+)\.(\d+)(?:\.(\d+))?', ver)

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
            sys.stderr.write("CRITICAL {0}\n".format(msg))
    return False


def verify_socket(interface, pub_port, ret_port):
    '''
    Attempt to bind to the sockets to verify that they are available
    '''
    result = None

    pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        pubsock.bind((interface, int(pub_port)))
        pubsock.close()
        retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        retsock.bind((interface, int(ret_port)))
        retsock.close()
        result = True
    except Exception:
        msg = ("Unable to bind socket, this might not be a problem."
               " Is there another salt-master running?")
        if is_console_configured():
            log.warn(msg)
        else:
            sys.stderr.write("WARNING: {0}\n".format(msg))
        result = False
    finally:
        pubsock.close()
        retsock.close()

    return result


def verify_env(dirs, user, permissive=False, pki_dir=''):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            return True
    import pwd  # after confirming not running Windows
    import grp
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
        groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]

    except KeyError:
        err = ('Failed to prepare the Salt environment for user '
               '{0}. The user is not available.\n').format(user)
        sys.stderr.write(err)
        sys.exit(2)
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
            except OSError as e:
                msg = 'Failed to create directory path "{0}" - {1}\n'
                sys.stderr.write(msg.format(dir_, e))
                sys.exit(e.errno)

        mode = os.stat(dir_)
        # If starting the process as root, chown the new dirs
        if os.getuid() == 0:
            fmode = os.stat(dir_)
            if not fmode.st_uid == uid or not fmode.st_gid == gid:
                if permissive and fmode.st_gid in groups:
                    # Allow the directory to be owned by any group root
                    # belongs to if we say it's ok to be permissive
                    pass
                else:
                    # chown the file for the new user
                    os.chown(dir_, uid, gid)
            for root, dirs, files in os.walk(dir_):
                if 'jobs' in root:
                    continue
                for name in files:
                    if name.startswith('.'):
                        continue
                    path = os.path.join(root, name)
                    try:
                        fmode = os.stat(path)
                    except (IOError, OSError):
                        pass
                    if not fmode.st_uid == uid or not fmode.st_gid == gid:
                        if permissive and fmode.st_gid in groups:
                            pass
                        else:
                            # chown the file for the new user
                            os.chown(path, uid, gid)
                for name in dirs:
                    path = os.path.join(root, name)
                    fmode = os.stat(path)
                    if not fmode.st_uid == uid or not fmode.st_gid == gid:
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
            if not smode == 448 and not smode == 488:
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
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            return True
    if user == getpass.getuser():
        return True
    import pwd  # after confirming not running Windows
    try:
        p = pwd.getpwnam(user)
        try:
            os.setgid(p.pw_gid)
            os.setuid(p.pw_uid)
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
    """
    Returns a full list of directories leading up to, and including, a path.

    So list_path_traversal('/path/to/salt') would return:
        ['/', '/path', '/path/to', '/path/to/salt']
    in that order.

    This routine has been tested on Windows systems as well.
    list_path_traversal('c:\\path\\to\\salt') on Windows would return:
        ['c:\\', 'c:\\path', 'c:\\path\\to', 'c:\\path\\to\\salt']
    """
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


def check_path_traversal(path, user='root'):
    '''
    Walk from the root up to a directory and verify that the current
    user has access to read each directory. This is used for  making
    sure a user can read all parent directories of the minion's  key
    before trying to go and generate a new key and raising an IOError
    '''
    for p in list_path_traversal(path):
        if not os.access(p, os.R_OK):
            msg = 'Could not access {0}.'.format(p)
            current_user = getpass.getuser()
            # Make the error message more intelligent based on how
            # the user invokes salt-call or whatever other script.
            if user != current_user:
                msg += ' Try running as user {0}.'.format(user)
            else:
                msg += ' Please give {0} read permissions.'.format(user, p)
            # Propagate this exception up so there isn't a sys.exit()
            # in the middle of code that could be imported elsewhere.
            raise SaltClientError(msg)


def check_max_open_files(opts):
    mof_c = opts.get('max_open_files', 100000)
    if sys.platform.startswith('win'):
        # Check the windows api for more detail on this
        # http://msdn.microsoft.com/en-us/library/xt874334(v=vs.71).aspx
        # and the python binding http://timgolden.me.uk/pywin32-docs/win32file.html
        mof_s = mof_h = win32file._getmaxstdio()
    else:
        mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)

    accepted_keys_dir = os.path.join(opts.get('pki_dir'), 'minions')
    accepted_count = len([
        key for key in os.listdir(accepted_keys_dir) if
        os.path.isfile(os.path.join(accepted_keys_dir, key))
    ])

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
