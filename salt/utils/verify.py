'''
A few checks to make sure the environment is sane
'''
# Original Author: Jeff Schroeder <jeffschroeder@computer.org>
import os
import re
import sys
import stat
import getpass
import logging

log = logging.getLogger(__name__)

__all__ = ('zmq_version', 'run')


def zmq_version():
    '''ZeroMQ python bindings >= 2.1.9 are required'''
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

    major,minor,point = match.groups()
    if major == 2 and minor == 1:
        # zmq 2.1dev could be built against a newer libzmq
        if "dev" in ver and not point:
            log.warn('Using dev zmq module, please report unexpected results')
        elif point and point >= 9:
            return True
    elif major > 2 or (major == 2 and minor > 1):
        return True

    # If all else fails, gracefully croak and warn the user
    log.critical("ZeroMQ python bindings >= 2.1.9 are required")
    return False


def verify_env(dirs):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            try:
                cumask = os.umask(63)  # 077
                os.makedirs(dir_)
                os.umask(cumask)
            except OSError, e:
                sys.stderr.write('Failed to create directory path "{0}" - {1}\n'.format(dir_, e))

        mode = os.stat(dir_)
        # TODO: Should this log if it can't set the permissions
        #       to very secure for these PKI cert directories?
        if not stat.S_IMODE(mode.st_mode) == 448:
            if os.access(dir_, os.W_OK):
                os.chmod(dir_, 448)
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
            if user == 'root':
                msg = 'Sorry, the salt must run as root.  http://xkcd.com/838'
            else:
                msg = 'Salt must be run from root or user "{0}"'.format(user)
            log.critical(msg)
            return False
    except KeyError:
        msg = 'User not found: "{0}"'.format(user)
        log.critical(msg)
        return False
    return True
