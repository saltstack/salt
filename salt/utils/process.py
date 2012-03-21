import logging
import os
import signal
import time

log = logging.getLogger(__name__)


def set_pidfile(pidfile):
    '''
    Save the pidfile
    '''
    pdir = os.path.dirname(pidfile)
    if not os.path.isdir(pdir):
        os.makedirs(pdir)
    try:
        with open(pidfile, 'w+') as f:
            f.write(str(os.getpid()))
    except IOError:
        pass


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
                log.error(('Process did not die with terminate(): {0}'
                    .format(proc.pid)))
                os.kill(signal.SIGKILL, proc.pid)
    except (AssertionError, AttributeError) as e:
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass
