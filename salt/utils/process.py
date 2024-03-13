"""
Functions for daemonizing and otherwise modifying running processes
"""

import contextlib
import copy
import errno
import functools
import inspect
import io
import json
import logging
import multiprocessing
import multiprocessing.util
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time

from tornado import gen

import salt._logging
import salt.defaults.exitcodes
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.versions

log = logging.getLogger(__name__)

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
    """
    Append "name" to the current process title
    """
    if HAS_SETPROCTITLE:
        current = setproctitle.getproctitle()
        if current.strip().endswith("MainProcess"):
            current, _ = current.rsplit("MainProcess", 1)
        setproctitle.setproctitle(f"{current.rstrip()} {name}")


def daemonize(redirect_out=True):
    """
    Daemonize a process
    """
    # Avoid circular import
    import salt.utils.crypt

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            salt.utils.crypt.reinit_crypto()
            os._exit(salt.defaults.exitcodes.EX_OK)
    except OSError as exc:
        log.error("fork #1 failed: %s (%s)", exc.errno, exc)
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    # decouple from parent environment
    os.chdir("/")
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
        log.error("fork #2 failed: %s (%s)", exc.errno, exc)
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    salt.utils.crypt.reinit_crypto()

    # A normal daemonization redirects the process output to /dev/null.
    # Unfortunately when a python multiprocess is called the output is
    # not cleanly redirected and the parent process dies when the
    # multiprocessing process attempts to access stdout or err.
    if redirect_out:
        with salt.utils.files.fopen("/dev/null", "r+") as dev_null:
            # Redirect python stdin/out/err
            # and the os stdin/out/err which can be different
            dup2(dev_null, sys.stdin)
            dup2(dev_null, sys.stdout)
            dup2(dev_null, sys.stderr)
            dup2(dev_null, 0)
            dup2(dev_null, 1)
            dup2(dev_null, 2)


def dup2(file1, file2):
    """
    Duplicate file descriptor fd to fd2, closing the latter first if necessary.
    This method is similar to os.dup2 but ignores streams that do not have a
    supported fileno method.
    """
    if isinstance(file1, int):
        fno1 = file1
    else:
        try:
            fno1 = file1.fileno()
        except io.UnsupportedOperation:
            log.warning("Unsupported operation on file: %r", file1)
            return
    if isinstance(file2, int):
        fno2 = file2
    else:
        try:
            fno2 = file2.fileno()
        except io.UnsupportedOperation:
            log.warning("Unsupported operation on file: %r", file2)
            return
    os.dup2(fno1, fno2)


def daemonize_if(opts):
    """
    Daemonize a module function process if multiprocessing is True and the
    process is not being called by salt-call
    """
    if "salt-call" in sys.argv[0]:
        return
    if not opts.get("multiprocessing", True):
        return
    if sys.platform.startswith("win"):
        return
    daemonize(False)


def systemd_notify_call(action):
    """
    Notify systemd that this process has started
    """
    process = subprocess.Popen(
        ["systemd-notify", action], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    process.communicate()
    status = process.poll()
    return status == 0


def notify_systemd():
    """
    Notify systemd that this process has started
    """
    try:
        import systemd.daemon  # pylint: disable=no-name-in-module
    except ImportError:
        if salt.utils.path.which("systemd-notify") and systemd_notify_call("--booted"):
            # Notify systemd synchronously
            notify_socket = os.getenv("NOTIFY_SOCKET")
            if notify_socket:
                # Handle abstract namespace socket
                if notify_socket.startswith("@"):
                    notify_socket = f"\0{notify_socket[1:]}"
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    sock.connect(notify_socket)
                    sock.sendall(b"READY=1")
                    sock.close()
                except OSError:
                    return systemd_notify_call("--ready")
                return True
        return False

    if systemd.daemon.booted():
        try:
            return systemd.daemon.notify("READY=1")
        except SystemError:
            # Daemon was not started by systemd
            pass


def get_process_info(pid=None):
    """
    Gets basic info about a process.
    pid: None, or int: None will get the current process pid
    Return: None or Dict
    """
    if pid is None:
        pid = os.getpid()
    elif not psutil.pid_exists(pid):
        return

    raw_process_info = psutil.Process(pid)

    # pid_exists can have false positives
    # for example Windows reserves PID 5 in a hack way
    # another reasons is the the process requires kernel permissions
    try:
        raw_process_info.status()
    except psutil.NoSuchProcess:
        return None

    return {
        "pid": raw_process_info.pid,
        "name": raw_process_info.name(),
        "start_time": raw_process_info.create_time(),
    }


def claim_mantle_of_responsibility(file_name):
    """
    Checks that no other live processes has this responsibility.
    If claiming the mantle of responsibility was successful True will be returned.
    file_name: str
    Return: bool
    """

    # all OSs supported by salt has psutil
    if not HAS_PSUTIL:
        log.critical(
            "Assuming no other Process has this responsibility! pidfile: %s", file_name
        )
        return True

    # add file directory if missing
    file_directory_name = os.path.dirname(file_name)
    if not os.path.isdir(file_directory_name) and file_directory_name:
        os.makedirs(file_directory_name)

    # get process info from file
    file_process_info = None
    try:
        with salt.utils.files.fopen(file_name, "r") as file:
            file_process_info = json.load(file)
    except json.decoder.JSONDecodeError:
        log.error("pidfile: %s is corrupted", file_name)
    except FileNotFoundError:
        log.info("pidfile: %s not found", file_name)

    this_process_info = get_process_info()

    # check if this process all ready has the responsibility
    if file_process_info == this_process_info:
        return True

    if not isinstance(file_process_info, dict) or not isinstance(
        file_process_info.get("pid"), int
    ):
        file_process_info = None

    # check if process is still alive
    if isinstance(file_process_info, dict) and file_process_info == get_process_info(
        file_process_info.get("pid")
    ):
        return False

    # process can take the mantle of responsibility
    with salt.utils.files.fopen(file_name, "w") as file:
        json.dump(this_process_info, file)
    return True


def check_mantle_of_responsibility(file_name):
    """
    Sees who has the mantle of responsibility
    file_name: str
    Return: None or int
    """

    # all OSs supported by salt has psutil
    if not HAS_PSUTIL:
        log.critical(
            "Assuming no other Process has this responsibility! pidfile: %s", file_name
        )
        return

    # get process info from file
    try:
        with salt.utils.files.fopen(file_name, "r") as file:
            file_process_info = json.load(file)
    except json.decoder.JSONDecodeError:
        log.error("pidfile: %s is corrupted", file_name)
        return
    except FileNotFoundError:
        log.info("pidfile: %s not found", file_name)
        return

    if not isinstance(file_process_info, dict) or not isinstance(
        file_process_info.get("pid"), int
    ):
        return

    if file_process_info == get_process_info(file_process_info["pid"]):
        return file_process_info["pid"]


def set_pidfile(pidfile, user):
    """
    Save the pidfile
    """
    pdir = os.path.dirname(pidfile)
    if not os.path.isdir(pdir) and pdir:
        os.makedirs(pdir)
    try:
        with salt.utils.files.fopen(pidfile, "w+") as ofile:
            ofile.write(str(os.getpid()))
    except OSError:
        pass

    log.debug("Created pidfile: %s", pidfile)
    if salt.utils.platform.is_windows():
        return True

    import pwd  # after confirming not running Windows

    # import grp
    try:
        pwnam = pwd.getpwnam(user)
        uid = pwnam[2]
        gid = pwnam[3]
        # groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
    except (KeyError, IndexError):
        sys.stderr.write(
            "Failed to set the pid to user: {}. The user is not available.\n".format(
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
        msg = "Failed to set the ownership of PID file {} to user {}.".format(
            pidfile, user
        )
        log.debug("%s Traceback follows:", msg, exc_info=True)
        sys.stderr.write(f"{msg}\n")
        sys.exit(err.errno)
    log.debug("Chowned pidfile: %s to user: %s", pidfile, user)


def check_pidfile(pidfile):
    """
    Determine if a pidfile has been written out
    """
    return os.path.isfile(pidfile)


def get_pidfile(pidfile):
    """
    Return the pid from a pidfile as an integer
    """
    try:
        with salt.utils.files.fopen(pidfile) as pdf:
            pid = pdf.read().strip()
        return int(pid)
    except (OSError, TypeError, ValueError):
        return -1


def clean_proc(proc, wait_for_kill=10):
    """
    Generic method for cleaning up multiprocessing procs
    """
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
                log.error("Process did not die with terminate(): %s", proc.pid)
                os.kill(proc.pid, signal.SIGKILL)
    except (AssertionError, AttributeError):
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass


def os_is_running(pid):
    """
    Use OS facilities to determine if a process is running
    """
    if isinstance(pid, str):
        pid = int(pid)
    if HAS_PSUTIL:
        return psutil.pid_exists(pid)
    else:
        try:
            os.kill(pid, 0)  # SIG 0 is the "are you alive?" signal
            return True
        except OSError:
            return False


class ThreadPool:
    """
    This is a very VERY basic threadpool implementation
    This was made instead of using multiprocessing ThreadPool because
    we want to set max queue size and we want to daemonize threads (neither
    is exposed in the stdlib version).

    Since there isn't much use for this class as of right now this implementation
    Only supports daemonized threads and will *not* return results

    TODO: if this is found to be more generally useful it would be nice to pull
    in the majority of code from upstream or from http://bit.ly/1wTeJtM
    """

    def __init__(self, num_threads=None, queue_size=0):
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
                    "ThreadPool executing func: %s with args=%s kwargs=%s",
                    func,
                    args,
                    kwargs,
                )
                func(*args, **kwargs)
            except Exception as err:  # pylint: disable=broad-except
                log.debug(err, exc_info=True)


class ProcessManager:
    """
    A class which will manage processes that should be running
    """

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
        """
        Create a processes and args + kwargs
        This will deterimine if it is a Process class, otherwise it assumes
        it is a function
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        if inspect.isclass(tgt) and issubclass(tgt, multiprocessing.Process):
            kwargs["name"] = name or tgt.__qualname__
            process = tgt(*args, **kwargs)
        else:
            process = Process(
                target=tgt, args=args, kwargs=kwargs, name=name or tgt.__qualname__
            )

        if isinstance(process, SignalHandlingProcess):
            with default_signals(signal.SIGINT, signal.SIGTERM):
                process.start()
        else:
            process.start()
        log.debug("Started '%s' with pid %s", process.name, process.pid)
        self._process_map[process.pid] = {
            "tgt": tgt,
            "args": args,
            "kwargs": kwargs,
            "Process": process,
        }
        return process

    def restart_process(self, pid):
        """
        Create new process (assuming this one is dead), then remove the old one
        """
        if self._restart_processes is False:
            return
        exit = self._process_map[pid]["Process"].exitcode
        if exit > 0:
            log.info(
                "Process %s (%s) died with exit status %s, restarting...",
                self._process_map[pid]["tgt"],
                pid,
                self._process_map[pid]["Process"].exitcode,
            )
        else:
            log.debug(
                "Process %s (%s) died with exit status %s, restarting...",
                self._process_map[pid]["tgt"],
                pid,
                self._process_map[pid]["Process"].exitcode,
            )
        # don't block, the process is already dead
        self._process_map[pid]["Process"].join(1)

        self.add_process(
            self._process_map[pid]["tgt"],
            self._process_map[pid]["args"],
            self._process_map[pid]["kwargs"],
        )

        del self._process_map[pid]

    def stop_restarting(self):
        self._restart_processes = False

    def send_signal_to_processes(self, signal_):
        if salt.utils.platform.is_windows() and signal_ in (
            signal.SIGTERM,
            signal.SIGINT,
        ):
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

        for pid in self._process_map.copy():
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
        """
        Load and start all available api modules
        """
        log.debug("Process Manager starting!")
        if multiprocessing.current_process().name != "MainProcess":
            appendproctitle(self.name)

        # make sure to kill the subprocesses if the parent is killed
        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # There are no SIGTERM handlers installed, install ours
            signal.signal(signal.SIGTERM, self._handle_signals)
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # There are no SIGINT handlers installed, install ours
            signal.signal(signal.SIGINT, self._handle_signals)

        while True:
            log.trace("Process manager iteration")
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
                if not self._process_map:
                    break
            # OSError is raised if a signal handler is called (SIGTERM) during os.wait
            except OSError:
                break
            except OSError as exc:  # pylint: disable=duplicate-except
                # IOError with errno of EINTR (4) may be raised
                # when using time.sleep() on Windows.
                if exc.errno != errno.EINTR:
                    raise
                break

    def check_children(self):
        """
        Check the children once
        """
        if self._restart_processes is True:
            for pid, mapping in self._process_map.copy().items():
                if not mapping["Process"].is_alive():
                    log.trace("Process restart of %s", pid)
                    self.restart_process(pid)

    def kill_children(self, *args, **kwargs):
        """
        Kill all of the children
        """
        if salt.utils.platform.is_windows():
            if multiprocessing.current_process().name != "MainProcess":
                # Since the main process will kill subprocesses by tree,
                # no need to do anything in the subprocesses.
                # Sometimes, when both a subprocess and the main process
                # call 'taskkill', it will leave a 'taskkill' zombie process.
                # We want to avoid this.
                return
            with salt.utils.files.fopen(os.devnull, "wb") as devnull:
                for pid, p_map in self._process_map.items():
                    # On Windows, we need to explicitly terminate sub-processes
                    # because the processes don't have a sigterm handler.
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdout=devnull,
                        stderr=devnull,
                    )
                    p_map["Process"].terminate()
        else:
            for pid, p_map in self._process_map.copy().items():
                log.trace("Terminating pid %s: %s", pid, p_map["Process"])
                if args:
                    # escalate the signal to the process
                    try:
                        os.kill(pid, args[0])
                    except OSError:
                        pass
                try:
                    p_map["Process"].terminate()
                except OSError as exc:
                    if exc.errno not in (errno.ESRCH, errno.EACCES):
                        raise
                if not p_map["Process"].is_alive():
                    try:
                        del self._process_map[pid]
                    except KeyError:
                        # Race condition
                        pass

        end_time = time.time() + self.wait_for_kill  # when to die

        log.trace("Waiting to kill process manager children")
        while self._process_map and time.time() < end_time:
            for pid, p_map in self._process_map.copy().items():
                log.trace("Joining pid %s: %s", pid, p_map["Process"])
                p_map["Process"].join(0)

                if not p_map["Process"].is_alive():
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
            for pid, p_map in self._process_map.copy().items():
                if not p_map["Process"].is_alive():
                    # The process is no longer alive, remove it from the process map dictionary
                    try:
                        del self._process_map[pid]
                    except KeyError:
                        # This is a race condition if a signal was passed to all children
                        pass
                    continue
                log.trace("Killing pid %s: %s", pid, p_map["Process"])
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError as exc:
                    log.exception(exc)
                    # in case the process has since decided to die, os.kill returns OSError
                    if not p_map["Process"].is_alive():
                        # The process is no longer alive, remove it from the process map dictionary
                        try:
                            del self._process_map[pid]
                        except KeyError:
                            # This is a race condition if a signal was passed to all children
                            pass

        if self._process_map:
            # Some processes disrespected the KILL signal!!!!
            available_retries = kwargs.get("retry", 3)
            if available_retries >= 0:
                log.info(
                    "Some processes failed to respect the KILL signal: %s",
                    "; ".join(
                        "Process: {} (Pid: {})".format(v["Process"], k)
                        for (k, v) in self._process_map.items()
                    ),
                )
                log.info("kill_children retries left: %s", available_retries)
                kwargs["retry"] = available_retries - 1
                return self.kill_children(*args, **kwargs)
            else:
                log.warning(
                    "Failed to kill the following processes: %s",
                    "; ".join(
                        "Process: {} (Pid: {})".format(v["Process"], k)
                        for (
                            k,
                            v,
                        ) in self._process_map.items()
                    ),
                )
                log.warning(
                    "Salt will either fail to terminate now or leave some "
                    "zombie processes behind"
                )

    def terminate(self):
        """
        Properly terminate this process manager instance
        """
        self.stop_restarting()
        self.send_signal_to_processes(signal.SIGTERM)
        self.kill_children()

    def _handle_signals(self, *args, **kwargs):
        # first lets reset signal handlers to default one to prevent running this twice
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.stop_restarting()
        self.send_signal_to_processes(signal.SIGTERM)

        # check that this is the correct process, children inherit this
        # handler, if we are in a child lets just run the original handler
        if os.getpid() != self._pid:
            if callable(self._sigterm_handler):
                return self._sigterm_handler(*args)
            elif self._sigterm_handler is not None:
                return signal.default_int_handler(signal.SIGTERM)(*args)
            else:
                return

        # Terminate child processes
        self.kill_children(*args, **kwargs)


class Process(multiprocessing.Process):
    """
    Salt relies on this custom implementation of :py:class:`~multiprocessing.Process` to
    simplify/automate some common procedures, for example, logging in the new process is
    configured for "free" for every new process.
    This is most important in platforms which default to ``spawn` instead of ``fork`` for
    new processes.

    This is achieved by some dunder methods in the class:

    * ``__new__``:

        This method ensures that any arguments and/or keyword arguments that are passed to
        ``__init__`` are captured.

        By having this information captured, we can define ``__setstate__`` and ``__getstate__``
        to automatically take care of reconstructing the object state on spawned processes.

    * ``__getstate__``:

        This method should return a dictionary which will be used as the ``state`` argument to
        :py:method:`salt.utils.process.Process.__setstate__`.
        Usually, when subclassing, this method does not need to be implemented, however,
        if implemented, `super()` **must** be called.

    * ``__setstate__``:

        This method reconstructs the object on the spawned process.
        The ``state`` argument is constructed by the
        :py:method:`salt.utils.process.Process.__getstate__` method.
        Usually, when subclassing, this method does not need to be implemented, however,
        if implemented, `super()` **must** be called.


    An example of where ``__setstate__`` and ``__getstate__`` needed to be subclassed can be
    seen in :py:class:`salt.master.MWorker`.

    The gist of it is something like, if there are internal attributes which need to maintain
    their state on spawned processes, then, subclasses must implement ``__getstate__`` and
    ``__setstate__`` to ensure that.


    For example:


    .. code-block:: python

        import salt.utils.process

        class MyCustomProcess(salt.utils.process.Process):

            def __init__(self, opts, **kwargs):
                super().__init__(**kwargs)
                self.opts = opts

                # This attribute, counter, should only start at 0 on the initial(parent) process.
                # Any child processes, need to carry the current value of the counter(instead of
                # starting at zero).
                self.counter = 0

            def __getstate__(self):
                state = super().__getstate__()
                state.update(
                    {
                        "counter": self.counter,
                    }
                )
                return state

            def __setstate__(self, state):
                super().__setstate__(state)
                self.counter = state["counter"]
    """

    def __new__(cls, *args, **kwargs):
        """
        This method ensures that any arguments and/or keyword arguments that are passed to
        ``__init__`` are captured.

        By having this information captured, we can define ``__setstate__`` and ``__getstate__``
        to automatically take care of object pickling which is required for platforms that
        spawn processes instead of forking them.
        """
        # We implement __new__ because we want to capture the passed in *args and **kwargs
        # in order to remove the need for each class to implement __getstate__ and __setstate__
        # which is required on spawning platforms
        instance = super().__new__(cls)
        instance._after_fork_methods = []
        instance._finalize_methods = []
        instance.__logging_config__ = salt._logging.get_logging_options_dict()

        if salt.utils.platform.spawning_platform():
            # On spawning platforms, subclasses should call super if they define
            # __setstate__ and/or __getstate__
            instance._args_for_getstate = copy.copy(args)
            instance._kwargs_for_getstate = copy.copy(kwargs)

        # Because we need to enforce our after fork and finalize routines,
        # we must wrap this class run method to allow for these extra steps
        # to be executed pre and post calling the actual run method,
        # having subclasses call super would just not work.
        #
        # We use setattr here to fool pylint not to complain that we're
        # overriding run from the subclass here
        setattr(instance, "run", instance.__decorate_run(instance.run))
        return instance

    # __setstate__ and __getstate__ are only used on spawning platforms.
    def __setstate__(self, state):
        """
        This method reconstructs the object on the spawned process.
        The ``state`` argument is constructed by :py:method:`salt.utils.process.Process.__getstate__`.

        Usually, when subclassing, this method does not need to be implemented, however,
        if implemented, `super()` **must** be called.
        """
        args = state["args"]
        kwargs = state["kwargs"]
        logging_config = state["logging_config"]
        # This will invoke __init__ of the most derived class.
        self.__init__(*args, **kwargs)
        # Override self.__logging_config__ with what's in state
        self.__logging_config__ = logging_config
        for function, args, kwargs in state["after_fork_methods"]:
            self.register_after_fork_method(function, *args, **kwargs)
        for function, args, kwargs in state["finalize_methods"]:
            self.register_finalize_method(function, *args, **kwargs)

    def __getstate__(self):
        """
        This method should return a dictionary which will be used as the ``state`` argument to
        :py:method:`salt.utils.process.Process.__setstate__`.
        Usually, when subclassing, this method does not need to be implemented, however,
        if implemented, `super()` **must** be called.
        """
        args = self._args_for_getstate
        kwargs = self._kwargs_for_getstate
        return {
            "args": args,
            "kwargs": kwargs,
            "after_fork_methods": self._after_fork_methods,
            "finalize_methods": self._finalize_methods,
            "logging_config": self.__logging_config__,
        }

    def __decorate_run(self, run_func):  # pylint: disable=unused-private-member
        @functools.wraps(run_func)
        def wrapped_run_func():
            # Static after fork method, always needs to happen first
            appendproctitle(self.name)

            # Set the logging options dictionary if not already set
            if not salt._logging.get_logging_options_dict():
                salt._logging.set_logging_options_dict(self.__logging_config__)

            if not salt.utils.platform.spawning_platform():
                # On non-spawning platforms, the new process inherits the parent
                # process logging setup.
                # To be on the safe side and avoid duplicate handlers or handlers which connect
                # to services which would have to reconnect, we just shutdown logging before
                # setting it up again.
                try:
                    salt._logging.shutdown_logging()
                except Exception as exc:  # pylint: disable=broad-except
                    log.exception(
                        "Failed to shutdown logging when starting on %s: %s", self, exc
                    )

            # Setup logging on the new process
            try:
                salt._logging.setup_logging()
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "Failed to configure logging on %s: %s",
                    self,
                    exc,
                )

            # Run any after fork methods registered
            for method, args, kwargs in self._after_fork_methods:
                try:
                    method(*args, **kwargs)
                except Exception:  # pylint: disable=broad-except
                    log.exception(
                        "Failed to run after fork callback on %s; method=%r; args=%r; and kwargs=%r",
                        self,
                        method,
                        args,
                        kwargs,
                    )
                    continue
            try:
                # Run the process target function
                return run_func()
            except SystemExit:  # pylint: disable=try-except-raise
                # These are handled by multiprocessing.Process._bootstrap()
                raise
            except Exception:  # pylint: disable=broad-except
                log.error(
                    "An un-handled exception from the multiprocessing process "
                    "'%s' was caught:\n",
                    self.name,
                    exc_info=True,
                )
                # Re-raise the exception. multiprocessing.Process will write it to
                # sys.stderr and set the proper exitcode and we have already logged
                # it above.
                raise
            finally:
                # Run any registered process finalization routines
                try:
                    for method, args, kwargs in self._finalize_methods:
                        try:
                            method(*args, **kwargs)
                        except Exception:  # pylint: disable=broad-except
                            log.exception(
                                "Failed to run finalize callback on %s; method=%r; args=%r; and kwargs=%r",
                                self,
                                method,
                                args,
                                kwargs,
                            )
                            continue
                finally:
                    # Static finalize method, should always run last, shutdown logging.
                    try:
                        salt._logging.shutdown_logging()
                    except Exception as exc:  # pylint: disable=broad-except
                        log.exception("Failed to shutdown logging on %s: %s", self, exc)

        return wrapped_run_func

    def register_after_fork_method(self, function, *args, **kwargs):
        """
        Register a function to run after the process has forked
        """
        after_fork_method_tuple = (function, args, kwargs)
        if after_fork_method_tuple not in self._after_fork_methods:
            self._after_fork_methods.append(after_fork_method_tuple)

    def register_finalize_method(self, function, *args, **kwargs):
        """
        Register a function to run as process terminates
        """
        finalize_method_tuple = (function, args, kwargs)
        if finalize_method_tuple not in self._finalize_methods:
            self._finalize_methods.append(finalize_method_tuple)


class SignalHandlingProcess(Process):
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        instance.register_after_fork_method(
            SignalHandlingProcess._setup_signals, instance
        )
        return instance

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signals)
        signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        msg = f"{self.__class__.__name__} received a "
        if signum == signal.SIGINT:
            msg += "SIGINT"
        elif signum == signal.SIGTERM:
            msg += "SIGTERM"
        msg += ". Exiting"
        log.debug(msg)
        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                if hasattr(process, "children"):
                    for child in process.children(recursive=True):
                        try:
                            if child.is_running():
                                child.terminate()
                        except psutil.NoSuchProcess:
                            log.warning(
                                "Unable to kill child of process %d, it does "
                                "not exist. My pid is %d",
                                self.pid,
                                os.getpid(),
                            )
            except psutil.NoSuchProcess:
                log.warning(
                    "Unable to kill children of process %d, it does not exist."
                    "My pid is %d",
                    self.pid,
                    os.getpid(),
                )
        # It's OK to call os._exit instead of sys.exit on forked processed
        os._exit(salt.defaults.exitcodes.EX_OK)

    def start(self):
        with default_signals(signal.SIGINT, signal.SIGTERM):
            super().start()


@contextlib.contextmanager
def default_signals(*signals):
    """
    Temporarily restore signals to their default values.
    """
    old_signals = {}
    for signum in signals:
        try:
            saved_signal = signal.getsignal(signum)
            signal.signal(signum, signal.SIG_DFL)
        except ValueError as exc:
            # This happens when a netapi module attempts to run a function
            # using wheel_async, because the process trying to register signals
            # will not be the main PID.
            log.trace("Failed to register signal for signum %d: %s", signum, exc)
        else:
            old_signals[signum] = saved_signal

    try:
        # Do whatever is needed with the reset signals
        yield
    finally:
        # Restore signals
        for signum in old_signals:
            signal.signal(signum, old_signals[signum])

        del old_signals


class SubprocessList:
    def __init__(self, processes=None, lock=None):
        if processes is None:
            self.processes = []
        else:
            self.processes = processes
        if lock is None:
            self.lock = multiprocessing.Lock()
        else:
            self.lock = lock
        self.count = 0

    def add(self, proc):
        with self.lock:
            self.processes.append(proc)
            log.debug("Subprocess %s added", proc.name)
            self.count += 1

    def cleanup(self):
        with self.lock:
            for proc in self.processes:
                if proc.is_alive():
                    continue
                proc.join()
                self.processes.remove(proc)
                self.count -= 1
                log.debug("Subprocess %s cleaned up", proc.name)
