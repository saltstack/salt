# -*- coding: utf-8 -*-
'''
Functions for daemonizing and otherwise modifying running processes
'''

# Import python libs
from __future__ import absolute_import, with_statement, print_function, unicode_literals
import copy
import io
import os
import sys
import time
import errno
import types
import signal
import logging
import functools
import threading
import contextlib
import subprocess
import multiprocessing
import multiprocessing.util
import socket

# Import salt libs
import salt.defaults.exitcodes
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.log.setup
import salt.defaults.exitcodes
import salt.utils.versions
from salt.log.mixins import NewStyleClassMixIn

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import queue, range  # pylint: disable=import-error,redefined-builtin
from tornado import gen

log = logging.getLogger(__name__)

# pylint: disable=import-error
HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

try:
    import setproctitle
    HAS_SETPROCTITLE = True
except ImportError:
    HAS_SETPROCTITLE = False


def appendproctitle(name):
    '''
    Append "name" to the current process title
    '''
    if HAS_SETPROCTITLE:
        setproctitle.setproctitle(setproctitle.getproctitle() + ' ' + name)


def daemonize(redirect_out=True):
    '''
    Daemonize a process
    '''
    # Avoid circular import
    import salt.utils.crypt
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            salt.utils.crypt.reinit_crypto()
            os._exit(salt.defaults.exitcodes.EX_OK)
    except OSError as exc:
        log.error('fork #1 failed: %s (%s)', exc.errno, exc)
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    # decouple from parent environment
    os.chdir('/')
    # noinspection PyArgumentList
    os.setsid()
    os.umask(0o022)  # pylint: disable=blacklisted-function

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            salt.utils.crypt.reinit_crypto()
            sys.exit(salt.defaults.exitcodes.EX_OK)
    except OSError as exc:
        log.error('fork #2 failed: %s (%s)', exc.errno, exc)
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    salt.utils.crypt.reinit_crypto()

    # A normal daemonization redirects the process output to /dev/null.
    # Unfortunately when a python multiprocess is called the output is
    # not cleanly redirected and the parent process dies when the
    # multiprocessing process attempts to access stdout or err.
    if redirect_out:
        with salt.utils.files.fopen('/dev/null', 'r+') as dev_null:
            # Redirect python stdin/out/err
            # and the os stdin/out/err which can be different
            dup2(dev_null, sys.stdin)
            dup2(dev_null, sys.stdout)
            dup2(dev_null, sys.stderr)
            dup2(dev_null, 0)
            dup2(dev_null, 1)
            dup2(dev_null, 2)


def dup2(file1, file2):
    '''
    Duplicate file descriptor fd to fd2, closing the latter first if necessary.
    This method is similar to os.dup2 but ignores streams that do not have a
    supported fileno method.
    '''
    if isinstance(file1, int):
        fno1 = file1
    else:
        try:
            fno1 = file1.fileno()
        except io.UnsupportedOperation:
            log.warn('Unsupported operation on file: %r', file1)
            return
    if isinstance(file2, int):
        fno2 = file2
    else:
        try:
            fno2 = file2.fileno()
        except io.UnsupportedOperation:
            log.warn('Unsupported operation on file: %r', file2)
            return
    os.dup2(fno1, fno2)


def daemonize_if(opts):
    '''
    Daemonize a module function process if multiprocessing is True and the
    process is not being called by salt-call
    '''
    if 'salt-call' in sys.argv[0]:
        return
    if not opts.get('multiprocessing', True):
        return
    if sys.platform.startswith('win'):
        return
    daemonize(False)


def systemd_notify_call(action):
    process = subprocess.Popen(['systemd-notify', action], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()
    status = process.poll()
    return status == 0


def notify_systemd():
    '''
    Notify systemd that this process has started
    '''
    try:
        import systemd.daemon  # pylint: disable=no-name-in-module
    except ImportError:
        if salt.utils.path.which('systemd-notify') \
                and systemd_notify_call('--booted'):
            # Notify systemd synchronously
            notify_socket = os.getenv('NOTIFY_SOCKET')
            if notify_socket:
                # Handle abstract namespace socket
                if notify_socket.startswith('@'):
                    notify_socket = '\0{0}'.format(notify_socket[1:])
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    sock.connect(notify_socket)
                    sock.sendall('READY=1'.encode())
                    sock.close()
                except socket.error:
                    return systemd_notify_call('--ready')
                return True
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
        with salt.utils.files.fopen(pidfile, 'w+') as ofile:
            ofile.write(str(os.getpid()))  # future lint: disable=blacklisted-function
    except IOError:
        pass

    log.debug('Created pidfile: %s', pidfile)
    if salt.utils.platform.is_windows():
        return True

    import pwd  # after confirming not running Windows
    #import grp
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
        #groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
    except (KeyError, IndexError):
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
        log.debug('%s Traceback follows:', msg, exc_info=True)
        sys.stderr.write('{0}\n'.format(msg))
        sys.exit(err.errno)
    log.debug('Chowned pidfile: %s to user: %s', pidfile, user)


def check_pidfile(pidfile):
    '''
    Determine if a pidfile has been written out
    '''
    return os.path.isfile(pidfile)


def get_pidfile(pidfile):
    '''
    Return the pid from a pidfile as an integer
    '''
    try:
        with salt.utils.files.fopen(pidfile) as pdf:
            pid = pdf.read().strip()
        return int(pid)
    except (OSError, IOError, TypeError, ValueError):
        return -1


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
                log.error('Process did not die with terminate(): %s', proc.pid)
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
    if isinstance(pid, six.string_types):
        pid = int(pid)
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
                try:
                    func, args, kwargs = self._job_queue.get(timeout=1)
                    self._job_queue.task_done()  # Mark the task as done once we get it
                except queue.Empty:
                    continue
            except AttributeError:
                # During shutdown, `queue` may not have an `Empty` atttribute. Thusly,
                # we have to catch a possible exception from our exception handler in
                # order to avoid an unclean shutdown. Le sigh.
                continue
            try:
                log.debug(
                    'ThreadPool executing func: %s with args=%s kwargs=%s',
                    func, args, kwargs
                )
                func(*args, **kwargs)
            except Exception as err:  # pylint: disable=broad-except
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
        self._restart_processes = True

    def add_process(self, tgt, args=None, kwargs=None, name=None):
        '''
        Create a processes and args + kwargs
        This will deterimine if it is a Process class, otherwise it assumes
        it is a function
        '''
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        if salt.utils.platform.is_windows():
            # Need to ensure that 'log_queue' and 'log_queue_level' is
            # correctly transferred to processes that inherit from
            # 'Process'.
            if type(Process) is type(tgt) and (
                    issubclass(tgt, Process)):
                need_log_queue = True
            else:
                need_log_queue = False

            if need_log_queue:
                if 'log_queue' not in kwargs:
                    if hasattr(self, 'log_queue'):
                        kwargs['log_queue'] = self.log_queue
                    else:
                        kwargs['log_queue'] = (
                            salt.log.setup.get_multiprocessing_logging_queue()
                        )
                if 'log_queue_level' not in kwargs:
                    if hasattr(self, 'log_queue_level'):
                        kwargs['log_queue_level'] = self.log_queue_level
                    else:
                        kwargs['log_queue_level'] = (
                            salt.log.setup.get_multiprocessing_logging_level()
                        )

        # create a nicer name for the debug log
        if name is None:
            if isinstance(tgt, types.FunctionType):
                name = '{0}.{1}'.format(
                    tgt.__module__,
                    tgt.__name__,
                )
            else:
                name = '{0}{1}.{2}'.format(
                    tgt.__module__,
                    '.{0}'.format(tgt.__class__) if six.text_type(tgt.__class__) != "<type 'type'>" else '',
                    tgt.__name__,
                )

        if type(multiprocessing.Process) is type(tgt) and issubclass(tgt, multiprocessing.Process):
            process = tgt(*args, **kwargs)
        else:
            process = multiprocessing.Process(target=tgt, args=args, kwargs=kwargs, name=name)

        if isinstance(process, SignalHandlingProcess):
            with default_signals(signal.SIGINT, signal.SIGTERM):
                process.start()
        else:
            process.start()
        log.debug("Started '%s' with pid %s", name, process.pid)
        self._process_map[process.pid] = {'tgt': tgt,
                                          'args': args,
                                          'kwargs': kwargs,
                                          'Process': process}
        return process

    def restart_process(self, pid):
        '''
        Create new process (assuming this one is dead), then remove the old one
        '''
        if self._restart_processes is False:
            return
        log.info(
            'Process %s (%s) died with exit status %s, restarting...',
            self._process_map[pid]['tgt'],
            pid,
            self._process_map[pid]['Process'].exitcode
        )
        # don't block, the process is already dead
        self._process_map[pid]['Process'].join(1)

        self.add_process(self._process_map[pid]['tgt'],
                         self._process_map[pid]['args'],
                         self._process_map[pid]['kwargs'])

        del self._process_map[pid]

    def stop_restarting(self):
        self._restart_processes = False

    def send_signal_to_processes(self, signal_):
        if (salt.utils.platform.is_windows() and
                signal_ in (signal.SIGTERM, signal.SIGINT)):
            # On Windows, the subprocesses automatically have their signal
            # handlers invoked. If you send one of these signals while the
            # signal handler is running, it will kill the process where it
            # is currently running and the signal handler will not finish.
            # This will also break the process tree: children of killed
            # children will become parentless and not findable when trying
            # to kill the process tree (they don't inherit their parent's
            # parent). Hence the 'MWorker' processes would be left over if
            # the 'ReqServer' process is killed this way since 'taskkill'
            # with the tree option will not be able to find them.
            return

        for pid in six.iterkeys(self._process_map.copy()):
            try:
                os.kill(pid, signal_)
            except OSError as exc:
                if exc.errno not in (errno.ESRCH, errno.EACCES):
                    # If it's not a "No such process" error, raise it
                    raise
                # Otherwise, it's a dead process, remove it from the process map
                del self._process_map[pid]

    @gen.coroutine
    def run(self, asynchronous=False):
        '''
        Load and start all available api modules
        '''
        log.debug('Process Manager starting!')
        appendproctitle(self.name)

        # make sure to kill the subprocesses if the parent is killed
        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # There are no SIGTERM handlers installed, install ours
            signal.signal(signal.SIGTERM, self.kill_children)
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # There are no SIGINT handlers installed, install ours
            signal.signal(signal.SIGINT, self.kill_children)

        while True:
            log.trace('Process manager iteration')
            try:
                # in case someone died while we were waiting...
                self.check_children()
                # The event-based subprocesses management code was removed from here
                # because os.wait() conflicts with the subprocesses management logic
                # implemented in `multiprocessing` package. See #35480 for details.
                if asynchronous:
                    yield gen.sleep(10)
                else:
                    time.sleep(10)
                if len(self._process_map) == 0:
                    break
            # OSError is raised if a signal handler is called (SIGTERM) during os.wait
            except OSError:
                break
            except IOError as exc:  # pylint: disable=duplicate-except
                # IOError with errno of EINTR (4) may be raised
                # when using time.sleep() on Windows.
                if exc.errno != errno.EINTR:
                    raise
                break

    def check_children(self):
        '''
        Check the children once
        '''
        if self._restart_processes is True:
            for pid, mapping in six.iteritems(self._process_map):
                if not mapping['Process'].is_alive():
                    log.trace('Process restart of %s', pid)
                    self.restart_process(pid)

    def kill_children(self, *args, **kwargs):
        '''
        Kill all of the children
        '''
        # first lets reset signal handlers to default one to prevent running this twice
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        # check that this is the correct process, children inherit this
        # handler, if we are in a child lets just run the original handler
        if os.getpid() != self._pid:
            if callable(self._sigterm_handler):
                return self._sigterm_handler(*args)
            elif self._sigterm_handler is not None:
                return signal.default_int_handler(signal.SIGTERM)(*args)
            else:
                return
        if salt.utils.platform.is_windows():
            if multiprocessing.current_process().name != 'MainProcess':
                # Since the main process will kill subprocesses by tree,
                # no need to do anything in the subprocesses.
                # Sometimes, when both a subprocess and the main process
                # call 'taskkill', it will leave a 'taskkill' zombie process.
                # We want to avoid this.
                return
            with salt.utils.files.fopen(os.devnull, 'wb') as devnull:
                for pid, p_map in six.iteritems(self._process_map):
                    # On Windows, we need to explicitly terminate sub-processes
                    # because the processes don't have a sigterm handler.
                    subprocess.call(
                        ['taskkill', '/F', '/T', '/PID', six.text_type(pid)],
                        stdout=devnull, stderr=devnull
                        )
                    p_map['Process'].terminate()
        else:
            for pid, p_map in six.iteritems(self._process_map.copy()):
                log.trace('Terminating pid %s: %s', pid, p_map['Process'])
                if args:
                    # escalate the signal to the process
                    try:
                        os.kill(pid, args[0])
                    except OSError:
                        pass
                try:
                    p_map['Process'].terminate()
                except OSError as exc:
                    if exc.errno not in (errno.ESRCH, errno.EACCES):
                        raise
                if not p_map['Process'].is_alive():
                    try:
                        del self._process_map[pid]
                    except KeyError:
                        # Race condition
                        pass

        end_time = time.time() + self.wait_for_kill  # when to die

        log.trace('Waiting to kill process manager children')
        while self._process_map and time.time() < end_time:
            for pid, p_map in six.iteritems(self._process_map.copy()):
                log.trace('Joining pid %s: %s', pid, p_map['Process'])
                p_map['Process'].join(0)

                if not p_map['Process'].is_alive():
                    # The process is no longer alive, remove it from the process map dictionary
                    try:
                        del self._process_map[pid]
                    except KeyError:
                        # This is a race condition if a signal was passed to all children
                        pass

        # if any managed processes still remain to be handled, let's kill them
        kill_iterations = 2
        while kill_iterations >= 0:
            kill_iterations -= 1
            for pid, p_map in six.iteritems(self._process_map.copy()):
                if not p_map['Process'].is_alive():
                    # The process is no longer alive, remove it from the process map dictionary
                    try:
                        del self._process_map[pid]
                    except KeyError:
                        # This is a race condition if a signal was passed to all children
                        pass
                    continue
                log.trace('Killing pid %s: %s', pid, p_map['Process'])
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError as exc:
                    log.exception(exc)
                    # in case the process has since decided to die, os.kill returns OSError
                    if not p_map['Process'].is_alive():
                        # The process is no longer alive, remove it from the process map dictionary
                        try:
                            del self._process_map[pid]
                        except KeyError:
                            # This is a race condition if a signal was passed to all children
                            pass

        if self._process_map:
            # Some processes disrespected the KILL signal!!!!
            available_retries = kwargs.get('retry', 3)
            if available_retries >= 0:
                log.info(
                    'Some processes failed to respect the KILL signal: %s',
                        '; '.join(
                            'Process: {0} (Pid: {1})'.format(v['Process'], k) for  # pylint: disable=str-format-in-logging
                            (k, v) in self._process_map.items()
                        )
                )
                log.info('kill_children retries left: %s', available_retries)
                kwargs['retry'] = available_retries - 1
                return self.kill_children(*args, **kwargs)
            else:
                log.warning(
                    'Failed to kill the following processes: %s',
                    '; '.join(
                        'Process: {0} (Pid: {1})'.format(v['Process'], k) for  # pylint: disable=str-format-in-logging
                        (k, v) in self._process_map.items()
                    )
                )
                log.warning(
                    'Salt will either fail to terminate now or leave some '
                    'zombie processes behind'
                )


class Process(multiprocessing.Process, NewStyleClassMixIn):

    def __init__(self, *args, **kwargs):
        log_queue = kwargs.pop('log_queue', None)
        log_queue_level = kwargs.pop('log_queue_level', None)
        super(Process, self).__init__(*args, **kwargs)
        if salt.utils.platform.is_windows():
            # On Windows, subclasses should call super if they define
            # __setstate__ and/or __getstate__
            self._args_for_getstate = copy.copy(args)
            self._kwargs_for_getstate = copy.copy(kwargs)
        self.log_queue = log_queue
        if self.log_queue is None:
            self.log_queue = salt.log.setup.get_multiprocessing_logging_queue()
        else:
            # Set the logging queue so that it can be retrieved later with
            # salt.log.setup.get_multiprocessing_logging_queue().
            salt.log.setup.set_multiprocessing_logging_queue(self.log_queue)

        self.log_queue_level = log_queue_level
        if self.log_queue_level is None:
            self.log_queue_level = salt.log.setup.get_multiprocessing_logging_level()
        else:
            salt.log.setup.set_multiprocessing_logging_level(self.log_queue_level)

        self._after_fork_methods = [
            (Process._setup_process_logging, [self], {}),
        ]
        self._finalize_methods = [
            (salt.log.setup.shutdown_multiprocessing_logging, [], {})
        ]

        # Because we need to enforce our after fork and finalize routines,
        # we must wrap this class run method to allow for these extra steps
        # to be executed pre and post calling the actual run method,
        # having subclasses call super would just not work.
        #
        # We use setattr here to fool pylint not to complain that we're
        # overriding run from the subclass here
        setattr(self, 'run', self.__decorate_run(self.run))

    # __setstate__ and __getstate__ are only used on Windows.
    def __setstate__(self, state):
        args = state['args']
        kwargs = state['kwargs']
        # This will invoke __init__ of the most derived class.
        self.__init__(*args, **kwargs)
        self._after_fork_methods = self._after_fork_methods
        self._finalize_methods = self._finalize_methods

    def __getstate__(self):
        args = self._args_for_getstate
        kwargs = self._kwargs_for_getstate
        if 'log_queue' not in kwargs:
            kwargs['log_queue'] = self.log_queue
        if 'log_queue_level' not in kwargs:
            kwargs['log_queue_level'] = self.log_queue_level
        return {'args': args,
                'kwargs': kwargs,
                '_after_fork_methods': self._after_fork_methods,
                '_finalize_methods': self._finalize_methods,
                }

    def _setup_process_logging(self):
        salt.log.setup.setup_multiprocessing_logging(self.log_queue)

    def __decorate_run(self, run_func):

        @functools.wraps(run_func)
        def wrapped_run_func():
            for method, args, kwargs in self._after_fork_methods:
                method(*args, **kwargs)
            try:
                return run_func()
            except SystemExit:
                # These are handled by multiprocessing.Process._bootstrap()
                six.reraise(*sys.exc_info())
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    'An un-handled exception from the multiprocessing process '
                    '\'%s\' was caught:\n', self.name, exc_info=True)
                # Re-raise the exception. multiprocessing.Process will write it to
                # sys.stderr and set the proper exitcode and we have already logged
                # it above.
                six.reraise(*sys.exc_info())
            finally:
                for method, args, kwargs in self._finalize_methods:
                    method(*args, **kwargs)

        return wrapped_run_func


class MultiprocessingProcess(Process):
    '''
    This class exists for backwards compatibility and to properly deprecate it.
    '''

    def __init__(self, *args, **kwargs):
        salt.utils.versions.warn_until_date(
            '20220101',
            'Please stop using \'{name}.MultiprocessingProcess\' and instead use '
            '\'{name}.Process\'. \'{name}.MultiprocessingProcess\' will go away '
            'after {{date}}.'.format(
                name=__name__
            ),
            stacklevel=3
        )
        super(MultiprocessingProcess, self).__init__(*args, **kwargs)


class SignalHandlingProcess(Process):
    def __init__(self, *args, **kwargs):
        super(SignalHandlingProcess, self).__init__(*args, **kwargs)
        self._signal_handled = multiprocessing.Event()
        self._after_fork_methods.append(
            (SignalHandlingProcess._setup_signals, [self], {})
        )

    def signal_handled(self):
        return self._signal_handled.is_set()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signals)
        signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):
        self._signal_handled.set()
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        msg = '{0} received a '.format(self.__class__.__name__)
        if signum == signal.SIGINT:
            msg += 'SIGINT'
        elif signum == signal.SIGTERM:
            msg += 'SIGTERM'
        msg += '. Exiting'
        log.debug(msg)
        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                if hasattr(process, 'children'):
                    for child in process.children(recursive=True):
                        try:
                            if child.is_running():
                                child.terminate()
                        except psutil.NoSuchProcess:
                            log.warn(
                                'Unable to kill child of process %d, it does '
                                'not exist. My pid is %d',
                                self.pid, os.getpid()
                            )
            except psutil.NoSuchProcess:
                log.warn(
                    'Unable to kill children of process %d, it does not exist.'
                    'My pid is %d',
                    self.pid, os.getpid()
                )
        sys.exit(salt.defaults.exitcodes.EX_OK)

    def start(self):
        with default_signals(signal.SIGINT, signal.SIGTERM):
            super(SignalHandlingProcess, self).start()


class SignalHandlingMultiprocessingProcess(SignalHandlingProcess):
    '''
    This class exists for backwards compatibility and to properly deprecate it.
    '''

    def __init__(self, *args, **kwargs):
        salt.utils.versions.warn_until_date(
            '20220101',
            'Please stop using \'{name}.SignalHandlingMultiprocessingProcess\' and instead use '
            '\'{name}.SignalHandlingProcess\'. \'{name}.SignalHandlingMultiprocessingProcess\' '
            'will go away after {{date}}.'.format(
                name=__name__
            ),
            stacklevel=3
        )
        super(SignalHandlingMultiprocessingProcess, self).__init__(*args, **kwargs)


@contextlib.contextmanager
def default_signals(*signals):
    old_signals = {}
    for signum in signals:
        try:
            saved_signal = signal.getsignal(signum)
            signal.signal(signum, signal.SIG_DFL)
        except ValueError as exc:
            # This happens when a netapi module attempts to run a function
            # using wheel_async, because the process trying to register signals
            # will not be the main PID.
            log.trace(
                'Failed to register signal for signum %d: %s',
                signum, exc
            )
        else:
            old_signals[signum] = saved_signal

    # Do whatever is needed with the reset signals
    yield

    # Restore signals
    for signum in old_signals:
        signal.signal(signum, old_signals[signum])

    del old_signals


class SubprocessList(object):

    def __init__(self, processes=None, lock=None):
        if processes is None:
            self.processes = []
        else:
            self.processes = processes
        if lock is None:
            self.lock = multiprocessing.Lock()
        else:
            self.lock = lock

    def add(self, proc):
        with self.lock:
            self.processes.append(proc)
            log.debug('Subprocess %s added', proc.name)

    def cleanup(self):
        with self.lock:
            for proc in self.processes:
                if proc.is_alive():
                    continue
                proc.join()
                self.processes.remove(proc)
                log.debug('Subprocess %s cleaned up', proc.name)
