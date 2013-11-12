'''
Set up the Salt integration test suite
'''

# Import Python libs
import re
import os
import sys
import time
import shutil
import pprint
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


INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))
SALT_LIBS = os.path.dirname(CODE_DIR)

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.case import ShellTestCase
from salttesting.mixins import CheckShellBinaryNameAndVersionMixIn
from salttesting.parser import PNUM, print_header, SaltTestcaseParser
from salttesting.helpers import ensure_in_syspath, RedirectStdStreams

# Update sys.path
ensure_in_syspath(CODE_DIR, SALT_LIBS)

# Import Salt libs
import salt
import salt.config
import salt.master
import salt.minion
import salt.runner
import salt.output
import salt.version
from salt.utils import fopen, get_colors
from salt.utils.verify import verify_env

# Import 3rd-party libs
import yaml

# Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
SYS_TMP_DIR = os.environ.get('TMPDIR', tempfile.gettempdir())
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
PYEXEC = 'python{0}.{1}'.format(sys.version_info[0], sys.version_info[1])
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_CONF_DIR = os.path.join(TMP, 'config')

log = logging.getLogger(__name__)


def run_tests(TestCase, needs_daemon=True):
    '''
    Run integration tests for a chosen test case.

    Function uses optparse to set up test environment
    '''
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

        def run_testcase(self, testcase, needs_daemon=True):
            if needs_daemon:
                print('Setting up Salt daemons to execute tests')
                with TestDaemon(self):
                    return SaltTestcaseParser.run_testcase(self, testcase)
            return SaltTestcaseParser.run_testcase(self, testcase)

    parser = TestcaseParser()
    parser.parse_args()
    if parser.run_testcase(TestCase, needs_daemon=needs_daemon) is False:
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
        running_tests_user = pwd.getpwuid(os.getuid()).pw_name
        self.master_opts = salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )
        self.master_opts['user'] = running_tests_user
        minion_config_path = os.path.join(
            INTEGRATION_TEST_DIR, 'files', 'conf', 'minion'
        )
        self.minion_opts = salt.config.minion_config(minion_config_path)
        self.minion_opts['user'] = running_tests_user
        self.syndic_opts = salt.config.syndic_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic'),
            minion_config_path
        )
        self.syndic_opts['user'] = running_tests_user

        #if sys.version_info < (2, 7):
        #    self.minion_opts['multiprocessing'] = False
        self.sub_minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'sub_minion')
        )
        self.sub_minion_opts['root_dir'] = os.path.join(TMP, 'subsalt')
        self.sub_minion_opts['user'] = running_tests_user
        #if sys.version_info < (2, 7):
        #    self.sub_minion_opts['multiprocessing'] = False
        self.smaster_opts = salt.config.master_config(
            os.path.join(
                INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic_master'
            )
        )
        self.smaster_opts['user'] = running_tests_user

        # Set up config options that require internal data
        self.master_opts['pillar_roots'] = {
            'base': [os.path.join(FILES, 'pillar', 'base')]
        }
        self.master_opts['file_roots'] = {
            'base': [
                os.path.join(FILES, 'file', 'base'),
                # Let's support runtime created files that can be used like:
                #   salt://my-temp-file.txt
                TMP_STATE_TREE
            ]
        }
        self.master_opts['ext_pillar'].append(
            {'cmd_yaml': 'cat {0}'.format(
                os.path.join(
                    FILES,
                    'ext.yaml'
                )
            )}
        )
        self.master_opts['extension_modules'] = os.path.join(INTEGRATION_TEST_DIR, 'files', 'extension_modules')
        # clean up the old files
        self._clean()

        # Point the config values to the correct temporary paths
        for name in ('hosts', 'aliases'):
            optname = '{0}.file'.format(name)
            optname_path = os.path.join(TMP, name)
            self.master_opts[optname] = optname_path
            self.minion_opts[optname] = optname_path
            self.sub_minion_opts[optname] = optname_path

        verify_env([os.path.join(self.master_opts['pki_dir'], 'minions'),
                    os.path.join(self.master_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.master_opts['pki_dir'],
                                 'minions_rejected'),
                    os.path.join(self.master_opts['cachedir'], 'jobs'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions'),
                    os.path.join(self.smaster_opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.smaster_opts['pki_dir'],
                                 'minions_rejected'),
                    os.path.join(self.smaster_opts['cachedir'], 'jobs'),
                    os.path.dirname(self.master_opts['log_file']),
                    self.minion_opts['extension_modules'],
                    self.sub_minion_opts['extension_modules'],
                    self.sub_minion_opts['pki_dir'],
                    self.master_opts['sock_dir'],
                    self.smaster_opts['sock_dir'],
                    self.sub_minion_opts['sock_dir'],
                    self.minion_opts['sock_dir'],
                    TMP_STATE_TREE,
                    TMP
                    ],
                   running_tests_user)

        # Set up PATH to mockbin
        self._enter_mockbin()

        master = salt.master.Master(self.master_opts)
        self.master_process = multiprocessing.Process(target=master.start)
        self.master_process.start()

        minion = salt.minion.Minion(self.minion_opts)
        self.minion_process = multiprocessing.Process(target=minion.tune_in)
        self.minion_process.start()

        sub_minion = salt.minion.Minion(self.sub_minion_opts)
        self.sub_minion_process = multiprocessing.Process(
            target=sub_minion.tune_in
        )
        self.sub_minion_process.start()

        smaster = salt.master.Master(self.smaster_opts)
        self.smaster_process = multiprocessing.Process(target=smaster.start)
        self.smaster_process.start()

        syndic = salt.minion.Syndic(self.syndic_opts)
        self.syndic_process = multiprocessing.Process(target=syndic.tune_in)
        self.syndic_process.start()

        if os.environ.get('DUMP_SALT_CONFIG', None) is not None:
            from copy import deepcopy
            try:
                os.makedirs('/tmp/salttest/conf')
            except OSError:
                pass
            master_opts = deepcopy(self.master_opts)
            minion_opts = deepcopy(self.minion_opts)
            master_opts.pop('conf_file', None)

            minion_opts.pop('conf_file', None)
            minion_opts.pop('grains', None)
            minion_opts.pop('pillar', None)
            open('/tmp/salttest/conf/master', 'w').write(
                yaml.dump(master_opts)
            )
            open('/tmp/salttest/conf/minion', 'w').write(
                yaml.dump(minion_opts)
            )

        self.minion_targets = set(['minion', 'sub_minion'])
        self.pre_setup_minions()
        self.setup_minions()

        if self.parser.options.sysinfo:
            print_header('~~~~~~~ Versions Report ', inline=True)
            print('\n'.join(salt.version.versions_report()))

            print_header(
                '~~~~~~~ Minion Grains Information ', inline=True,
            )
            grains = self.client.cmd('minion', 'grains.items')

            minion_opts = self.minion_opts.copy()
            minion_opts['color'] = self.parser.options.no_colors is False
            salt.output.display_output(grains, 'grains', minion_opts)

        print_header('', sep='=', inline=True)

        try:
            return self
        finally:
            self.post_setup_minions()

    @property
    def client(self):
        '''
        Return a local client which will be used for example to ping and sync
        the test minions.

        This client is defined as a class attribute because it's creation needs
        to be deferred to a latter stage. If created it on `__enter__` like it
        previously was, it would not receive the master events.
        '''
        return salt.client.LocalClient(
            mopts=self.master_opts
        )

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        import integration
        integration.SYNDIC = None
        self.sub_minion_process.terminate()
        self.sub_minion_process.join()
        self.minion_process.terminate()
        self.minion_process.join()
        self.master_process.terminate()
        self.master_process.join()
        self.syndic_process.terminate()
        self.syndic_process.join()
        self.smaster_process.terminate()
        self.smaster_process.join()
        self._exit_mockbin()
        self._clean()

    def pre_setup_minions(self):
        '''
        Subclass this method for additional minion setups.
        '''

    def setup_minions(self):
        # Wait for minions to connect back
        wait_minion_connections = multiprocessing.Process(
            target=self.wait_for_minion_connections,
            args=(self.minion_targets, self.MINIONS_CONNECT_TIMEOUT)
        )
        wait_minion_connections.start()
        wait_minion_connections.join()
        wait_minion_connections.terminate()
        if wait_minion_connections.exitcode > 0:
            print(
                '\n {RED_BOLD}*{ENDC} ERROR: Minions failed to connect'.format(
                **self.colors
                )
            )
            return False

        del wait_minion_connections

        sync_needed = self.parser.options.clean
        if self.parser.options.clean is False:
            def sumfile(fpath):
                # Since we will be do'in this for small files, it should be ok
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
            sync_minions = multiprocessing.Process(
                target=self.sync_minion_modules,
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

    def _exit_mockbin(self):
        path = os.environ.get('PATH', '')
        path_items = path.split(os.pathsep)
        try:
            path_items.remove(MOCKBIN)
        except ValueError:
            pass
        os.environ['PATH'] = os.pathsep.join(path_items)

    def _clean(self):
        '''
        Clean out the tmp files
        '''
        if not self.parser.options.clean:
            return
        if os.path.isdir(self.sub_minion_opts['root_dir']):
            shutil.rmtree(self.sub_minion_opts['root_dir'])
        if os.path.isdir(self.master_opts['root_dir']):
            shutil.rmtree(self.master_opts['root_dir'])
        if os.path.isdir(self.smaster_opts['root_dir']):
            shutil.rmtree(self.smaster_opts['root_dir'])
        if os.path.isdir(TMP):
            shutil.rmtree(TMP)

    def wait_for_jid(self, targets, jid, timeout=120):
        time.sleep(1)  # Allow some time for minions to accept jobs
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        job_finished = False
        while now <= expire:
            running = self.__client_job_running(targets, jid)
            sys.stdout.write('\r' + ' ' * PNUM + '\r')
            if not running and job_finished is False:
                # Let's not have false positives and wait one more seconds
                job_finished = True
            elif not running and job_finished is True:
                return True
            elif running and job_finished is True:
                job_finished = False

            if job_finished is False:
                sys.stdout.write(
                    '   * {YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                        '{0}'.format(expire - now).rsplit('.', 1)[0],
                        ', '.join(running),
                        **self.colors
                    )
                )
                sys.stdout.flush()
            time.sleep(1)
            now = datetime.now()
        else:
            sys.stdout.write(
                '\n {RED_BOLD}*{ENDC} ERROR: Failed to get information '
                'back\n'.format(**self.colors)
            )
            sys.stdout.flush()
        return False

    def __client_job_running(self, targets, jid):
        running = self.client.cmd(
            list(targets), 'saltutil.running', expr_form='list'
        )
        return [
            k for (k, v) in running.iteritems() if v and v[0]['jid'] == jid
        ]

    def wait_for_minion_connections(self, targets, timeout):
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
            sys.stdout.write('\r' + ' ' * PNUM + '\r')
            sys.stdout.write(
                ' * {YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                    '{0}'.format(expire - now).rsplit('.', 1)[0],
                    ', '.join(expected_connections),
                    **self.colors
                )
            )
            sys.stdout.flush()

            responses = self.client.cmd(
                list(expected_connections), 'test.ping', expr_form='list',
            )
            for target in responses:
                if target not in expected_connections:
                    # Someone(minion) else "listening"?
                    continue
                expected_connections.remove(target)
                sys.stdout.write('\r' + ' ' * PNUM + '\r')
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
        else:
            print(
                '\n {RED_BOLD}*{ENDC} WARNING: Minions failed to connect '
                'back. Tests requiring them WILL fail'.format(**self.colors)
            )
            print_header('=', sep='=', inline=True)
            raise SystemExit()

    def sync_minion_modules(self, targets, timeout=120):
        # Let's sync all connected minions
        print(
            ' {LIGHT_BLUE}*{ENDC} Syncing minion\'s modules '
            '(saltutil.sync_modules)'.format(
                ', '.join(targets),
                **self.colors
            )
        )
        syncing = set(targets)
        jid_info = self.client.run_job(
            list(targets), 'saltutil.sync_modules',
            expr_form='list',
            timeout=9999999999999999,
        )

        if self.wait_for_jid(targets, jid_info['jid'], timeout) is False:
            print(
                ' {RED_BOLD}*{ENDC} WARNING: Minions failed to sync modules. '
                'Tests requiring these modules WILL fail'.format(**self.colors)
            )
            raise SystemExit()

        while syncing:
            rdata = self.client.get_full_returns(jid_info['jid'], syncing, 1)
            if rdata:
                for name, output in rdata.iteritems():
                    if not output['ret']:
                        # Already synced!?
                        syncing.remove(name)
                        continue

                    print(
                        '   {LIGHT_GREEN}*{ENDC} Synced {0} modules: '
                        '{1}'.format(
                            name, ', '.join(output['ret']), **self.colors
                        )
                    )
                    # Synced!
                    try:
                        syncing.remove(name)
                    except KeyError:
                        print(
                            ' {RED_BOLD}*{ENDC} {0} already synced??? '
                            '{1}'.format(name, output, **self.colors)
                        )
        return True


class AdaptedConfigurationTestCaseMixIn(object):

    __slots__ = ()

    def get_config_dir(self):
        integration_config_dir = os.path.join(
            INTEGRATION_TEST_DIR, 'files', 'conf'
        )
        if os.getuid() == 0:
            # Running as root, the running user does not need to be updated
            return integration_config_dir

        for fname in os.listdir(integration_config_dir):
            self.get_config_file_path(fname)
        return TMP_CONF_DIR

    def get_config_file_path(self, filename):
        integration_config_file = os.path.join(
            INTEGRATION_TEST_DIR, 'files', 'conf', filename
        )
        if os.getuid() == 0:
            # Running as root, the running user does not need to be updated
            return integration_config_file

        if not os.path.isdir(TMP_CONF_DIR):
            os.makedirs(TMP_CONF_DIR)

        updated_config_path = os.path.join(TMP_CONF_DIR, filename)
        if not os.path.isfile(updated_config_path):
            self.__update_config(integration_config_file, updated_config_path)
        return updated_config_path

    def __update_config(self, source, dest):
        if not os.path.isfile(dest):
            running_tests_user = pwd.getpwuid(os.getuid()).pw_name
            configuration = yaml.load(open(source).read())
            configuration['user'] = running_tests_user
            open(dest, 'w').write(yaml.dump(configuration))


class SaltClientTestCaseMixIn(AdaptedConfigurationTestCaseMixIn):

    _salt_client_config_file_name_ = 'master'
    __slots__ = ('client', '_salt_client_config_file_name_')

    @property
    def client(self):
        return salt.client.LocalClient(
            self.get_config_file_path(self._salt_client_config_file_name_)
        )


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
        return orig[minion_tgt]

    def run_state(self, function, **kwargs):
        '''
        Run the state.single command and return the state return structure
        '''
        return self.run_function('state.single', [function], **kwargs)

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
            self.get_config_file_path('minion')
        )

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
            self.get_config_file_path('sub_minion')
        )

    @property
    def master_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.master_config(
            self.get_config_file_path('master')
        )


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

    def run_salt(self, arg_str, with_retcode=False):
        '''
        Execute salt
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt', arg_str, with_retcode=with_retcode)

    def run_run(self, arg_str, with_retcode=False):
        '''
        Execute salt-run
        '''
        arg_str = '-c {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-run', arg_str, with_retcode=with_retcode)

    def run_run_plus(self, fun, options='', *arg):
        '''
        Execute Salt run and the salt run function and return the data from
        each in a dict
        '''
        ret = {}
        ret['out'] = self.run_run(
            '{0} {1} {2}'.format(options, fun, ' '.join(arg))
        )
        opts = salt.config.master_config(
            self.get_config_file_path('master')
        )
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

    def run_cp(self, arg_str, with_retcode=False):
        '''
        Execute salt-cp
        '''
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-cp', arg_str, with_retcode=with_retcode)

    def run_call(self, arg_str, with_retcode=False):
        arg_str = '--config-dir {0} {1}'.format(self.get_config_dir(), arg_str)
        return self.run_script('salt-call', arg_str, with_retcode=with_retcode)


class ShellCaseCommonTestsMixIn(CheckShellBinaryNameAndVersionMixIn):

    _call_binary_expected_version_ = salt.__version__

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
                'Error: {0!r}'.format(
                    err
                )
            )

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info < __version_info__:
            self.skipTest(
                'We\'re likely about to release a new version. This test '
                'would fail. Parsed({0!r}) < Expected({1!r})'.format(
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
        elif isinstance(keys, basestring):
            # If it's a basestring , make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError('The passed keys need to be a list')
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        keys = self.__return_valid_keys(keys)
        okeys = keys[:]
        for part in ret.itervalues():
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    'Could not get ret{0} from salt\'s return: {1}'.format(
                        ''.join(['[{0!r}]'.format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        'Could not get ret{0} from salt\'s return: {1}'.format(
                            ''.join(['[{0!r}]'.format(k) for k in keys]), part
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
                        **(ret.values()[0])
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
                        **(ret.values()[0])
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
                        **(ret.values()[0])
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

    def assertInSalStatetWarning(self, in_comment, ret):
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
