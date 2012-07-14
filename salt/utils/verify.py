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
        msg = 'Using untested zmq python bindings version: \'{0}\''
        log.warn(msg.format(ver))
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
            log.warn('Using dev zmq module, please report unexpected results')
            return True
        elif point and point >= 9:
            return True
    elif major > 2 or (major == 2 and minor > 1):
        return True

    # If all else fails, gracefully croak and warn the user
    log.critical('ZeroMQ python bindings >= 2.1.9 are required')
    if 'salt-master' in sys.argv[0]:
        log.critical('The Salt Master is unstable using a ZeroMQ version '
            'lower than 2.1.11 and requires this fix: http://lists.zeromq.'
            'org/pipermail/zeromq-dev/2011-June/012094.html')
    return False


def verify_socket(interface, pub_port, ret_port):
    '''
    Attempt to bind to the sockets to verify that they are available
    '''
    result = None

    pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        pubsock.bind((interface, int(pub_port)))
        pubsock.close()
        retsock.bind((interface, int(ret_port)))
        retsock.close()
        result = True
    except Exception:
        log.warn("Unable to bind socket, this might not be a problem."
                 " Is there another salt-master running?")
        result = False
    finally:
        pubsock.close()
        retsock.close()

    return True  # TODO: Make this test actually function as advertised
                 # Disabled check as per github issue number 1594

def verify_env(dirs, user):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            return True
    import pwd  # after confirming not running Windows
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
    except KeyError:
        err = ('Failed to prepare the Salt environment for user '
               '{0}. The user is not available.\n').format(user)
        sys.stderr.write(err)
        sys.exit(2)
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            try:
                cumask = os.umask(63)  # 077
                os.makedirs(dir_)
                # If starting the process as root, chown the new dirs
                if os.getuid() == 0:
                    os.chown(dir_, uid, gid)
                os.umask(cumask)
            except OSError as e:
                msg = 'Failed to create directory path "{0}" - {1}\n'
                sys.stderr.write(msg.format(dir_, e))

        mode = os.stat(dir_)
        # If starting the process as root, chown the new dirs
        if os.getuid() == 0:
            fmode = os.stat(dir_)
            if not fmode.st_uid == uid or not fmode.st_gid == gid:
                # chown the file for the new user
                os.chown(dir_, uid, gid)
            for root, dirs, files in os.walk(dir_):
                if 'jobs' in root:
                    continue
                for name in files:
                    path = os.path.join(root, name)
                    try:
                        fmode = os.stat(path)
                    except (IOError, OSError):
                        pass
                    if not fmode.st_uid == uid or not fmode.st_gid == gid:
                        # chown the file for the new user
                        os.chown(path, uid, gid)
                for name in dirs:
                    path = os.path.join(root, name)
                    fmode = os.stat(path)
                    if not fmode.st_uid == uid or not fmode.st_gid == gid:
                        # chown the file for the new user
                        os.chown(path, uid, gid)
        # Allow the pki dir to be 700 or 750, but nothing else.
        # This prevents other users from writing out keys, while
        # allowing the use-case of 3rd-party software (like django)
        # to read in what it needs to integrate.
        #
        # If the permissions aren't correct, default to the more secure 700.
        smode = stat.S_IMODE(mode.st_mode)
        if not smode == 448 and not smode == 488:
            if os.access(dir_, os.W_OK):
                os.chmod(dir_, 448)
            else:
                msg = 'Unable to securely set the permissions of "{0}".'
                msg = msg.format(dir_)
                log.critical(msg)
    # Run the extra verification checks
    zmq_version()


def check_user(user, log):
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
            log.critical(msg.format(user))
            return False
    except KeyError:
        msg = 'User not found: "{0}"'.format(user)
        log.critical(msg)
        return False
    return True

def check_parent_dirs(fname, user='root'):
    '''
    Walk from the root up to a directory and verify that the current
    user has access to read each directory. This is used for  making
    sure a user can read all parent directories of the minion's  key
    before trying to go and generate a new key and raising an IOError
    '''
    # TODO: Test the below line on Windows
    dir_comps = fname.split(os.path.sep)[1:-1]
    # Loop over all parent directories of the minion key
    # to properly test if salt has read access to  them.
    for i,dirname in enumerate(dir_comps):
        # Create the full path to the directory using a list slice
        d = os.path.join(os.path.sep, *dir_comps[:i + 1])
        msg ='Could not access directory {0}.'.format(d)
        current_user = getpass.getuser()
        # Make the error message more intelligent based on how
        # the user invokes salt-call or whatever other script.
        if user != current_user:
            msg += ' Try running as user {0}.'.format(user)
        else:
            msg += ' Please give {0} read permissions.'.format(user, d)
        if not os.access(d, os.R_OK):
            # Propagate this exception up so there isn't a sys.exit()
            # in the middle of code that could be imported elsewhere.
            raise SaltClientError(msg)
