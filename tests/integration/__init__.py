# -*- coding: utf-8 -*-

'''
Set up the Salt integration test suite
'''

# Import Python libs
from __future__ import absolute_import, print_function
import os
import re
import sys
import copy
import json
import time
import stat
import errno
import signal
import shutil
import pprint
import atexit
import socket
import logging
import tempfile
import threading
import subprocess
import multiprocessing
from datetime import datetime, timedelta
try:
    import pwd
except ImportError:
    pass

STATE_FUNCTION_RUNNING_RE = re.compile(
    r'''The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID '''
    r'(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)'
)
INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.case import ShellTestCase
from salttesting.mixins import CheckShellBinaryNameAndVersionMixIn
from salttesting.parser import PNUM, print_header, SaltTestcaseParser
from salttesting.helpers import requires_sshd_server
from salttesting.helpers import ensure_in_syspath, RedirectStdStreams

# Update sys.path
ensure_in_syspath(CODE_DIR)

# Import Salt libs
import salt
import salt.config
import salt.minion
import salt.runner
import salt.output
import salt.version
import salt.utils
import salt.utils.process
import salt.log.setup as salt_log_setup
from salt.ext import six
from salt.utils.verify import verify_env
from salt.utils.immutabletypes import freeze
from salt.utils.nb_popen import NonBlockingPopen
from salt.exceptions import SaltClientError

try:
    from shlex import quote as _quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _quote

try:
    import salt.master
except ImportError:
    # Not required for raet tests
    pass

# Import 3rd-party libs
import yaml
import msgpack
import salt.ext.six as six
from salt.ext.six.moves import cStringIO

try:
    import salt.ext.six.moves.socketserver as socketserver
except ImportError:
    import socketserver

if salt.utils.is_windows():
    import win32api

from tornado import gen
from tornado import ioloop

try:
    from salttesting.helpers import terminate_process_pid
except ImportError:
    # Once the latest salt-testing works against salt's develop branch
    # uncomment the following 2 lines and delete the function defined
    # in this except
    #print('Please upgrade your version of salt-testing')
    #sys.exit(1)

    import psutil

    def terminate_process_pid(pid, only_children=False):
        children = []
        process = None

        # Let's begin the shutdown routines
        if sys.platform.startswith('win'):
            sigint = signal.CTRL_BREAK_EVENT  # pylint: disable=no-member
            sigint_name = 'CTRL_BREAK_EVENT'
        else:
            sigint = signal.SIGINT
            sigint_name = 'SIGINT'

        try:
            process = psutil.Process(pid)
            if hasattr(process, 'children'):
                children = process.children(recursive=True)
        except psutil.NoSuchProcess:
            log.info('No process with the PID %s was found running', pid)

        if process and only_children is False:
            try:
                cmdline = process.cmdline()
            except psutil.AccessDenied:
                # macOS denies us access to the above information
                cmdline = None
            if not cmdline:
                try:
                    cmdline = process.as_dict()
                except psutil.NoSuchProcess as exc:
                    log.debug('No such process found. Stacktrace: {0}'.format(exc))
            log.info('Sending %s to process: %s', sigint_name, cmdline)
            process.send_signal(sigint)
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                pass

            if psutil.pid_exists(pid):
                log.info('Terminating process: %s', cmdline)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    pass

            if psutil.pid_exists(pid):
                log.warning('Killing process: %s', cmdline)
                process.kill()

            if psutil.pid_exists(pid):
                log.warning('Process left behind which we were unable to kill: %s', cmdline)
        if children:
            # Lets log and kill any child processes which salt left behind
            def kill_children(_children, terminate=False, kill=False):
                for child in _children[:][::-1]:  # Iterate over a reversed copy of the list
                    try:
                        if not kill and child.status() == psutil.STATUS_ZOMBIE:
                            # Zombie processes will exit once child processes also exit
                            continue
                        try:
                            cmdline = child.cmdline()
                        except psutil.AccessDenied as err:
                            log.debug('Cannot obtain child process cmdline: %s', err)
                            cmdline = ''
                        if not cmdline:
                            cmdline = child.as_dict()
                        if kill:
                            log.warning('Killing child process left behind: %s', cmdline)
                            child.kill()
                        elif terminate:
                            log.warning('Terminating child process left behind: %s', cmdline)
                            child.terminate()
                        else:
                            log.warning('Sending %s to child process left behind: %s', sigint_name, cmdline)
                            child.send_signal(sigint)
                        if not psutil.pid_exists(child.pid):
                            _children.remove(child)
                    except psutil.NoSuchProcess:
                        _children.remove(child)

            kill_children(children)

            if children:
                try:
                    psutil.wait_procs(children, timeout=10, callback=lambda proc: kill_children(children, terminate=True))
                except psutil.AccessDenied:
                    kill_children(children, terminate=True)

            if children:
                try:
                    psutil.wait_procs(children, timeout=5, callback=lambda proc: kill_children(children, kill=True))
                except psutil.AccessDenied:
                    kill_children(children, kill=True)

SYS_TMP_DIR = os.path.realpath(
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    os.environ.get('TMPDIR', tempfile.gettempdir()) if not salt.utils.is_darwin() else '/tmp'
)
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
PYEXEC = 'python{0}.{1}'.format(*sys.version_info)
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_PRODENV_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-prodenv-state-tree')
TMP_CONF_DIR = os.path.join(TMP, 'config')
TMP_SUB_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'sub-minion')
TMP_SYNDIC_MINION_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-minion')
TMP_SYNDIC_MASTER_CONF_DIR = os.path.join(TMP_CONF_DIR, 'syndic-master')
CONF_DIR = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
PILLAR_DIR = os.path.join(FILES, 'pillar')
TMP_SCRIPT_DIR = os.path.join(TMP, 'scripts')
ENGINES_DIR = os.path.join(FILES, 'engines')
LOG_HANDLERS_DIR = os.path.join(FILES, 'log_handlers')

SCRIPT_TEMPLATES = {
    'salt': [
        'from salt.scripts import salt_main\n',
        'if __name__ == \'__main__\':\n'
        '    salt_main()'
    ],
    'salt-api': [
        'import salt.cli\n',
        'def main():\n',
        '    sapi = salt.cli.SaltAPI()',
        '    sapi.run()\n',
        'if __name__ == \'__main__\':',
        '    main()'
    ],
    'common': [
        'from salt.scripts import salt_{0}\n',
        'from salt.utils import is_windows\n\n',
        'if __name__ == \'__main__\':\n',
        '    if is_windows():\n',
        '        import os.path\n',
        '        import py_compile\n',
        '        cfile = os.path.splitext(__file__)[0] + ".pyc"\n',
        '        if not os.path.exists(cfile):\n',
        '            py_compile.compile(__file__, cfile)\n',
        '    salt_{0}()'
    ]
}
RUNTIME_CONFIGS = {}

log = logging.getLogger(__name__)


def cleanup_runtime_config_instance(to_cleanup):
    # Explicit and forced cleanup
    for key in list(to_cleanup.keys()):
        instance = to_cleanup.pop(key)
        del instance


atexit.register(cleanup_runtime_config_instance, RUNTIME_CONFIGS)

_RUNTESTS_PORTS = {}


def get_unused_localhost_port():
    '''
    Return a random unused port on localhost
    '''
    usock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    usock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    usock.bind(('127.0.0.1', 0))
    port = usock.getsockname()[1]
    if port in (54505, 54506, 64505, 64506, 64510, 64511, 64520, 64521):
        # These ports are hardcoded in the test configuration
        port = get_unused_localhost_port()
        usock.close()
        return port

    DARWIN = True if sys.platform.startswith('darwin') else False
    BSD = True if 'bsd' in sys.platform else False

    if DARWIN and port in _RUNTESTS_PORTS:
        port = get_unused_localhost_port()
        usock.close()
        return port

    _RUNTESTS_PORTS[port] = usock

    if DARWIN or BSD:
        usock.close()

    return port


def close_open_sockets(sockets_dict):
    for port in list(sockets_dict):
        sock = sockets_dict.pop(port)
        sock.close()


atexit.register(close_open_sockets, _RUNTESTS_PORTS)


SALT_LOG_PORT = get_unused_localhost_port()


def run_tests(*test_cases, **kwargs):
    '''
    Run integration tests for the chosen test cases.

    Function uses optparse to set up test environment
    '''

    needs_daemon = kwargs.pop('needs_daemon', True)
    if kwargs:
        raise RuntimeError(
            'The \'run_tests\' function only accepts \'needs_daemon\' as a '
            'keyword argument'
        )

    class TestcaseParser(SaltTestcaseParser):
        def setup_additional_options(self):
            self.add_option(
                '--sysinfo',
                default=False,
                action='store_true',
                help='Print some system information.'
            )
            self.output_options_group.add_option(
                '--no-colors',
                '--no-colours',
                default=False,
                action='store_true',
                help='Disable colour printing.'
            )
            if needs_daemon:
                self.add_option(
                    '--transport',
                    default='zeromq',
                    choices=('zeromq', 'raet', 'tcp'),
                    help=('Select which transport to run the integration tests with, '
                          'zeromq, raet, or tcp. Default: %default')
                )

        def validate_options(self):
            SaltTestcaseParser.validate_options(self)
            # Transplant configuration
            transport = None
            if needs_daemon:
                transport = self.options.transport
            TestDaemon.transplant_configs(transport=transport)

        def run_testcase(self, testcase, needs_daemon=True):  # pylint: disable=W0221
            if needs_daemon:
                print(' * Setting up Salt daemons to execute tests')
                with TestDaemon(self):
                    return SaltTestcaseParser.run_testcase(self, testcase)
            return SaltTestcaseParser.run_testcase(self, testcase)

    parser = TestcaseParser()
    parser.parse_args()
    for case in test_cases:
        if parser.run_testcase(case, needs_daemon=needs_daemon) is False:
            parser.finalize(1)
    parser.finalize(0)


class ThreadingMixIn(socketserver.ThreadingMixIn):
    daemon_threads = True


class ThreadedSocketServer(ThreadingMixIn, socketserver.TCPServer):

    allow_reuse_address = True

    def server_activate(self):
        self.shutting_down = threading.Event()
        socketserver.TCPServer.server_activate(self)
        #super(ThreadedSocketServer, self).server_activate()

    def server_close(self):
        if hasattr(self, 'shutting_down'):
            self.shutting_down.set()
        socketserver.TCPServer.server_close(self)
        #super(ThreadedSocketServer, self).server_close()


class SocketServerRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        unpacker = msgpack.Unpacker(encoding='utf-8')
        while not self.server.shutting_down.is_set():
            try:
                wire_bytes = self.request.recv(1024)
                if not wire_bytes:
                    break
                unpacker.feed(wire_bytes)
                for record_dict in unpacker:
                    record = logging.makeLogRecord(record_dict)
                    logger = logging.getLogger(record.name)
                    logger.handle(record)
            except (EOFError, KeyboardInterrupt, SystemExit):
                break
            except socket.error as exc:
                try:
                    if exc.errno == errno.WSAECONNRESET:
                        # Connection reset on windows
                        break
                except AttributeError:
                    # We're not on windows
                    pass
                log.exception(exc)
            except Exception as exc:
                log.exception(exc)


class ScriptPathMixin(object):

    def get_script_path(self, script_name):
        '''
        Return the path to a testing runtime script
        '''
        if not os.path.isdir(TMP_SCRIPT_DIR):
            os.makedirs(TMP_SCRIPT_DIR)

        script_path = os.path.join(TMP_SCRIPT_DIR,
                                   'cli_{0}.py'.format(script_name.replace('-', '_')))

        if not os.path.isfile(script_path):
            log.info('Generating {0}'.format(script_path))

            # Late import
            import salt.utils

            with salt.utils.fopen(script_path, 'w') as sfh:
                script_template = SCRIPT_TEMPLATES.get(script_name, None)
                if script_template is None:
                    script_template = SCRIPT_TEMPLATES.get('common', None)
                if script_template is None:
                    raise RuntimeError(
                        '{0} does not know how to handle the {1} script'.format(
                            self.__class__.__name__,
                            script_name
                        )
                    )
                sfh.write(
                    '#!{0}\n\n'.format(sys.executable) +
                    'import sys\n' +
                    'CODE_DIR="{0}"\n'.format(CODE_DIR) +
                    'if CODE_DIR not in sys.path:\n' +
                    '    sys.path.insert(0, CODE_DIR)\n\n' +
                    '\n'.join(script_template).format(script_name.replace('salt-', ''))
                )
            fst = os.stat(script_path)
            os.chmod(script_path, fst.st_mode | stat.S_IEXEC)

        log.info('Returning script path %r', script_path)
        return script_path


class SaltScriptBase(ScriptPathMixin):
    '''
    Base class for Salt CLI scripts
    '''

    cli_script_name = None

    def __init__(self,
                 config,
                 config_dir,
                 bin_dir_path,
                 io_loop=None):
        self.config = config
        self.config_dir = config_dir
        self.bin_dir_path = bin_dir_path
        self._io_loop = io_loop

    @property
    def io_loop(self):
        '''
        Return an IOLoop
        '''
        if self._io_loop is None:
            self._io_loop = ioloop.IOLoop.current()
        return self._io_loop

    def get_script_args(self):  # pylint: disable=no-self-use
        '''
        Returns any additional arguments to pass to the CLI script
        '''
        return []


class SaltDaemonScriptBase(SaltScriptBase, ShellTestCase):
    '''
    Base class for Salt Daemon CLI scripts
    '''

    def __init__(self, *args, **kwargs):
        super(SaltDaemonScriptBase, self).__init__(*args, **kwargs)
        self._running = multiprocessing.Event()
        self._connectable = multiprocessing.Event()
        self._process = None

    def is_alive(self):
        '''
        Returns true if the process is alive
        '''
        return self._running.is_set()

    def get_check_ports(self):  # pylint: disable=no-self-use
        '''
        Return a list of ports to check against to ensure the daemon is running
        '''
        return []

    def start(self):
        '''
        Start the daemon subprocess
        '''
        self._process = salt.utils.process.SignalHandlingMultiprocessingProcess(
            target=self._start, args=(self._running,))
        self._process.start()
        self._running.set()
        return True

    def _start(self, running_event):
        '''
        The actual, coroutine aware, start method
        '''
        log.info('Starting %s %s DAEMON', self.display_name, self.__class__.__name__)
        proc_args = [
            self.get_script_path(self.cli_script_name),
            '-c',
            self.config_dir,
        ] + self.get_script_args()
        if salt.utils.is_windows():
            # Windows need the python executable to come first
            proc_args.insert(0, sys.executable)
        log.info('Running \'%s\' from %s...', ' '.join(proc_args), self.__class__.__name__)

        try:
            terminal = NonBlockingPopen(proc_args, cwd=CODE_DIR)

            while running_event.is_set() and terminal.poll() is None:
                # We're not actually interested in processing the output, just consume it
                if terminal.stdout is not None:
                    terminal.recv()
                if terminal.stderr is not None:
                    terminal.recv_err()
                time.sleep(0.125)
        except (SystemExit, KeyboardInterrupt):
            pass

        terminate_process_pid(terminal.pid)
        terminal.communicate()

    def terminate(self):
        '''
        Terminate the started daemon
        '''
        log.info('Terminating %s %s DAEMON', self.display_name, self.__class__.__name__)
        self._running.clear()
        self._connectable.clear()
        time.sleep(0.0125)
        terminate_process_pid(self._process.pid)
        self._process.join()
        log.info('%s %s DAEMON terminated', self.display_name, self.__class__.__name__)

    def wait_until_running(self, timeout=None):
        '''
        Blocking call to wait for the daemon to start listening
        '''
        if self._connectable.is_set():
            return True
        try:
            return self.io_loop.run_sync(self._wait_until_running, timeout=timeout)
        except ioloop.TimeoutError:
            return False

    @gen.coroutine
    def _wait_until_running(self):
        '''
        The actual, coroutine aware, call to wait for the daemon to start listening
        '''
        check_ports = self.get_check_ports()
        log.debug(
            '%s is checking the following ports to assure running status: %s',
            self.__class__.__name__,
            check_ports
        )
        while self._running.is_set():
            if not check_ports:
                self._connectable.set()
                break
            for port in set(check_ports):
                if isinstance(port, int):
                    log.trace('Checking connectable status on port: %s', port)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    conn = sock.connect_ex(('localhost', port))
                    if conn == 0:
                        log.debug('Port %s is connectable!', port)
                        check_ports.remove(port)
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                            sock.close()
                        except socket.error as exc:
                            if not sys.platform.startswith('darwin'):
                                raise
                            try:
                                if exc.errno != errno.ENOTCONN:
                                    raise
                            except AttributeError:
                                # This is not macOS !?
                                pass
                    del sock
                elif isinstance(port, str):
                    joined = self.run_run('manage.joined', config_dir=self.config_dir)
                    joined = [x.lstrip('- ') for x in joined]
                    if port in joined:
                        check_ports.remove(port)
            yield gen.sleep(0.125)
        # A final sleep to allow the ioloop to do other things
        yield gen.sleep(0.125)
        log.info('All ports checked. %s running!', self.cli_script_name)
        raise gen.Return(self._connectable.is_set())


class SaltMinion(SaltDaemonScriptBase):
    '''
    Class which runs the salt-minion daemon
    '''

    cli_script_name = 'salt-minion'

    def get_script_args(self):
        script_args = ['-l', 'quiet']
        if salt.utils.is_windows() is False:
            script_args.append('--disable-keepalive')
        return script_args

    def get_check_ports(self):
        if salt.utils.is_windows():
            return set([self.config['tcp_pub_port'],
                        self.config['tcp_pull_port']])
        else:
            return set([self.config['id']])


class SaltMaster(SaltDaemonScriptBase):
    '''
    Class which runs the salt-minion daemon
    '''

    cli_script_name = 'salt-master'

    def get_check_ports(self):
        #return set([self.config['runtests_conn_check_port']])
        return set([self.config['ret_port'],
                    self.config['publish_port']])
        # Disabled along with Pytest config until fixed.
#                    self.config['runtests_conn_check_port']])

    def get_script_args(self):
        #return ['-l', 'debug']
        return ['-l', 'quiet']


class SaltSyndic(SaltDaemonScriptBase):
    '''
    Class which runs the salt-syndic daemon
    '''

    cli_script_name = 'salt-syndic'

    def get_script_args(self):
        #return ['-l', 'debug']
        return ['-l', 'quiet']

    def get_check_ports(self):
        return set()


class TestDaemon(object):
    '''
    Set up the master and minion daemons, and run related cases
    '''
    MINIONS_CONNECT_TIMEOUT = MINIONS_SYNC_TIMEOUT = 120

    def __init__(self, parser):
        self.parser = parser
        self.colors = salt.utils.get_colors(self.parser.options.no_colors is False)
        if salt.utils.is_windows():
            # There's no shell color support on windows...
            for key in self.colors:
                self.colors[key] = ''

    def __enter__(self):
        '''
        Start a master and minion
        '''
        # Setup the multiprocessing logging queue listener
        salt_log_setup.setup_multiprocessing_logging_listener(
            self.master_opts
        )

        # Set up PATH to mockbin
        self._enter_mockbin()

        if self.parser.options.transport == 'zeromq':
            self.start_zeromq_daemons()
        elif self.parser.options.transport == 'raet':
            self.start_raet_daemons()
        elif self.parser.options.transport == 'tcp':
            self.start_tcp_daemons()

        self.minion_targets = set(['minion', 'sub_minion'])
        self.pre_setup_minions()
        self.setup_minions()

        if getattr(self.parser.options, 'ssh', False):
            self.prep_ssh()

        if self.parser.options.sysinfo:
            try:
                print_header(
                    '~~~~~~~ Versions Report ', inline=True,
                    width=getattr(self.parser.options, 'output_columns', PNUM)
                )
            except TypeError:
                print_header('~~~~~~~ Versions Report ', inline=True)

            print('\n'.join(salt.version.versions_report()))

            try:
                print_header(
                    '~~~~~~~ Minion Grains Information ', inline=True,
                    width=getattr(self.parser.options, 'output_columns', PNUM)
                )
            except TypeError:
                print_header('~~~~~~~ Minion Grains Information ', inline=True)

            grains = self.client.cmd('minion', 'grains.items')

            minion_opts = self.minion_opts.copy()
            minion_opts['color'] = self.parser.options.no_colors is False
            salt.output.display_output(grains, 'grains', minion_opts)

        try:
            print_header(
                '=', sep='=', inline=True,
                width=getattr(self.parser.options, 'output_columns', PNUM)
            )
        except TypeError:
            print_header('', sep='=', inline=True)

        try:
            return self
        finally:
            self.post_setup_minions()

    def start_daemon(self, cls, opts, start_fun):
        def start(cls, opts, start_fun):
            salt.utils.appendproctitle('{0}-{1}'.format(self.__class__.__name__, cls.__name__))
            daemon = cls(opts)
            getattr(daemon, start_fun)()
        process = multiprocessing.Process(target=start,
                                          args=(cls, opts, start_fun))
        process.start()
        return process

    def start_zeromq_daemons(self):
        '''
        Fire up the daemons used for zeromq tests
        '''
        self.log_server = ThreadedSocketServer(('localhost', SALT_LOG_PORT), SocketServerRequestHandler)
        self.log_server_process = threading.Thread(target=self.log_server.serve_forever)
        self.log_server_process.daemon = True
        self.log_server_process.start()

        self.master_process = SaltMaster(self.master_opts, TMP_CONF_DIR, SCRIPT_DIR)
        self.master_process.display_name = 'salt-master'
        self.minion_process = SaltMinion(self.minion_opts, TMP_CONF_DIR, SCRIPT_DIR)
        self.minion_process.display_name = 'salt-minion'
        self.sub_minion_process = SaltMinion(self.sub_minion_opts, TMP_SUB_MINION_CONF_DIR, SCRIPT_DIR)
        self.sub_minion_process.display_name = 'sub salt-minion'
        self.smaster_process = SaltMaster(self.syndic_master_opts, TMP_SYNDIC_MASTER_CONF_DIR, SCRIPT_DIR)
        self.smaster_process.display_name = 'syndic salt-master'
        self.syndic_process = SaltSyndic(self.syndic_opts, TMP_SYNDIC_MINION_CONF_DIR, SCRIPT_DIR)
        self.syndic_process.display_name = 'salt-syndic'
        for process in (self.master_process, self.minion_process, self.sub_minion_process,
                        self.smaster_process, self.syndic_process):
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting {0} ... {ENDC}'.format(
                    process.display_name,
                    **self.colors
                )
            )
            sys.stdout.flush()
            process.start()
            process.wait_until_running(timeout=60)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting {0} ... STARTED!\n{ENDC}'.format(
                    process.display_name,
                    **self.colors
                )
            )
            sys.stdout.flush()

    def start_raet_daemons(self):
        '''
        Fire up the raet daemons!
        '''
        import salt.daemons.flo
        self.master_process = self.start_daemon(salt.daemons.flo.IofloMaster,
                                                self.master_opts,
                                                'start')

        self.minion_process = self.start_daemon(salt.daemons.flo.IofloMinion,
                                                self.minion_opts,
                                                'tune_in')

        self.sub_minion_process = self.start_daemon(salt.daemons.flo.IofloMinion,
                                                    self.sub_minion_opts,
                                                    'tune_in')
        # Wait for the daemons to all spin up
        time.sleep(5)

        # self.smaster_process = self.start_daemon(salt.daemons.flo.IofloMaster,
        #                                            self.syndic_master_opts,
        #                                            'start')

        # no raet syndic daemon yet

    start_tcp_daemons = start_zeromq_daemons

    def prep_ssh(self):
        '''
        Generate keys and start an ssh daemon on an alternate port
        '''
        sys.stdout.write(
            ' * {LIGHT_GREEN}Starting {0} ... {ENDC}'.format(
                'SSH server',
                **self.colors
            )
        )
        keygen = salt.utils.which('ssh-keygen')
        sshd = salt.utils.which('sshd')

        if not (keygen and sshd):
            print('WARNING: Could not initialize SSH subsystem. Tests for salt-ssh may break!')
            return
        if not os.path.exists(TMP_CONF_DIR):
            os.makedirs(TMP_CONF_DIR)

        # Generate client key
        pub_key_test_file = os.path.join(TMP_CONF_DIR, 'key_test.pub')
        priv_key_test_file = os.path.join(TMP_CONF_DIR, 'key_test')
        if os.path.exists(pub_key_test_file):
            os.remove(pub_key_test_file)
        if os.path.exists(priv_key_test_file):
            os.remove(priv_key_test_file)
        keygen_process = subprocess.Popen(
            [keygen, '-t',
                     'ecdsa',
                     '-b',
                     '521',
                     '-C',
                     '"$(whoami)@$(hostname)-$(date -I)"',
                     '-f',
                     'key_test',
                     '-P',
                     ''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=TMP_CONF_DIR
        )
        _, keygen_err = keygen_process.communicate()
        if keygen_err:
            print('ssh-keygen had errors: {0}'.format(salt.utils.to_str(keygen_err)))
        sshd_config_path = os.path.join(FILES, 'conf/_ssh/sshd_config')
        shutil.copy(sshd_config_path, TMP_CONF_DIR)
        auth_key_file = os.path.join(TMP_CONF_DIR, 'key_test.pub')

        # Generate server key
        server_key_dir = os.path.join(TMP_CONF_DIR, 'server')
        if not os.path.exists(server_key_dir):
            os.makedirs(server_key_dir)
        server_dsa_priv_key_file = os.path.join(server_key_dir, 'ssh_host_dsa_key')
        server_dsa_pub_key_file = os.path.join(server_key_dir, 'ssh_host_dsa_key.pub')
        server_ecdsa_priv_key_file = os.path.join(server_key_dir, 'ssh_host_ecdsa_key')
        server_ecdsa_pub_key_file = os.path.join(server_key_dir, 'ssh_host_ecdsa_key.pub')
        server_ed25519_priv_key_file = os.path.join(server_key_dir, 'ssh_host_ed25519_key')
        server_ed25519_pub_key_file = os.path.join(server_key_dir, 'ssh_host.ed25519_key.pub')

        for server_key_file in (server_dsa_priv_key_file,
                                server_dsa_pub_key_file,
                                server_ecdsa_priv_key_file,
                                server_ecdsa_pub_key_file,
                                server_ed25519_priv_key_file,
                                server_ed25519_pub_key_file):
            if os.path.exists(server_key_file):
                os.remove(server_key_file)

        keygen_process_dsa = subprocess.Popen(
            [keygen, '-t',
                     'dsa',
                     '-b',
                     '1024',
                     '-C',
                     '"$(whoami)@$(hostname)-$(date -I)"',
                     '-f',
                     'ssh_host_dsa_key',
                     '-P',
                     ''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=server_key_dir
        )
        _, keygen_dsa_err = keygen_process_dsa.communicate()
        if keygen_dsa_err:
            print('ssh-keygen had errors: {0}'.format(salt.utils.to_str(keygen_dsa_err)))

        keygen_process_ecdsa = subprocess.Popen(
            [keygen, '-t',
                     'ecdsa',
                     '-b',
                     '521',
                     '-C',
                     '"$(whoami)@$(hostname)-$(date -I)"',
                     '-f',
                     'ssh_host_ecdsa_key',
                     '-P',
                     ''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=server_key_dir
        )
        _, keygen_escda_err = keygen_process_ecdsa.communicate()
        if keygen_escda_err:
            print('ssh-keygen had errors: {0}'.format(salt.utils.to_str(keygen_escda_err)))

        keygen_process_ed25519 = subprocess.Popen(
            [keygen, '-t',
                     'ed25519',
                     '-b',
                     '521',
                     '-C',
                     '"$(whoami)@$(hostname)-$(date -I)"',
                     '-f',
                     'ssh_host_ed25519_key',
                     '-P',
                     ''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=server_key_dir
        )
        _, keygen_ed25519_err = keygen_process_ed25519.communicate()
        if keygen_ed25519_err:
            print('ssh-keygen had errors: {0}'.format(salt.utils.to_str(keygen_ed25519_err)))

        with salt.utils.fopen(os.path.join(TMP_CONF_DIR, 'sshd_config'), 'a') as ssh_config:
            ssh_config.write('AuthorizedKeysFile {0}\n'.format(auth_key_file))
            if not keygen_dsa_err:
                ssh_config.write('HostKey {0}\n'.format(server_dsa_priv_key_file))
            if not keygen_escda_err:
                ssh_config.write('HostKey {0}\n'.format(server_ecdsa_priv_key_file))
            if not keygen_ed25519_err:
                ssh_config.write('HostKey {0}\n'.format(server_ed25519_priv_key_file))

        self.sshd_pidfile = os.path.join(TMP_CONF_DIR, 'sshd.pid')
        self.sshd_process = subprocess.Popen(
            [sshd, '-f', 'sshd_config', '-oPidFile={0}'.format(self.sshd_pidfile)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=TMP_CONF_DIR
        )
        _, sshd_err = self.sshd_process.communicate()
        if sshd_err:
            print('sshd had errors on startup: {0}'.format(salt.utils.to_str(sshd_err)))
        else:
            os.environ['SSH_DAEMON_RUNNING'] = 'True'
        roster_path = os.path.join(FILES, 'conf/_ssh/roster')
        shutil.copy(roster_path, TMP_CONF_DIR)
        if salt.utils.is_windows():
            with salt.utils.fopen(os.path.join(TMP_CONF_DIR, 'roster'), 'a') as roster:
                roster.write('  user: {0}\n'.format(win32api.GetUserName()))
                roster.write('  priv: {0}/{1}'.format(TMP_CONF_DIR, 'key_test'))
        else:
            with salt.utils.fopen(os.path.join(TMP_CONF_DIR, 'roster'), 'a') as roster:
                roster.write('  user: {0}\n'.format(pwd.getpwuid(os.getuid()).pw_name))
                roster.write('  priv: {0}/{1}'.format(TMP_CONF_DIR, 'key_test'))
        sys.stdout.write(
            ' {LIGHT_GREEN}STARTED!\n{ENDC}'.format(
                **self.colors
            )
        )

    @classmethod
    def config(cls, role):
        '''
        Return a configuration for a master/minion/syndic.

        Currently these roles are:
            * master
            * minion
            * syndic
            * syndic_master
            * sub_minion
        '''
        return RUNTIME_CONFIGS[role]

    @classmethod
    def config_location(cls):
        return TMP_CONF_DIR

    @property
    def client(self):
        '''
        Return a local client which will be used for example to ping and sync
        the test minions.

        This client is defined as a class attribute because its creation needs
        to be deferred to a latter stage. If created it on `__enter__` like it
        previously was, it would not receive the master events.
        '''
        if 'runtime_client' not in RUNTIME_CONFIGS:
            RUNTIME_CONFIGS['runtime_client'] = salt.client.get_local_client(
                mopts=self.master_opts
            )
        return RUNTIME_CONFIGS['runtime_client']

    @classmethod
    def transplant_configs(cls, transport='zeromq'):
        if os.path.isdir(TMP_CONF_DIR):
            shutil.rmtree(TMP_CONF_DIR)
        os.makedirs(TMP_CONF_DIR)
        os.makedirs(TMP_SUB_MINION_CONF_DIR)
        os.makedirs(TMP_SYNDIC_MASTER_CONF_DIR)
        os.makedirs(TMP_SYNDIC_MINION_CONF_DIR)
        print(' * Transplanting configuration files to \'{0}\''.format(TMP_CONF_DIR))
        if salt.utils.is_windows():
            running_tests_user = win32api.GetUserName()
        else:
            running_tests_user = pwd.getpwuid(os.getuid()).pw_name

        tests_known_hosts_file = os.path.join(TMP_CONF_DIR, 'salt_ssh_known_hosts')
        with salt.utils.fopen(tests_known_hosts_file, 'w') as known_hosts:
            known_hosts.write('')

        # This master connects to syndic_master via a syndic
        master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'master'))
        master_opts['known_hosts_file'] = tests_known_hosts_file
        master_opts['cachedir'] = os.path.join(TMP, 'rootdir', 'cache')
        master_opts['user'] = running_tests_user
        master_opts['config_dir'] = TMP_CONF_DIR
        master_opts['root_dir'] = os.path.join(TMP, 'rootdir')
        master_opts['pki_dir'] = os.path.join(TMP, 'rootdir', 'pki', 'master')

        # This is the syndic for master
        # Let's start with a copy of the syndic master configuration
        syndic_opts = copy.deepcopy(master_opts)
        # Let's update with the syndic configuration
        syndic_opts.update(salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic')))
        syndic_opts['cachedir'] = os.path.join(TMP, 'rootdir', 'cache')
        syndic_opts['config_dir'] = TMP_SYNDIC_MINION_CONF_DIR

        # This minion connects to master
        minion_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'minion'))
        minion_opts['cachedir'] = os.path.join(TMP, 'rootdir', 'cache')
        minion_opts['user'] = running_tests_user
        minion_opts['config_dir'] = TMP_CONF_DIR
        minion_opts['root_dir'] = os.path.join(TMP, 'rootdir')
        minion_opts['pki_dir'] = os.path.join(TMP, 'rootdir', 'pki')
        minion_opts['hosts.file'] = os.path.join(TMP, 'rootdir', 'hosts')
        minion_opts['aliases.file'] = os.path.join(TMP, 'rootdir', 'aliases')

        # This sub_minion also connects to master
        sub_minion_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'sub_minion'))
        sub_minion_opts['cachedir'] = os.path.join(TMP, 'rootdir-sub-minion', 'cache')
        sub_minion_opts['user'] = running_tests_user
        sub_minion_opts['config_dir'] = TMP_SUB_MINION_CONF_DIR
        sub_minion_opts['root_dir'] = os.path.join(TMP, 'rootdir-sub-minion')
        sub_minion_opts['pki_dir'] = os.path.join(TMP, 'rootdir-sub-minion', 'pki', 'minion')
        sub_minion_opts['hosts.file'] = os.path.join(TMP, 'rootdir', 'hosts')
        sub_minion_opts['aliases.file'] = os.path.join(TMP, 'rootdir', 'aliases')

        # This is the master of masters
        syndic_master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic_master'))
        syndic_master_opts['cachedir'] = os.path.join(TMP, 'rootdir-syndic-master', 'cache')
        syndic_master_opts['user'] = running_tests_user
        syndic_master_opts['config_dir'] = TMP_SYNDIC_MASTER_CONF_DIR
        syndic_master_opts['root_dir'] = os.path.join(TMP, 'rootdir-syndic-master')
        syndic_master_opts['pki_dir'] = os.path.join(TMP, 'rootdir-syndic-master', 'pki', 'master')

        if transport == 'raet':
            master_opts['transport'] = 'raet'
            master_opts['raet_port'] = 64506
            minion_opts['transport'] = 'raet'
            minion_opts['raet_port'] = 64510
            sub_minion_opts['transport'] = 'raet'
            sub_minion_opts['raet_port'] = 64520
            # syndic_master_opts['transport'] = 'raet'

        if transport == 'tcp':
            master_opts['transport'] = 'tcp'
            minion_opts['transport'] = 'tcp'
            sub_minion_opts['transport'] = 'tcp'
            syndic_master_opts['transport'] = 'tcp'

        # Set up config options that require internal data
        master_opts['pillar_roots'] = syndic_master_opts['pillar_roots'] = {
            'base': [os.path.join(FILES, 'pillar', 'base')]
        }
        master_opts['file_roots'] = syndic_master_opts['file_roots'] = {
            'base': [
                os.path.join(FILES, 'file', 'base'),
                # Let's support runtime created files that can be used like:
                #   salt://my-temp-file.txt
                TMP_STATE_TREE
            ],
            # Alternate root to test __env__ choices
            'prod': [
                os.path.join(FILES, 'file', 'prod'),
                TMP_PRODENV_STATE_TREE
            ]
        }
        master_opts.setdefault('reactor', []).append(
            {
                'salt/minion/*/start': [
                    os.path.join(FILES, 'reactor-sync-minion.sls')
                ],
            }
        )
        for opts_dict in (master_opts, syndic_master_opts):
            if 'ext_pillar' not in opts_dict:
                opts_dict['ext_pillar'] = []
            if salt.utils.is_windows():
                opts_dict['ext_pillar'].append(
                    {'cmd_yaml': 'type {0}'.format(os.path.join(FILES, 'ext.yaml'))})
            else:
                opts_dict['ext_pillar'].append(
                    {'cmd_yaml': 'cat {0}'.format(os.path.join(FILES, 'ext.yaml'))})

        for opts_dict in (master_opts, syndic_master_opts):
            # We need to copy the extension modules into the new master root_dir or
            # it will be prefixed by it
            new_extension_modules_path = os.path.join(opts_dict['root_dir'], 'extension_modules')
            if not os.path.exists(new_extension_modules_path):
                shutil.copytree(
                    os.path.join(
                        INTEGRATION_TEST_DIR, 'files', 'extension_modules'
                    ),
                    new_extension_modules_path
                )
            opts_dict['extension_modules'] = os.path.join(opts_dict['root_dir'], 'extension_modules')

        # Point the config values to the correct temporary paths
        for name in ('hosts', 'aliases'):
            optname = '{0}.file'.format(name)
            optname_path = os.path.join(TMP, name)
            master_opts[optname] = optname_path
            minion_opts[optname] = optname_path
            sub_minion_opts[optname] = optname_path
            syndic_opts[optname] = optname_path
            syndic_master_opts[optname] = optname_path

        for conf in (master_opts, minion_opts, sub_minion_opts, syndic_opts, syndic_master_opts):
            if 'log_handlers_dirs' not in conf:
                conf['log_handlers_dirs'] = []
            conf['log_handlers_dirs'].insert(0, LOG_HANDLERS_DIR)
            conf['runtests_log_port'] = SALT_LOG_PORT

        # ----- Transcribe Configuration ---------------------------------------------------------------------------->
        for entry in os.listdir(CONF_DIR):
            if entry in ('master', 'minion', 'sub_minion', 'syndic', 'syndic_master'):
                # These have runtime computed values and will be handled
                # differently
                continue
            entry_path = os.path.join(CONF_DIR, entry)
            if os.path.isfile(entry_path):
                shutil.copy(
                    entry_path,
                    os.path.join(TMP_CONF_DIR, entry)
                )
            elif os.path.isdir(entry_path):
                shutil.copytree(
                    entry_path,
                    os.path.join(TMP_CONF_DIR, entry)
                )

        for entry in ('master', 'minion', 'sub_minion', 'syndic', 'syndic_master'):
            computed_config = copy.deepcopy(locals()['{0}_opts'.format(entry)])
            with salt.utils.fopen(os.path.join(TMP_CONF_DIR, entry), 'w') as fp_:
                fp_.write(yaml.dump(computed_config, default_flow_style=False))
        sub_minion_computed_config = copy.deepcopy(sub_minion_opts)
        salt.utils.fopen(os.path.join(TMP_SUB_MINION_CONF_DIR, 'minion'), 'w').write(
            yaml.dump(sub_minion_computed_config, default_flow_style=False)
        )
        shutil.copyfile(os.path.join(TMP_CONF_DIR, 'master'), os.path.join(TMP_SUB_MINION_CONF_DIR, 'master'))

        syndic_master_computed_config = copy.deepcopy(syndic_master_opts)
        salt.utils.fopen(os.path.join(TMP_SYNDIC_MASTER_CONF_DIR, 'master'), 'w').write(
            yaml.dump(syndic_master_computed_config, default_flow_style=False)
        )
        syndic_computed_config = copy.deepcopy(syndic_opts)
        salt.utils.fopen(os.path.join(TMP_SYNDIC_MINION_CONF_DIR, 'minion'), 'w').write(
            yaml.dump(syndic_computed_config, default_flow_style=False)
        )
        shutil.copyfile(os.path.join(TMP_CONF_DIR, 'master'), os.path.join(TMP_SYNDIC_MINION_CONF_DIR, 'master'))
        # <---- Transcribe Configuration -----------------------------------------------------------------------------

        # ----- Verify Environment ---------------------------------------------------------------------------------->
        master_opts = salt.config.master_config(os.path.join(TMP_CONF_DIR, 'master'))
        minion_opts = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'minion'))
        syndic_opts = salt.config.syndic_config(
            os.path.join(TMP_SYNDIC_MINION_CONF_DIR, 'master'),
            os.path.join(TMP_SYNDIC_MINION_CONF_DIR, 'minion'),
        )
        sub_minion_opts = salt.config.minion_config(os.path.join(TMP_SUB_MINION_CONF_DIR, 'minion'))
        syndic_master_opts = salt.config.master_config(os.path.join(TMP_SYNDIC_MASTER_CONF_DIR, 'master'))

        RUNTIME_CONFIGS['master'] = freeze(master_opts)
        RUNTIME_CONFIGS['minion'] = freeze(minion_opts)
        RUNTIME_CONFIGS['syndic'] = freeze(syndic_opts)
        RUNTIME_CONFIGS['sub_minion'] = freeze(sub_minion_opts)
        RUNTIME_CONFIGS['syndic_master'] = freeze(syndic_master_opts)

        verify_env([os.path.join(master_opts['pki_dir'], 'minions'),
                    os.path.join(master_opts['pki_dir'], 'minions_pre'),
                    os.path.join(master_opts['pki_dir'], 'minions_rejected'),
                    os.path.join(master_opts['pki_dir'], 'minions_denied'),
                    os.path.join(master_opts['cachedir'], 'jobs'),
                    os.path.join(master_opts['cachedir'], 'raet'),
                    os.path.join(master_opts['root_dir'], 'cache', 'tokens'),
                    os.path.join(syndic_master_opts['pki_dir'], 'minions'),
                    os.path.join(syndic_master_opts['pki_dir'], 'minions_pre'),
                    os.path.join(syndic_master_opts['pki_dir'], 'minions_rejected'),
                    os.path.join(syndic_master_opts['cachedir'], 'jobs'),
                    os.path.join(syndic_master_opts['cachedir'], 'raet'),
                    os.path.join(syndic_master_opts['root_dir'], 'cache', 'tokens'),
                    os.path.join(master_opts['pki_dir'], 'accepted'),
                    os.path.join(master_opts['pki_dir'], 'rejected'),
                    os.path.join(master_opts['pki_dir'], 'pending'),
                    os.path.join(syndic_master_opts['pki_dir'], 'accepted'),
                    os.path.join(syndic_master_opts['pki_dir'], 'rejected'),
                    os.path.join(syndic_master_opts['pki_dir'], 'pending'),
                    os.path.join(syndic_master_opts['cachedir'], 'raet'),

                    os.path.join(minion_opts['pki_dir'], 'accepted'),
                    os.path.join(minion_opts['pki_dir'], 'rejected'),
                    os.path.join(minion_opts['pki_dir'], 'pending'),
                    os.path.join(minion_opts['cachedir'], 'raet'),
                    os.path.join(sub_minion_opts['pki_dir'], 'accepted'),
                    os.path.join(sub_minion_opts['pki_dir'], 'rejected'),
                    os.path.join(sub_minion_opts['pki_dir'], 'pending'),
                    os.path.join(sub_minion_opts['cachedir'], 'raet'),
                    os.path.dirname(master_opts['log_file']),
                    minion_opts['extension_modules'],
                    sub_minion_opts['extension_modules'],
                    sub_minion_opts['pki_dir'],
                    master_opts['sock_dir'],
                    syndic_master_opts['sock_dir'],
                    sub_minion_opts['sock_dir'],
                    minion_opts['sock_dir'],
                    TMP_STATE_TREE,
                    TMP_PRODENV_STATE_TREE,
                    TMP,
                    ],
                   running_tests_user)

        cls.master_opts = master_opts
        cls.minion_opts = minion_opts
        cls.sub_minion_opts = sub_minion_opts
        cls.syndic_opts = syndic_opts
        cls.syndic_master_opts = syndic_master_opts
        # <---- Verify Environment -----------------------------------------------------------------------------------

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        self.sub_minion_process.terminate()
        self.minion_process.terminate()
        self.master_process.terminate()
        try:
            self.syndic_process.terminate()
        except AttributeError:
            pass
        try:
            self.smaster_process.terminate()
        except AttributeError:
            pass
        #salt.utils.process.clean_proc(self.sub_minion_process, wait_for_kill=50)
        #self.sub_minion_process.join()
        #salt.utils.process.clean_proc(self.minion_process, wait_for_kill=50)
        #self.minion_process.join()
        #salt.utils.process.clean_proc(self.master_process, wait_for_kill=50)
        #self.master_process.join()
        #try:
        #    salt.utils.process.clean_proc(self.syndic_process, wait_for_kill=50)
        #    self.syndic_process.join()
        #except AttributeError:
        #    pass
        #try:
        #    salt.utils.process.clean_proc(self.smaster_process, wait_for_kill=50)
        #    self.smaster_process.join()
        #except AttributeError:
        #    pass
        self.log_server.server_close()
        self.log_server.shutdown()
        self._exit_mockbin()
        self._exit_ssh()
        self.log_server_process.join()
        # Shutdown the multiprocessing logging queue listener
        salt_log_setup.shutdown_multiprocessing_logging()
        salt_log_setup.shutdown_multiprocessing_logging_listener(daemonizing=True)

    def pre_setup_minions(self):
        '''
        Subclass this method for additional minion setups.
        '''

    def setup_minions(self):
        '''
        Minions setup routines
        '''

    def post_setup_minions(self):
        '''
        Subclass this method to execute code after the minions have been setup
        '''

    def _enter_mockbin(self):
        path = os.environ.get('PATH', '')
        path_items = path.split(os.pathsep)
        if MOCKBIN not in path_items:
            path_items.insert(0, MOCKBIN)
        os.environ['PATH'] = os.pathsep.join(path_items)

    def _exit_ssh(self):
        if hasattr(self, 'sshd_process'):
            try:
                self.sshd_process.kill()
            except OSError as exc:
                if exc.errno != 3:
                    raise
            with salt.utils.fopen(self.sshd_pidfile) as fhr:
                try:
                    os.kill(int(fhr.read()), signal.SIGKILL)
                except OSError as exc:
                    if exc.errno != 3:
                        raise

    def _exit_mockbin(self):
        path = os.environ.get('PATH', '')
        path_items = path.split(os.pathsep)
        try:
            path_items.remove(MOCKBIN)
        except ValueError:
            pass
        os.environ['PATH'] = os.pathsep.join(path_items)

    @classmethod
    def clean(cls):
        '''
        Clean out the tmp files
        '''
        def remove_readonly(func, path, excinfo):
            os.chmod(path, stat.S_IWRITE)
            func(path)

        for dirname in (TMP, TMP_STATE_TREE, TMP_PRODENV_STATE_TREE):
            if os.path.isdir(dirname):
                shutil.rmtree(dirname, onerror=remove_readonly)

    def wait_for_jid(self, targets, jid, timeout=120):
        time.sleep(1)  # Allow some time for minions to accept jobs
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        job_finished = False
        while now <= expire:
            running = self.__client_job_running(targets, jid)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            if not running and job_finished is False:
                # Let's not have false positives and wait one more seconds
                job_finished = True
            elif not running and job_finished is True:
                return True
            elif running and job_finished is True:
                job_finished = False

            if job_finished is False:
                sys.stdout.write(
                    '   * {LIGHT_YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                        '{0}'.format(expire - now).rsplit('.', 1)[0],
                        ', '.join(running),
                        **self.colors
                    )
                )
                sys.stdout.flush()
            time.sleep(1)
            now = datetime.now()
        else:  # pylint: disable=W0120
            sys.stdout.write(
                '\n {LIGHT_RED}*{ENDC} ERROR: Failed to get information '
                'back\n'.format(**self.colors)
            )
            sys.stdout.flush()
        return False

    def __client_job_running(self, targets, jid):
        running = self.client.cmd(
            list(targets), 'saltutil.running', expr_form='list'
        )
        return [
            k for (k, v) in six.iteritems(running) if v and v[0]['jid'] == jid
        ]

    def wait_for_minion_connections(self, targets, timeout):
        salt.utils.appendproctitle('WaitForMinionConnections')
        sys.stdout.write(
            ' {LIGHT_BLUE}*{ENDC} Waiting at most {0} for minions({1}) to '
            'connect back\n'.format(
                (timeout > 60 and
                 timedelta(seconds=timeout) or
                 '{0} secs'.format(timeout)),
                ', '.join(targets),
                **self.colors
            )
        )
        sys.stdout.flush()
        expected_connections = set(targets)
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        while now <= expire:
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                    '{0}'.format(expire - now).rsplit('.', 1)[0],
                    ', '.join(expected_connections),
                    **self.colors
                )
            )
            sys.stdout.flush()

            try:
                responses = self.client.cmd(
                    list(expected_connections), 'test.ping', expr_form='list',
                )
            # we'll get this exception if the master process hasn't finished starting yet
            except SaltClientError:
                time.sleep(0.1)
                now = datetime.now()
                continue
            for target in responses:
                if target not in expected_connections:
                    # Someone(minion) else "listening"?
                    continue
                expected_connections.remove(target)
                sys.stdout.write(
                    '\r{0}\r'.format(
                        ' ' * getattr(self.parser.options, 'output_columns',
                                      PNUM)
                    )
                )
                sys.stdout.write(
                    '   {LIGHT_GREEN}*{ENDC} {0} connected.\n'.format(
                        target, **self.colors
                    )
                )
                sys.stdout.flush()

            if not expected_connections:
                return

            time.sleep(1)
            now = datetime.now()
        else:  # pylint: disable=W0120
            print(
                '\n {LIGHT_RED}*{ENDC} WARNING: Minions failed to connect '
                'back. Tests requiring them WILL fail'.format(**self.colors)
            )
            try:
                print_header(
                    '=', sep='=', inline=True,
                    width=getattr(self.parser.options, 'output_columns', PNUM)

                )
            except TypeError:
                print_header('=', sep='=', inline=True)
            raise SystemExit()

    def sync_minion_modules_(self, modules_kind, targets, timeout=None):
        if not timeout:
            timeout = 120
        # Let's sync all connected minions
        print(
            ' {LIGHT_BLUE}*{ENDC} Syncing minion\'s {1} '
            '(saltutil.sync_{1})'.format(
                ', '.join(targets),
                modules_kind,
                **self.colors
            )
        )
        syncing = set(targets)
        jid_info = self.client.run_job(
            list(targets), 'saltutil.sync_{0}'.format(modules_kind),
            expr_form='list',
            timeout=999999999999999,
        )

        if self.wait_for_jid(targets, jid_info['jid'], timeout) is False:
            print(
                ' {LIGHT_RED}*{ENDC} WARNING: Minions failed to sync {0}. '
                'Tests requiring these {0} WILL fail'.format(
                    modules_kind, **self.colors)
            )
            raise SystemExit()

        while syncing:
            rdata = self.client.get_full_returns(jid_info['jid'], syncing, 1)
            if rdata:
                for name, output in six.iteritems(rdata):
                    if not output['ret']:
                        # Already synced!?
                        syncing.remove(name)
                        continue

                    if isinstance(output['ret'], six.string_types):
                        # An errors has occurred
                        print(
                            ' {LIGHT_RED}*{ENDC} {0} Failed to sync {2}: '
                            '{1}'.format(
                                name, output['ret'],
                                modules_kind,
                                **self.colors)
                        )
                        return False

                    print(
                        '   {LIGHT_GREEN}*{ENDC} Synced {0} {2}: '
                        '{1}'.format(
                            name,
                            ', '.join(output['ret']),
                            modules_kind, **self.colors
                        )
                    )
                    # Synced!
                    try:
                        syncing.remove(name)
                    except KeyError:
                        print(
                            ' {LIGHT_RED}*{ENDC} {0} already synced??? '
                            '{1}'.format(name, output, **self.colors)
                        )
        return True

    def sync_minion_states(self, targets, timeout=None):
        salt.utils.appendproctitle('SyncMinionStates')
        self.sync_minion_modules_('states', targets, timeout=timeout)

    def sync_minion_modules(self, targets, timeout=None):
        salt.utils.appendproctitle('SyncMinionModules')
        self.sync_minion_modules_('modules', targets, timeout=timeout)

    def sync_minion_grains(self, targets, timeout=None):
        self.sync_minion_modules_('grains', targets, timeout=timeout)


class AdaptedConfigurationTestCaseMixIn(object):

    __slots__ = ()

    def get_config(self, config_for, from_scratch=False):
        if from_scratch:
            if config_for in ('master', 'syndic_master'):
                return salt.config.master_config(self.get_config_file_path(config_for))
            elif config_for in ('minion', 'sub_minion'):
                return salt.config.minion_config(self.get_config_file_path(config_for))
            elif config_for in ('syndic',):
                return salt.config.syndic_config(
                    self.get_config_file_path(config_for),
                    self.get_config_file_path('minion')
                )
            elif config_for == 'client_config':
                return salt.config.client_config(self.get_config_file_path('master'))

        if config_for not in RUNTIME_CONFIGS:
            if config_for in ('master', 'syndic_master'):
                RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.master_config(self.get_config_file_path(config_for))
                )
            elif config_for in ('minion', 'sub_minion'):
                RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.minion_config(self.get_config_file_path(config_for))
                )
            elif config_for in ('syndic',):
                RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.syndic_config(
                        self.get_config_file_path(config_for),
                        self.get_config_file_path('minion')
                    )
                )
            elif config_for == 'client_config':
                RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.client_config(self.get_config_file_path('master'))
                )
        return RUNTIME_CONFIGS[config_for]

    def get_config_dir(self):
        return TMP_CONF_DIR

    def get_config_file_path(self, filename):
        if filename == 'syndic_master':
            return os.path.join(TMP_SYNDIC_MASTER_CONF_DIR, 'master')
        if filename == 'syndic':
            return os.path.join(TMP_SYNDIC_MINION_CONF_DIR, 'minion')
        if filename == 'sub_minion':
            return os.path.join(TMP_SUB_MINION_CONF_DIR, 'minion')
        return os.path.join(TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        '''
        Return the options used for the master
        '''
        return self.get_config('master')


class SaltMinionEventAssertsMixIn(object):
    '''
    Asserts to verify that a given event was seen
    '''

    def __new__(cls, *args, **kwargs):
        # We have to cross-call to re-gen a config
        cls.q = multiprocessing.Queue()
        cls.fetch_proc = multiprocessing.Process(target=cls._fetch, args=(cls.q,))
        cls.fetch_proc.start()
        return object.__new__(cls)

    @staticmethod
    def _fetch(q):
        '''
        Collect events and store them
        '''
        def _clean_queue():
            print('Cleaning queue!')
            while not q.empty():
                queue_item = q.get()
                queue_item.task_done()

        atexit.register(_clean_queue)
        a_config = AdaptedConfigurationTestCaseMixIn()
        event = salt.utils.event.get_event('minion', sock_dir=a_config.get_config('minion')['sock_dir'], opts=a_config.get_config('minion'))
        while True:
            try:
                events = event.get_event(full=False)
            except Exception:
                # This is broad but we'll see all kinds of issues right now
                # if we drop the proc out from under the socket while we're reading
                pass
            q.put(events)

    def assertMinionEventFired(self, tag):
        #TODO
        raise salt.exceptions.NotImplemented('assertMinionEventFired() not implemented')

    def assertMinionEventReceived(self, desired_event):
        queue_wait = 5  # 2.5s
        while self.q.empty():
            time.sleep(0.5)  # Wait for events to be pushed into the queue
            queue_wait -= 1
            if queue_wait <= 0:
                raise AssertionError('Queue wait timer expired')
        while not self.q.empty():  # This is not thread-safe and may be inaccurate
            event = self.q.get()
            if isinstance(event, dict):
                event.pop('_stamp')
            if desired_event == event:
                self.fetch_proc.terminate()
                return True
        self.fetch_proc.terminate()
        raise AssertionError('Event {0} was not received by minion'.format(desired_event))


class SaltClientTestCaseMixIn(AdaptedConfigurationTestCaseMixIn):

    _salt_client_config_file_name_ = 'master'
    __slots__ = ()

    @property
    def client(self):
        if 'runtime_client' not in RUNTIME_CONFIGS:
            RUNTIME_CONFIGS['runtime_client'] = salt.client.get_local_client(
                mopts=self.get_config(self._salt_client_config_file_name_, from_scratch=True)
            )
        return RUNTIME_CONFIGS['runtime_client']


class ModuleCase(TestCase, SaltClientTestCaseMixIn):
    '''
    Execute a module function
    '''

    def runTest(self):
        '''
        TODO remove after salt-testing PR #74 is merged and deployed
        '''
        try:
            super(ModuleCase, self).runTest()
        except AttributeError:
            log.error('ModuleCase runTest() could not execute. Requires at least v2016.8.3 of '
                    'salt-testing package')

    def minion_run(self, _function, *args, **kw):
        '''
        Run a single salt function on the 'minion' target and condition
        the return down to match the behavior of the raw function call
        '''
        return self.run_function(_function, args, **kw)

    def run_function(self, function, arg=(), minion_tgt='minion', timeout=25,
                     **kwargs):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        know_to_return_none = (
            'file.chown', 'file.chgrp', 'ssh.recv_known_host'
        )
        orig = self.client.cmd(
            minion_tgt, function, arg, timeout=timeout, kwarg=kwargs
        )

        if minion_tgt not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion \'{0}\'. Command output: {1}'.format(
                    minion_tgt, orig
                )
            )
        elif orig[minion_tgt] is None and function not in know_to_return_none:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get \'{0}\' from '
                'the minion \'{1}\'. Command output: {2}'.format(
                    function, minion_tgt, orig
                )
            )

        # Try to match stalled state functions
        orig[minion_tgt] = self._check_state_return(
            orig[minion_tgt]
        )

        return orig[minion_tgt]

    def run_state(self, function, **kwargs):
        '''
        Run the state.single command and return the state return structure
        '''
        ret = self.run_function('state.single', [function], **kwargs)
        return self._check_state_return(ret)

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return self.get_config('minion')

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the sub_minion
        '''
        return self.get_config('sub_minion')

    def _check_state_return(self, ret):
        if isinstance(ret, dict):
            # This is the supposed return format for state calls
            return ret

        if isinstance(ret, list):
            jids = []
            # These are usually errors
            for item in ret[:]:
                if not isinstance(item, six.string_types):
                    # We don't know how to handle this
                    continue
                match = STATE_FUNCTION_RUNNING_RE.match(item)
                if not match:
                    # We don't know how to handle this
                    continue
                jid = match.group('jid')
                if jid in jids:
                    continue

                jids.append(jid)

                job_data = self.run_function(
                    'saltutil.find_job', [jid]
                )
                job_kill = self.run_function('saltutil.kill_job', [jid])
                msg = (
                    'A running state.single was found causing a state lock. '
                    'Job details: \'{0}\'  Killing Job Returned: \'{1}\''.format(
                        job_data, job_kill
                    )
                )
                ret.append('[TEST SUITE ENFORCED]{0}'
                           '[/TEST SUITE ENFORCED]'.format(msg))
        return ret


class SyndicCase(TestCase, SaltClientTestCaseMixIn):
    '''
    Execute a syndic based execution test
    '''
    _salt_client_config_file_name_ = 'syndic_master'

    def run_function(self, function, arg=()):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg, timeout=25)
        if 'minion' not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion. Command output: {0}'.format(orig)
            )
        return orig['minion']


class ShellCase(AdaptedConfigurationTestCaseMixIn, ShellTestCase, ScriptPathMixin):
    '''
    Execute a test for a shell command
    '''

    _code_dir_ = CODE_DIR
    _script_dir_ = SCRIPT_DIR
    _python_executable_ = PYEXEC

    def chdir(self, dirname):
        try:
            os.chdir(dirname)
        except OSError:
            os.chdir(INTEGRATION_TEST_DIR)

    def run_salt(self, arg_str, with_retcode=False, catch_stderr=False, timeout=60):  # pylint: disable=W0221
        '''
        Execute salt
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=timeout)

    def run_ssh(self, arg_str, with_retcode=False, catch_stderr=False, timeout=60):  # pylint: disable=W0221
        '''
        Execute salt-ssh
        '''
        arg_str = '-ldebug -W -c {0} -i --priv {1} --roster-file {2} --out=json localhost {3}'.format(self.get_config_dir(), os.path.join(TMP_CONF_DIR, 'key_test'), os.path.join(TMP_CONF_DIR, 'roster'), arg_str)
        return self.run_script('salt-ssh', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=timeout, raw=True)

    def run_run(self, arg_str, with_retcode=False, catch_stderr=False, async=False, timeout=60, config_dir=None):
        '''
        Execute salt-run
        '''
        arg_str = '-c {0}{async_flag} -t {timeout} {1}'.format(config_dir or self.get_config_dir(),
                                                  arg_str,
                                                  timeout=timeout,
                                                  async_flag=' --async' if async else '')
        return self.run_script('salt-run', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=60)

    def run_run_plus(self, fun, *arg, **kwargs):
        '''
        Execute the runner function and return the return data and output in a dict
        '''
        ret = {'fun': fun}
        from_scratch = bool(kwargs.pop('__reload_config', False))
        # Have to create an empty dict and then update it, as the result from
        # self.get_config() is an ImmutableDict which cannot be updated.
        opts = {}
        opts.update(self.get_config('client_config', from_scratch=from_scratch))
        opts_arg = list(arg)
        if kwargs:
            opts_arg.append({'__kwarg__': True})
            opts_arg[-1].update(kwargs)
        opts.update({'doc': False, 'fun': fun, 'arg': opts_arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret['return'] = runner.run()
            try:
                ret['jid'] = runner.jid
            except AttributeError:
                ret['jid'] = None

        # Compile output
        # TODO: Support outputters other than nested
        opts['color'] = False
        opts['output_file'] = cStringIO()
        try:
            salt.output.display_output(ret['return'], opts=opts)
            ret['out'] = opts['output_file'].getvalue().splitlines()
        finally:
            opts['output_file'].close()

        return ret

    def run_key(self, arg_str, catch_stderr=False, with_retcode=False):
        '''
        Execute salt-key
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script(
            'salt-key',
            arg_str,
            catch_stderr=catch_stderr,
            with_retcode=with_retcode,
            timeout=60
        )

    def run_cp(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt-cp
        '''
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-cp', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=60)

    def run_call(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt-call.
        '''
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-call', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=60)

    def run_cloud(self, arg_str, catch_stderr=False, timeout=30):
        '''
        Execute salt-cloud
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr,
                               timeout=timeout)


class ShellCaseCommonTestsMixIn(CheckShellBinaryNameAndVersionMixIn):

    _call_binary_expected_version_ = salt.version.__version__

    def test_salt_with_git_version(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')
        from salt.utils import which
        from salt.version import __version_info__, SaltStackVersion
        git = which('git')
        if not git:
            self.skipTest('The git binary is not available')

        # Let's get the output of git describe
        process = subprocess.Popen(
            [git, 'describe', '--tags', '--first-parent', '--match', 'v[0-9]*'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=CODE_DIR
        )
        out, err = process.communicate()
        if process.returncode != 0:
            process = subprocess.Popen(
                [git, 'describe', '--tags', '--match', 'v[0-9]*'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                cwd=CODE_DIR
            )
            out, err = process.communicate()
        if not out:
            self.skipTest(
                'Failed to get the output of \'git describe\'. '
                'Error: \'{0}\''.format(
                    salt.utils.to_str(err)
                )
            )

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info < __version_info__:
            self.skipTest(
                'We\'re likely about to release a new version. This test '
                'would fail. Parsed(\'{0}\') < Expected(\'{1}\')'.format(
                    parsed_version.info, __version_info__
                )
            )
        elif parsed_version.info != __version_info__:
            self.skipTest(
                'In order to get the proper salt version with the '
                'git hash you need to update salt\'s local git '
                'tags. Something like: \'git fetch --tags\' or '
                '\'git fetch --tags upstream\' if you followed '
                'salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.'
            )
        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(parsed_version.string, out)


@requires_sshd_server
class SSHCase(ShellCase):
    '''
    Execute a command via salt-ssh
    '''
    def _arg_str(self, function, arg):
        return '{0} {1}'.format(function, ' '.join(arg))

    def run_function(self, function, arg=(), timeout=90, **kwargs):
        '''
        We use a 90s timeout here, which some slower systems do end up needing
        '''
        ret = self.run_ssh(self._arg_str(function, arg), timeout=timeout)
        try:
            return json.loads(ret)['localhost']
        except Exception:
            return ret


class SaltReturnAssertsMixIn(object):

    def assertReturnSaltType(self, ret):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                '{0} is not dict. Salt returned: {1}'.format(
                    type(ret).__name__, ret
                )
            )

    def assertReturnNonEmptySaltType(self, ret):
        self.assertReturnSaltType(ret)
        try:
            self.assertNotEqual(ret, {})
        except AssertionError:
            raise AssertionError(
                '{} is equal to {}. Salt returned an empty dictionary.'
            )

    def __return_valid_keys(self, keys):
        if isinstance(keys, tuple):
            # If it's a tuple, turn it into a list
            keys = list(keys)
        elif isinstance(keys, six.string_types):
            # If it's a string, make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError('The passed keys need to be a list')
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        keys = self.__return_valid_keys(keys)
        okeys = keys[:]
        for part in six.itervalues(ret):
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    'Could not get ret{0} from salt\'s return: {1}'.format(
                        ''.join(['[\'{0}\']'.format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        'Could not get ret{0} from salt\'s return: {1}'.format(
                            ''.join(['[\'{0}\']'.format(k) for k in keys]), part
                        )
                    )
            return ret_item

    def assertSaltTrueReturn(self, ret):
        try:
            self.assertTrue(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not True. Salt Comment:\n{comment}'.format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned:\n{0}'.format(
                        pprint.pformat(ret)
                    )
                )

    def assertSaltFalseReturn(self, ret):
        try:
            self.assertFalse(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not False. Salt Comment:\n{comment}'.format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertSaltNoneReturn(self, ret):
        try:
            self.assertIsNone(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not None. Salt Comment:\n{comment}'.format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertInSaltComment(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertNotInSaltComment(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertSaltCommentRegexpMatches(self, ret, pattern):
        return self.assertInSaltReturnRegexpMatches(ret, pattern, 'comment')

    def assertInSaltStateWarning(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertNotInSaltStateWarning(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertInSaltReturn(self, item_to_check, ret, keys):
        return self.assertIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertNotInSaltReturn(self, item_to_check, ret, keys):
        return self.assertNotIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertInSaltReturnRegexpMatches(self, ret, pattern, keys=()):
        return self.assertRegexpMatches(
            self.__getWithinSaltReturn(ret, keys), pattern
        )

    def assertSaltStateChangesEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )

    def assertSaltStateChangesNotEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertNotEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )
