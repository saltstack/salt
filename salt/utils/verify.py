'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>
import os
import re
import pwd
import sys
import stat
import getpass
import logging

log = logging.getLogger(__name__)

__all__ = ('zmq_version', 'run')


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


def verify_env(dirs, user):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
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
                sys.stderr.write('Failed to create directory path "{0}" - {1}\n'.format(dir_, e))

        mode = os.stat(dir_)
        # If starting the process as root, chown the new dirs
        if os.getuid() == 0:
            fmode = os.stat(dir_)
            if not fmode.st_uid == uid or not fmode.st_gid == gid:
                # chown the file for the new user
                os.chown(dir_, uid, gid)
            for root, dirs, files in os.walk(dir_):
                for name in files:
                    path = os.path.join(root, name)
                    fmode = os.stat(path)
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
                msg = 'Unable to securely set the permissions of "{0}".'.format(dir_)
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
