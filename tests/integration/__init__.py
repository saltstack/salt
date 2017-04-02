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

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.normpath(os.path.abspath(__file__))))
if os.name == 'nt':
    TESTS_DIR = TESTS_DIR.replace('\\', '\\\\')
CODE_DIR = os.path.dirname(TESTS_DIR)

# Let's inject CODE_DIR so salt is importable if not there already
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

# Import salt tests support dirs
from tests.support.paths import *  # pylint: disable=wildcard-import
from tests.support.processes import *  # pylint: disable=wildcard-import
from tests.support.unit import TestCase
from tests.support.case import ShellTestCase
from tests.support.parser import PNUM, print_header, SaltTestcaseParser
from tests.support.helpers import requires_sshd_server, RedirectStdStreams
from tests.support.paths import ScriptPathMixin
from tests.support.mixins import RUNTIME_CONFIGS
from tests.support.mixins import CheckShellBinaryNameAndVersionMixin, ShellCaseCommonTestsMixin
from tests.support.mixins import AdaptedConfigurationTestCaseMixin, SaltClientTestCaseMixin
from tests.support.mixins import SaltMinionEventAssertsMixin, SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
# Import Salt libs
import salt
import salt.config
import salt.minion
import salt.runner
import salt.output
import salt.version
import salt.utils
import salt.utils.network
import salt.utils.process
import salt.log.setup as salt_log_setup
from salt.ext import six
from salt.utils.verify import verify_env
from salt.utils.immutabletypes import freeze
from salt.utils.nb_popen import NonBlockingPopen
from salt.exceptions import SaltClientError

try:
    from salt.utils.gitfs import HAS_GITPYTHON, HAS_PYGIT2
    HAS_GITFS = HAS_GITPYTHON or HAS_PYGIT2
except ImportError:
    HAS_GITFS = False

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

from tornado import gen
from tornado import ioloop

# Import salt tests support libs
from tests.support.processes import SaltMaster, SaltMinion, SaltSyndic

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

        if not HAS_GITFS:
            sys.stdout.write(
                ' * {LIGHT_RED}No suitable provider for git_pillar is installed. Install\n'
                '   GitPython or Pygit2.{ENDC}\n'.format(
                    **self.colors
                )
            )

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
        if not salt.utils.network.ip_addrs():
            sys.stdout.write(
                ' * {LIGHT_RED}Unable to list IPv4 addresses. Test suite startup will be\n'
                '   slower. Install iproute/ifconfig to fix this.{ENDC}\n'.format(
                    **self.colors
                )
            )
        self.log_server = ThreadedSocketServer(('localhost', SALT_LOG_PORT), SocketServerRequestHandler)
        self.log_server_process = threading.Thread(target=self.log_server.serve_forever)
        self.log_server_process.daemon = True
        self.log_server_process.start()
        try:
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting salt-master ... {ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
            self.master_process = start_daemon(
                daemon_name='salt-master',
                daemon_id=self.master_opts['id'],
                daemon_log_prefix='salt-master/{}'.format(self.master_opts['id']),
                daemon_cli_script_name='master',
                daemon_config=self.master_opts,
                daemon_config_dir=TMP_CONF_DIR,
                daemon_class=SaltMaster,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=30)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting salt-master ... STARTED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_RED}Starting salt-master ... FAILED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()

        try:
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting salt-minion ... {ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
            self.minion_process = start_daemon(
                daemon_name='salt-minion',
                daemon_id=self.master_opts['id'],
                daemon_log_prefix='salt-minion/{}'.format(self.minion_opts['id']),
                daemon_cli_script_name='minion',
                daemon_config=self.minion_opts,
                daemon_config_dir=TMP_CONF_DIR,
                daemon_class=SaltMinion,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=30)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting salt-minion ... STARTED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_RED}Starting salt-minion ... FAILED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()

        try:
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting sub salt-minion ... {ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
            self.sub_minion_process = start_daemon(
                daemon_name='sub salt-minion',
                daemon_id=self.master_opts['id'],
                daemon_log_prefix='sub-salt-minion/{}'.format(self.sub_minion_opts['id']),
                daemon_cli_script_name='minion',
                daemon_config=self.sub_minion_opts,
                daemon_config_dir=TMP_SUB_MINION_CONF_DIR,
                daemon_class=SaltMinion,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=30)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting sub salt-minion ... STARTED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_RED}Starting sub salt-minion ... FAILED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()

        try:
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting syndic salt-master ... {ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
            self.smaster_process = start_daemon(
                daemon_name='salt-smaster',
                daemon_id=self.syndic_master_opts['id'],
                daemon_log_prefix='salt-smaster/{}'.format(self.syndic_master_opts['id']),
                daemon_cli_script_name='master',
                daemon_config=self.syndic_master_opts,
                daemon_config_dir=TMP_SYNDIC_MASTER_CONF_DIR,
                daemon_class=SaltMaster,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=30)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting syndic salt-master ... STARTED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_RED}Starting syndic salt-master ... FAILED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()

        try:
            sys.stdout.write(
                ' * {LIGHT_YELLOW}Starting salt-syndic ... {ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
            self.syndic_process = start_daemon(
                daemon_name='salt-syndic',
                daemon_id=self.syndic_opts['id'],
                daemon_log_prefix='salt-syndic/{}'.format(self.syndic_opts['id']),
                daemon_cli_script_name='syndic',
                daemon_config=self.syndic_opts,
                daemon_config_dir=TMP_SYNDIC_MINION_CONF_DIR,
                daemon_class=SaltSyndic,
                bin_dir_path=SCRIPT_DIR,
                fail_hard=True,
                start_timeout=30)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_GREEN}Starting salt-syndic ... STARTED!\n{ENDC}'.format(**self.colors)
            )
            sys.stdout.flush()
        except (RuntimeWarning, RuntimeError):
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', PNUM)
                )
            )
            sys.stdout.write(
                ' * {LIGHT_RED}Starting salt-syndic ... FAILED!\n{ENDC}'.format(**self.colors)
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
        with salt.utils.fopen(os.path.join(TMP_CONF_DIR, 'roster'), 'a') as roster:
            roster.write('  user: {0}\n'.format(RUNTIME_VARS.RUNNING_TESTS_USER))
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
        tests_known_hosts_file = os.path.join(TMP_CONF_DIR, 'salt_ssh_known_hosts')
        with salt.utils.fopen(tests_known_hosts_file, 'w') as known_hosts:
            known_hosts.write('')

        # This master connects to syndic_master via a syndic
        master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'master'))
        master_opts['known_hosts_file'] = tests_known_hosts_file
        master_opts['cachedir'] = os.path.join(TMP, 'rootdir', 'cache')
        master_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
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
        minion_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
        minion_opts['config_dir'] = TMP_CONF_DIR
        minion_opts['root_dir'] = os.path.join(TMP, 'rootdir')
        minion_opts['pki_dir'] = os.path.join(TMP, 'rootdir', 'pki')
        minion_opts['hosts.file'] = os.path.join(TMP, 'rootdir', 'hosts')
        minion_opts['aliases.file'] = os.path.join(TMP, 'rootdir', 'aliases')

        # This sub_minion also connects to master
        sub_minion_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'sub_minion'))
        sub_minion_opts['cachedir'] = os.path.join(TMP, 'rootdir-sub-minion', 'cache')
        sub_minion_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
        sub_minion_opts['config_dir'] = TMP_SUB_MINION_CONF_DIR
        sub_minion_opts['root_dir'] = os.path.join(TMP, 'rootdir-sub-minion')
        sub_minion_opts['pki_dir'] = os.path.join(TMP, 'rootdir-sub-minion', 'pki', 'minion')
        sub_minion_opts['hosts.file'] = os.path.join(TMP, 'rootdir', 'hosts')
        sub_minion_opts['aliases.file'] = os.path.join(TMP, 'rootdir', 'aliases')

        # This is the master of masters
        syndic_master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic_master'))
        syndic_master_opts['cachedir'] = os.path.join(TMP, 'rootdir-syndic-master', 'cache')
        syndic_master_opts['user'] = RUNTIME_VARS.RUNNING_TESTS_USER
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

        master_opts['runtests_conn_check_port'] = get_unused_localhost_port()
        minion_opts['runtests_conn_check_port'] = get_unused_localhost_port()
        sub_minion_opts['runtests_conn_check_port'] = get_unused_localhost_port()
        syndic_opts['runtests_conn_check_port'] = get_unused_localhost_port()
        syndic_master_opts['runtests_conn_check_port'] = get_unused_localhost_port()

        for conf in (master_opts, minion_opts, sub_minion_opts, syndic_opts, syndic_master_opts):
            if 'engines' not in conf:
                conf['engines'] = []
            conf['engines'].append({'salt_runtests': {}})

            if 'engines_dirs' not in conf:
                conf['engines_dirs'] = []

            conf['engines_dirs'].insert(0, ENGINES_DIR)

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
                   RUNTIME_VARS.RUNNING_TESTS_USER)

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
            # Give full permissions to owner
            os.chmod(path, stat.S_IRWXU)
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
            list(targets), 'saltutil.running', tgt_type='list'
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
                    list(expected_connections), 'test.ping', tgt_type='list',
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
            tgt_type='list',
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
        salt.utils.appendproctitle('SyncMinionGrains')
        self.sync_minion_modules_('grains', targets, timeout=timeout)


class ModuleCase(TestCase, SaltClientTestCaseMixin):
    '''
    Execute a module function
    '''

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
        if 'f_arg' in kwargs:
            kwargs['arg'] = kwargs.pop('f_arg')
        if 'f_timeout' in kwargs:
            kwargs['timeout'] = kwargs.pop('f_timeout')
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


class SyndicCase(TestCase, SaltClientTestCaseMixin):
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


class ShellCase(ShellTestCase, AdaptedConfigurationTestCaseMixin, ScriptPathMixin):
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
