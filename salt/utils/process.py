# Import python libs
import logging
import os
import signal
import time
import sys

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def set_pidfile(pidfile, user):
    '''
    Save the pidfile
    '''
    pdir = os.path.dirname(pidfile)
    if not os.path.isdir(pdir) and pdir:
        os.makedirs(pdir)
    try:
        with salt.utils.fopen(pidfile, 'w+') as ofile:
            ofile.write(str(os.getpid()))
    except IOError:
        pass

    log.debug(('Created pidfile: {0}').format(pidfile))
    if salt.utils.is_windows():
        return True

    import pwd  # after confirming not running Windows
    #import grp
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
        #groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
    except IndexError:
        sys.stderr.write(
            'Failed to set the pid to user: {0}. The user is not '
            'available.\n'.format(
                user
            )
        )
        sys.exit(2)
    try:
        os.chown(pidfile, uid, gid)
    except OSError as err:
        msg = ('Failed to set the ownership of PID file {0} '
               'to user {1}\n').format(pidfile, user)
        log.debug(msg, exc_info=True)
        sys.stderr.write(msg)
        sys.exit(err.errno)
    log.debug('Chowned pidfile: {0} to user: {1}'.format(pidfile, user))


def clean_proc(proc, wait_for_kill=10):
    '''
    Generic method for cleaning up multiprocessing procs
    '''
    # NoneType and other fun stuff need not apply
    if not proc:
        return
    try:
        waited = 0
        while proc.is_alive():
            proc.terminate()
            waited += 1
            time.sleep(0.1)
            if proc.is_alive() and (waited >= wait_for_kill):
                log.error(
                    'Process did not die with terminate(): {0}'.format(
                        proc.pid
                    )
                )
                os.kill(signal.SIGKILL, proc.pid)
    except (AssertionError, AttributeError):
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass
