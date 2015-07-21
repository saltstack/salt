# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import python libs
import logging
import os
import time
import types
import sys
import multiprocessing
import signal

import threading

# Import salt libs
import salt.defaults.exitcodes
import salt.utils
import salt.ext.six as six
from salt.ext.six.moves import queue, range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass


def notify_systemd():
    '''
    Notify systemd that this process has started
    '''
    try:
        import systemd.daemon
    except ImportError:
        return False
    if systemd.daemon.booted():
        try:
            return systemd.daemon.notify('READY=1')
        except SystemError:
            # Daemon was not started by systemd
            pass


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
        sys.exit(salt.defaults.exitcodes.EX_NOUSER)

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


class ThreadPool(object):
    '''
    This is a very VERY basic threadpool implementation
    This was made instead of using multiprocessing ThreadPool because
    we want to set max queue size and we want to daemonize threads (neither
    is exposed in the stdlib version).

    Since there isn't much use for this class as of right now this implementation
    Only supports daemonized threads and will *not* return results

    TODO: if this is found to be more generally useful it would be nice to pull
    in the majority of code from upstream or from http://bit.ly/1wTeJtM
    '''
    def __init__(self,
                 num_threads=None,
                 queue_size=0):
        # if no count passed, default to number of CPUs
        if num_threads is None:
            num_threads = multiprocessing.cpu_count()
        self.num_threads = num_threads

        # create a task queue of queue_size
        self._job_queue = queue.Queue(queue_size)

        self._workers = []

        # create worker threads
        for _ in range(num_threads):
            thread = threading.Thread(target=self._thread_target)
            thread.daemon = True
            thread.start()
            self._workers.append(thread)

    # intentionally not called "apply_async"  since we aren't keeping track of
    # the return at all, if we want to make this API compatible with multiprocessing
    # threadpool we can in the future, and we won't have to worry about name collision
    def fire_async(self, func, args=None, kwargs=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        try:
            self._job_queue.put_nowait((func, args, kwargs))
            return True
        except queue.Full:
            return False

    def _thread_target(self):
        while True:
            # 1s timeout so that if the parent dies this thread will die within 1s
            try:
                func, args, kwargs = self._job_queue.get(timeout=1)
                self._job_queue.task_done()  # Mark the task as done once we get it
            except queue.Empty:
                continue
            try:
                log.debug('ThreadPool executing func: {0} with args:{1}'
                          ' kwargs{2}'.format(func, args, kwargs))
                func(*args, **kwargs)
            except Exception as err:
                log.debug(err, exc_info=True)


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

        # store some pointers for the SIGTERM handler
        self._pid = os.getpid()
        self._sigterm_handler = signal.getsignal(signal.SIGTERM)

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

        if type(multiprocessing.Process) is type(tgt) and issubclass(tgt, multiprocessing.Process):
            process = tgt(*args, **kwargs)
        else:
            process = multiprocessing.Process(target=tgt, args=args, kwargs=kwargs)

        process.start()

        # create a nicer name for the debug log
        if isinstance(tgt, types.FunctionType):
            name = '{0}.{1}'.format(
                tgt.__module__,
                tgt.__name__,
            )
        else:
            name = '{0}.{1}.{2}'.format(
                tgt.__module__,
                tgt.__class__,
                tgt.__name__,
            )
        log.debug("Started '{0}' with pid {1}".format(name, process.pid))
        self._process_map[process.pid] = {'tgt': tgt,
                                          'args': args,
                                          'kwargs': kwargs,
                                          'Process': process}

    def restart_process(self, pid):
        '''
        Create new process (assuming this one is dead), then remove the old one
        '''
        log.info(('Process {0} ({1}) died with exit status {2},'
                  ' restarting...').format(self._process_map[pid]['tgt'],
                                           pid,
                                           self._process_map[pid]['Process'].exitcode))
        # don't block, the process is already dead
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

        while True:
            try:
                # in case someone died while we were waiting...
                self.check_children()

                pid, exit_status = os.wait()
                if pid not in self._process_map:
                    log.debug(('Process of pid {0} died, not a known'
                               ' process, will not restart').format(pid))
                    continue
                self.restart_process(pid)
            # OSError is raised if a signal handler is called (SIGTERM) during os.wait
            except OSError:
                break

    def check_children(self):
        '''
        Check the children once
        '''
        for pid, mapping in six.iteritems(self._process_map):
            if not mapping['Process'].is_alive():
                self.restart_process(pid)

    def kill_children(self, *args):
        '''
        Kill all of the children
        '''
        # check that this is the correct process, children inherit this
        # handler, if we are in a child lets just run the original handler
        if os.getpid() != self._pid:
            if callable(self._sigterm_handler):
                return self._sigterm_handler(*args)
            elif self._sigterm_handler is not None:
                return signal.default_int_handler(signal.SIGTERM)(*args)
            else:
                return

        for p_map in six.itervalues(self._process_map):
            p_map['Process'].terminate()

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
