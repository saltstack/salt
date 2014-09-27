# -*- coding: utf-8 -*-
# Import python libs
import logging
import os
import signal
import time
import sys
import multiprocessing
import signal

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

try:
    import systemd.daemon
    HAS_PYTHON_SYSTEMD = True
except ImportError:
    HAS_PYTHON_SYSTEMD = False


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
        sys.exit(os.EX_NOUSER)

    if os.getuid() == uid:
        # The current user already owns the pidfile. Return!
        return

    try:
        os.chown(pidfile, uid, gid)
    except OSError as err:
        msg = (
            'Failed to set the ownership of PID file {0} to user {1}.'.format(
                pidfile, user
            )
        )
        log.debug('{0} Traceback follows:\n'.format(msg), exc_info=True)
        sys.stderr.write('{0}\n'.format(msg))
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
                os.kill(proc.pid, signal.SIGKILL)
    except (AssertionError, AttributeError):
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass


def os_is_running(pid):
    '''
    Use OS facilities to determine if a process is running
    '''
    if HAS_PSUTIL:
        return psutil.pid_exists(pid)
    else:
        try:
            os.kill(pid, 0)  # SIG 0 is the "are you alive?" signal
            return True
        except OSError:
            return False


class ProcessManager(object):
    '''
    A class which will manage processes that should be running
    '''
    def __init__(self, name=None, wait_for_kill=1):
        # pid -> {tgt: foo, Process: object, args: args, kwargs: kwargs}
        self._process_map = {}

        self.name = name
        if self.name is None:
            self.name = self.__class__.__name__

        self.wait_for_kill = wait_for_kill

    def add_process(self, tgt, args=None, kwargs=None):
        '''
        Create a processes and args + kwargs
        This will deterimine if it is a Process class, otherwise it assumes
        it is a function
        '''
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        if type(multiprocessing.Process) == type(tgt) and issubclass(tgt, multiprocessing.Process):
            p = tgt(*args, **kwargs)
        else:
            p = multiprocessing.Process(target=tgt, args=args, kwargs=kwargs)

        p.start()
        log.debug("Started '{0}'(*{1}, **{2} with pid {3}".format(tgt,
                                                                  args,
                                                                  kwargs,
                                                                  p.pid))
        self._process_map[p.pid] = {'tgt': tgt,
                                    'args': args,
                                    'kwargs': kwargs,
                                    'Process': p}

    def restart_process(self, pid):
        '''
        Create new process (assuming this one is dead), then remove the old one
        '''
        log.info(('Process {0} ({1}) died with exit status {2},'
                  ' restarting...').format(self._process_map[pid]['tgt'],
                                           pid,
                                           self._process_map[pid]['Process'].exitcode))
        self._process_map[pid]['Process'].join(1)

        self.add_process(self._process_map[pid]['tgt'],
                         self._process_map[pid]['args'],
                         self._process_map[pid]['kwargs'])

        del self._process_map[pid]

    def run(self):
        '''
        Load and start all available api modules
        '''
        salt.utils.appendproctitle(self.name)
        # make sure to kill the subprocesses if the parent is killed
        signal.signal(signal.SIGTERM, self.kill_children)

        try:
            if HAS_PYTHON_SYSTEMD and systemd.daemon.booted():
                systemd.daemon.notify('READY=1')
        except SystemError:
            # Daemon wasn't started by systemd
            pass

        while True:
            try:
                pid, exit_status = os.wait()
                if pid not in self._process_map:
                    log.debug(('Process of pid {0} died, not a known'
                               ' process, will not restart').format(pid))
                    continue
                self.restart_process(pid)
            except OSError:
                break

            # in case someone died while we were waiting...
            self.check_children()

    def check_children(self):
        '''
        Check the children once
        '''
        for pid, mapping in self._process_map.iteritems():
            if not mapping['Process'].is_alive():
                self.restart_process(pid)

    def kill_children(self, *args):
        '''
        Kill all of the children
        '''
        for pid, p_map in self._process_map.items():
            p_map['Process'].terminate()

        #
        end_time = time.time() + self.wait_for_kill  # when to die

        while self._process_map and time.time() < end_time:
            for pid, p_map in self._process_map.items():
                p_map['Process'].join(0)

                # This is a race condition if a signal was passed to all children
                try:
                    del self._process_map[pid]
                except KeyError:
                    pass
        # if anyone is done after
        for pid in self._process_map:
            try:
                os.kill(signal.SIGKILL, pid)
            # in case the process has since decided to die, os.kill returns OSError
            except OSError:
                pass
