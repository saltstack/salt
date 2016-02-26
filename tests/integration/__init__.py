# -*- coding: utf-8 -*-

'''
Set up the Salt integration test suite
'''

# Import Python libs
from __future__ import absolute_import, print_function
import platform
import os
import re
import sys
import copy
import json
import time
import signal
import shutil
import pprint
import atexit
import logging
import tempfile
import subprocess
import multiprocessing
from hashlib import md5
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
from salt.utils import fopen, get_colors
from salt.utils.verify import verify_env
from salt.utils.immutabletypes import freeze
from salt.utils.process import MultiprocessingProcess
from salt.exceptions import SaltClientError

try:
    import salt.master
except ImportError:
    # Not required for raet tests
    pass

# Import 3rd-party libs
import yaml
import salt.ext.six as six

if salt.utils.is_windows():
    import win32api


if platform.uname()[0] == 'Darwin':
    SYS_TMP_DIR = '/tmp'
else:
    SYS_TMP_DIR = os.environ.get('TMPDIR', tempfile.gettempdir())

# Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
PYEXEC = 'python{0}.{1}'.format(*sys.version_info)
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_PRODENV_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-prodenv-state-tree')
TMP_CONF_DIR = os.path.join(TMP, 'config')
CONF_DIR = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
PILLAR_DIR = os.path.join(FILES, 'pillar')

RUNTIME_CONFIGS = {}

log = logging.getLogger(__name__)


def cleanup_runtime_config_instance(to_cleanup):
    # Explicit and forced cleanup
    for key in list(to_cleanup.keys()):
        instance = to_cleanup.pop(key)
        del instance


atexit.register(cleanup_runtime_config_instance, RUNTIME_CONFIGS)


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


class TestDaemon(object):
    '''
    Set up the master and minion daemons, and run related cases
    '''
    MINIONS_CONNECT_TIMEOUT = MINIONS_SYNC_TIMEOUT = 120

    def __init__(self, parser):
        self.parser = parser
        self.colors = get_colors(self.parser.options.no_colors is False)

    def __enter__(self):
        '''
        Start a master and minion
        '''
        # Setup the multiprocessing logging queue listener
        salt_log_setup.setup_multiprocessing_logging_listener(
            self.parser.options
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
        self.master_process = self.start_daemon(salt.master.Master,
                                                self.master_opts,
                                                'start')

        self.minion_process = self.start_daemon(salt.minion.Minion,
                                                self.minion_opts,
                                                'tune_in')

        self.sub_minion_process = self.start_daemon(salt.minion.Minion,
                                                    self.sub_minion_opts,
                                                    'tune_in')

        self.smaster_process = self.start_daemon(salt.master.Master,
                                                self.syndic_master_opts,
                                                'start')

        self.syndic_process = self.start_daemon(salt.minion.Syndic,
                                                self.syndic_opts,
                                                'tune_in')

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
        print(' * Initializing SSH subsystem')
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
        print(' * Transplanting configuration files to \'{0}\''.format(TMP_CONF_DIR))
        if salt.utils.is_windows():
            running_tests_user = win32api.GetUserName()
        else:
            running_tests_user = pwd.getpwuid(os.getuid()).pw_name
        master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'master'))
        master_opts['user'] = running_tests_user
        tests_know_hosts_file = os.path.join(TMP_CONF_DIR, 'salt_ssh_known_hosts')
        with salt.utils.fopen(tests_know_hosts_file, 'w') as known_hosts:
            known_hosts.write('')
        master_opts['known_hosts_file'] = tests_know_hosts_file

        minion_config_path = os.path.join(CONF_DIR, 'minion')
        minion_opts = salt.config._read_conf_file(minion_config_path)
        minion_opts['user'] = running_tests_user
        minion_opts['root_dir'] = master_opts['root_dir'] = os.path.join(TMP, 'master-minion-root')

        syndic_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic'))
        syndic_opts['user'] = running_tests_user

        sub_minion_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'sub_minion'))
        sub_minion_opts['root_dir'] = os.path.join(TMP, 'sub-minion-root')
        sub_minion_opts['user'] = running_tests_user

        syndic_master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic_master'))
        syndic_master_opts['user'] = running_tests_user
        syndic_master_opts['root_dir'] = os.path.join(TMP, 'syndic-master-root')

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
        master_opts['pillar_roots'] = {
            'base': [os.path.join(FILES, 'pillar', 'base')]
        }
        master_opts['file_roots'] = {
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
        master_opts['ext_pillar'].append(
            {'cmd_yaml': 'cat {0}'.format(
                os.path.join(
                    FILES,
                    'ext.yaml'
                )
            )}
        )

        # We need to copy the extension modules into the new master root_dir or
        # it will be prefixed by it
        new_extension_modules_path = os.path.join(master_opts['root_dir'], 'extension_modules')
        if not os.path.exists(new_extension_modules_path):
            shutil.copytree(
                os.path.join(
                    INTEGRATION_TEST_DIR, 'files', 'extension_modules'
                ),
                new_extension_modules_path
            )
        master_opts['extension_modules'] = os.path.join(TMP, 'master-minion-root', 'extension_modules')

        # Point the config values to the correct temporary paths
        for name in ('hosts', 'aliases'):
            optname = '{0}.file'.format(name)
            optname_path = os.path.join(TMP, name)
            master_opts[optname] = optname_path
            minion_opts[optname] = optname_path
            sub_minion_opts[optname] = optname_path

        # ----- Transcribe Configuration ---------------------------------------------------------------------------->
        for entry in os.listdir(CONF_DIR):
            if entry in ('master', 'minion', 'sub_minion', 'syndic_master'):
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

        for entry in ('master', 'minion', 'sub_minion', 'syndic_master'):
            computed_config = copy.deepcopy(locals()['{0}_opts'.format(entry)])
            salt.utils.fopen(os.path.join(TMP_CONF_DIR, entry), 'w').write(
                yaml.dump(computed_config, default_flow_style=False)
            )
        # <---- Transcribe Configuration -----------------------------------------------------------------------------

        # ----- Verify Environment ---------------------------------------------------------------------------------->
        master_opts = salt.config.master_config(os.path.join(TMP_CONF_DIR, 'master'))
        minion_config_path = os.path.join(TMP_CONF_DIR, 'minion')
        minion_opts = salt.config.minion_config(minion_config_path)

        syndic_opts = salt.config.syndic_config(
            os.path.join(TMP_CONF_DIR, 'syndic'),
            minion_config_path
        )
        sub_minion_opts = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'sub_minion'))
        syndic_master_opts = salt.config.master_config(os.path.join(TMP_CONF_DIR, 'syndic_master'))

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
        salt.utils.process.clean_proc(self.sub_minion_process, wait_for_kill=50)
        self.sub_minion_process.join()
        salt.utils.process.clean_proc(self.minion_process, wait_for_kill=50)
        self.minion_process.join()
        salt.utils.process.clean_proc(self.master_process, wait_for_kill=50)
        self.master_process.join()
        try:
            salt.utils.process.clean_proc(self.syndic_process, wait_for_kill=50)
            self.syndic_process.join()
        except AttributeError:
            pass
        try:
            salt.utils.process.clean_proc(self.smaster_process, wait_for_kill=50)
            self.smaster_process.join()
        except AttributeError:
            pass
        self._exit_mockbin()
        self._exit_ssh()
        # Shutdown the multiprocessing logging queue listener
        salt_log_setup.shutdown_multiprocessing_logging()
        salt_log_setup.shutdown_multiprocessing_logging_listener()

    def pre_setup_minions(self):
        '''
        Subclass this method for additional minion setups.
        '''

    def setup_minions(self):
        # Wait for minions to connect back
        wait_minion_connections = MultiprocessingProcess(
            target=self.wait_for_minion_connections,
            args=(self.minion_targets, self.MINIONS_CONNECT_TIMEOUT)
        )
        wait_minion_connections.start()
        wait_minion_connections.join()
        wait_minion_connections.terminate()
        if wait_minion_connections.exitcode > 0:
            print(
                '\n {LIGHT_RED}*{ENDC} ERROR: Minions failed to connect'.format(
                    **self.colors
                )
            )
            return False

        del wait_minion_connections

        sync_needed = self.parser.options.clean
        if self.parser.options.clean is False:
            def sumfile(fpath):
                # Since we will be doing this for small files, it should be ok
                fobj = fopen(fpath)
                m = md5()
                while True:
                    d = fobj.read(8096)
                    if not d:
                        break
                    m.update(d)
                return m.hexdigest()
            # Since we're not cleaning up, let's see if modules are already up
            # to date so we don't need to re-sync them
            modules_dir = os.path.join(FILES, 'file', 'base', '_modules')
            for fname in os.listdir(modules_dir):
                if not fname.endswith('.py'):
                    continue
                dfile = os.path.join(
                    '/tmp/salttest/cachedir/extmods/modules/', fname
                )

                if not os.path.exists(dfile):
                    sync_needed = True
                    break

                sfile = os.path.join(modules_dir, fname)
                if sumfile(sfile) != sumfile(dfile):
                    sync_needed = True
                    break

        if sync_needed:
            # Wait for minions to "sync_all"
            for target in [self.sync_minion_modules,
                           self.sync_minion_states,
                           self.sync_minion_grains]:
                sync_minions = MultiprocessingProcess(
                    target=target,
                    args=(self.minion_targets, self.MINIONS_SYNC_TIMEOUT)
                )
                sync_minions.start()
                sync_minions.join()
                if sync_minions.exitcode > 0:
                    return False
                sync_minions.terminate()
                del sync_minions

        return True

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
        for dirname in (TMP, TMP_STATE_TREE, TMP_PRODENV_STATE_TREE):
            if os.path.isdir(dirname):
                shutil.rmtree(dirname)

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
        return os.path.join(TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        '''
        Return the options used for the minion
        '''
        return self.get_config('master')


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
        Return the options used for the minion
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


class ShellCase(AdaptedConfigurationTestCaseMixIn, ShellTestCase):
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

    def run_salt(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr)

    def run_ssh(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt-ssh
        '''
        arg_str = '-c {0} -i --priv {1} --roster-file {2} --out=json localhost {3}'.format(self.get_config_dir(), os.path.join(TMP_CONF_DIR, 'key_test'), os.path.join(TMP_CONF_DIR, 'roster'), arg_str)
        return self.run_script('salt-ssh', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, raw=True)

    def run_run(self, arg_str, with_retcode=False, catch_stderr=False, async=False, timeout=60):
        '''
        Execute salt-run
        '''
        arg_str = '-c {0}{async_flag} -t {timeout} {1}'.format(self.get_config_dir(),
                                                  arg_str,
                                                  timeout=timeout,
                                                  async_flag=' --async' if async else '')
        return self.run_script('salt-run', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr)

    def run_run_plus(self, fun, options='', *arg, **kwargs):
        '''
        Execute Salt run and the salt run function and return the data from
        each in a dict
        '''
        ret = {}
        ret['out'] = self.run_run(
            '{0} {1} {2}'.format(options, fun, ' '.join(arg)), catch_stderr=kwargs.get('catch_stderr', None)
        )
        opts = {}
        opts.update(self.get_config('master'))
        opts.update({'doc': False, 'fun': fun, 'arg': arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret['fun'] = runner.run()
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
            with_retcode=with_retcode
        )

    def run_cp(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt-cp
        '''
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-cp', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr)

    def run_call(self, arg_str, with_retcode=False, catch_stderr=False):
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-call', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr)

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        '''
        Execute salt-cloud
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr, timeout)


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

    def run_function(self, function, arg=(), timeout=25, **kwargs):
        ret = self.run_ssh(self._arg_str(function, arg))
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
