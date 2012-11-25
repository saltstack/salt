'''
Set up the Salt integration test suite
'''

# Import Python libs
import optparse
import multiprocessing
import os
import sys
import shutil
import tempfile
import time
from datetime import datetime, timedelta
try:
    import pwd
except ImportError:
    pass

# Import Salt libs
import salt
import salt.config
import salt.master
import salt.minion
import salt.runner
from salt.utils import get_colors
from salt.utils.verify import verify_env
from saltunittest import TestCase, RedirectStdStreams

try:
    import console
    width, height = console.getTerminalSize()
    PNUM = width
except:
    PNUM = 70

if sys.version_info >= (2, 7):
    from subprocess import PIPE, Popen
    print('Using regular subprocess')
else:
    # Don't do import py27_subprocess as subprocess so within the remaining of
    # salt's source, whenever subprocess is imported, the proper one is used,
    # even in under python 2.6
    from py27_subprocess import PIPE, Popen
    print('Using copied 2.7 subprocess')


INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))
SCRIPT_DIR = os.path.join(CODE_DIR, 'scripts')

PYEXEC = 'python{0}.{1}'.format(sys.version_info[0], sys.version_info[1])

SYS_TMP_DIR = tempfile.gettempdir()
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
FILES = os.path.join(INTEGRATION_TEST_DIR, 'files')
MOCKBIN = os.path.join(INTEGRATION_TEST_DIR, 'mockbin')
MINIONS_CONNECT_TIMEOUT = MINIONS_SYNC_TIMEOUT = 60


def print_header(header, sep='~', top=True, bottom=True, inline=False,
                 centered=False):
    '''
    Allows some pretty printing of headers on the console, either with a
    "ruler" on bottom and/or top, inline, centered, etc.
    '''
    if top and not inline:
        print(sep * PNUM)

    if centered and not inline:
        fmt = u'{0:^{width}}'
    elif inline and not centered:
        fmt = u'{0:{sep}<{width}}'
    elif inline and centered:
        fmt = u'{0:{sep}^{width}}'
    else:
        fmt = u'{0}'
    print(fmt.format(header, sep=sep, width=PNUM))

    if bottom and not inline:
        print(sep * PNUM)


def run_tests(TestCase):
    '''
    Run integration tests for a chosen test case.

    Function uses optparse to set up test environment
    '''
    from saltunittest import TestLoader, TextTestRunner
    opts = parse_opts()
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestCase)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon(clean=opts.clean):
        runner = TextTestRunner(verbosity=opts.verbosity).run(tests)
        sys.exit(runner.wasSuccessful())


def parse_opts():
    '''
    Parse command line options for running integration tests
    '''
    parser = optparse.OptionParser()
    parser.add_option('-v',
            '--verbose',
            dest='verbosity',
            default=1,
            action='count',
            help='Verbose test runner output')
    parser.add_option('--clean',
            dest='clean',
            default=True,
            action='store_true',
            help=('Clean up test environment before and after '
                  'integration testing (default behaviour)'))
    parser.add_option('--no-clean',
            dest='clean',
            action='store_false',
            help=('Don\'t clean up test environment before and after '
                  'integration testing (speed up test process)'))
    options, _ = parser.parse_args()
    return options


class TestDaemon(object):
    '''
    Set up the master and minion daemons, and run related cases
    '''

    def __init__(self, opts=None):
        self.opts = opts
        self.colors = get_colors(opts.no_colors is False)

    def __enter__(self):
        '''
        Start a master and minion
        '''
        self.master_opts = salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )
        self.minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'minion')
        )
        self.sub_minion_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'sub_minion')
        )
        self.smaster_opts = salt.config.master_config(
            os.path.join(
                INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic_master'
            )
        )
        self.syndic_opts = salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'syndic'))
        self.syndic_opts['_master_conf_file'] = os.path.join(
            INTEGRATION_TEST_DIR,
            'files/conf/master'
        )
        # Set up config options that require internal data
        self.master_opts['pillar_roots'] = {
            'base': [os.path.join(FILES, 'pillar', 'base')]
        }
        self.master_opts['file_roots'] = {
            'base': [os.path.join(FILES, 'file', 'base')]
        }
        self.master_opts['ext_pillar'] = [
            {'cmd_yaml': 'cat {0}'.format(
                os.path.join(
                    FILES,
                    'ext.yaml'
                )
            )}
        ]
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
                    TMP
                    ],
                   pwd.getpwuid(os.getuid()).pw_name)

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

        #if os.environ.get('DUMP_SALT_CONFIG', None) is not None:
        #    try:
        #        import yaml
        #        os.makedirs('/tmp/salttest/conf')
        #    except OSError:
        #        pass
        #    self.master_opts['user'] = pwd.getpwuid(os.getuid()).pw_name
        #    self.minion_opts['user'] = pwd.getpwuid(os.getuid()).pw_name
        #    open('/tmp/salttest/conf/master', 'w').write(
        #        yaml.dump(self.master_opts)
        #    )
        #    open('/tmp/salttest/conf/minion', 'w').write(
        #        yaml.dump(self.minion_opts)
        #    )

        # Let's create a local client to ping and sync minions
        self.client = salt.client.LocalClient(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )

        evt_minions_connect = multiprocessing.Event()
        evt_minions_sync = multiprocessing.Event()
        minion_targets = set(['minion', 'sub_minion'])

        # Wait for minions to connect back
        wait_minions_connection = multiprocessing.Process(
            target=self.__wait_for_minions_connections,
            args=(evt_minions_connect, minion_targets)
        )
        wait_minions_connection.start()
        if evt_minions_connect.wait(MINIONS_CONNECT_TIMEOUT) is False:
            print('WARNING: Minions failed to connect back. Tests requiring '
                  'them WILL fail')
        wait_minions_connection.terminate()
        del(evt_minions_connect, wait_minions_connection)

        # Wait for minions to "sync_all"
        sync_minions = multiprocessing.Process(
            target=self.__sync_minions,
            args=(evt_minions_sync, minion_targets)
        )
        sync_minions.start()
        if evt_minions_sync.wait(MINIONS_SYNC_TIMEOUT) is False:
            print('WARNING: Minions failed to sync. Tests requiring the '
                  'testing `runtests_helper` module WILL fail')
        sync_minions.terminate()
        del(evt_minions_sync, sync_minions)

        if self.opts.sysinfo:
            from salt import version
            print_header('~~~~~~~ Versions Report ', inline=True)
            print('\n'.join(version.versions_report()))

            print_header(
                '~~~~~~~ Minion Grains Information ', inline=True,
            )
            grains = self.client.cmd('minion', 'grains.items')
            import pprint
            pprint.pprint(grains['minion'])

        print_header('', sep='=', inline=True)

        return self

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        self.sub_minion_process.terminate()
        self.minion_process.terminate()
        self.master_process.terminate()
        self.syndic_process.terminate()
        self.smaster_process.terminate()
        self._exit_mockbin()
        self._clean()

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
        if not self.opts.clean:
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
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        while now <= expire:
            running = self.__client_job_running(targets, jid)
            sys.stdout.write('\r' + ' ' * PNUM + '\r')
            if not running:
                print
                return True
            sys.stdout.write(
                '    * {YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                    '{0}'.format(expire - now).rsplit('.', 1)[0],
                    ', '.join(running),
                    **self.colors
                )
            )
            sys.stdout.flush()
            timeout -= 1
            time.sleep(1)
            now = datetime.now()
        else:
            sys.stdout.write('\n    * ERROR: Failed to get information back\n')
            sys.stdout.flush()
        return False

    def __client_job_running(self, targets, jid):
        running = self.client.cmd(
            ','.join(targets), 'saltutil.running', expr_form='list'
        )
        return [
            k for (k, v) in running.iteritems() if v and v[0]['jid'] == jid
        ]

    def __wait_for_minions_connections(self, evt, targets):
        print_header(
            'Waiting at most {0} secs for local minions to connect '
            'back and another {1} secs for them to '
            '"saltutil.sync_all()"'.format(
                MINIONS_CONNECT_TIMEOUT, MINIONS_SYNC_TIMEOUT
            ), sep='=', centered=True
        )
        targets = set(['minion', 'sub_minion'])
        expected_connections = set(targets)
        while True:
            # If enough time passes, a timeout will be triggered by
            # multiprocessing.Event, so, we can have this while True here
            targets = self.client.cmd('*', 'test.ping')
            for target in targets:
                if target not in expected_connections:
                    # Someone(minion) else "listening"?
                    continue
                expected_connections.remove(target)
                print('  * {0} minion connected'.format(target))
            if not expected_connections:
                # All expected connections have connected
                break
            time.sleep(1)
        evt.set()

    def __sync_minions(self, evt, targets):
        # Let's sync all connected minions
        print('  * Syncing local minion\'s dynamic data(saltutil.sync_all)')
        syncing = set(targets)
        jid_info = self.client.run_job(
            ','.join(targets), 'saltutil.sync_all',
            expr_form='list',
            timeout=9999999999999999,
        )

        if self.wait_for_jid(targets, jid_info['jid']) is False:
            evt.set()
            return

        while syncing:
            rdata = self.client.get_returns(jid_info['jid'], syncing, 1)
            if rdata:
                for idx, (name, output) in enumerate(rdata.iteritems()):
                    print('    * Synced {0}: {1}'.format(name, output))
                    # Synced!
                    try:
                        syncing.remove(name)
                    except KeyError:
                        print('    * {0} already synced???  {1}'.format(
                            name, output
                        ))
        evt.set()


class ModuleCase(TestCase):
    '''
    Execute a module function
    '''

    _client = None

    @property
    def client(self):
        if self._client is None:
            self._client = salt.client.LocalClient(
                os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
            )
        return self._client

    def minion_run(self, _function, *args, **kw):
        '''
        Run a single salt function on the 'minion' target and condition
        the return down to match the behavior of the raw function call
        '''
        return self.run_function(_function, args, **kw)

    def run_function(self, function, arg=(), minion_tgt='minion', **kwargs):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        know_to_return_none = ('file.chown', 'file.chgrp')
        orig = self.client.cmd(
            minion_tgt, function, arg, timeout=500, kwarg=kwargs
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

    def state_result(self, ret, raw=False):
        '''
        Return the result data from a single state return
        '''
        res = ret[next(iter(ret))]
        if raw:
            return res
        return res['result']

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
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'minion')
        )

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.minion_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'sub_minion')
        )

    @property
    def master_opts(self):
        '''
        Return the options used for the minion
        '''
        return salt.config.master_config(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )

    def assert_success(self, ret):
        try:
            res = self.state_result(ret, raw=True)
        except TypeError:
            pass
        else:
            if isinstance(res, dict):
                if res['result'] is True:
                    return
                if 'comment' in res:
                    raise AssertionError(res['comment'])
                ret = res
        raise AssertionError('bad result: %r' % (ret))


class SyndicCase(TestCase):
    '''
    Execute a syndic based execution test
    '''
    def setUp(self):
        '''
        Generate the tools to test a module
        '''
        self.client = salt.client.LocalClient(
            os.path.join(
                INTEGRATION_TEST_DIR,
                'files', 'conf', 'syndic_master'
            )
        )

    def run_function(self, function, arg=()):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg, timeout=500)
        if 'minion' not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion. Command output: {0}'.format(orig)
            )
        return orig['minion']


class ShellCase(TestCase):
    '''
    Execute a test for a shell command
    '''
    def run_script(self, script, arg_str, catch_stderr=False):
        '''
        Execute a script with the given argument string
        '''
        path = os.path.join(SCRIPT_DIR, script)
        if not os.path.isfile(path):
            return False
        ppath = 'PYTHONPATH={0}:{1}'.format(CODE_DIR, ':'.join(sys.path[1:]))
        cmd = '{0} {1} {2} {3}'.format(ppath, PYEXEC, path, arg_str)

        popen_kwargs = {
            'shell': True,
            'stdout': PIPE
        }

        if catch_stderr:
            popen_kwargs['stderr'] = PIPE

        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True

        process = Popen(cmd, **popen_kwargs)

        if catch_stderr:
            out, err = process.communicate()
            # Force closing stderr/stdout to release file descriptors
            process.stdout.close()
            process.stderr.close()
            try:
                return out.splitlines(), err.splitlines()
            finally:
                try:
                    process.terminate()
                except OSError, err:
                    # process already terminated
                    pass

        data = process.communicate()
        process.stdout.close()

        try:
            return data[0].splitlines()
        finally:
            try:
                process.terminate()
            except OSError, err:
                # process already terminated
                pass

    def run_salt(self, arg_str):
        '''
        Execute salt
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt', arg_str)

    def run_run(self, arg_str):
        '''
        Execute salt-run
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-run', arg_str)

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
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        )
        opts.update({'doc': False, 'fun': fun, 'arg': arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret['fun'] = runner.run()
        return ret

    def run_key(self, arg_str, catch_stderr=False):
        '''
        Execute salt-key
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
        arg_str = '-c {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-key', arg_str, catch_stderr=catch_stderr)

    def run_cp(self, arg_str):
        '''
        Execute salt-cp
        '''
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
        arg_str = '--config-dir {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-cp', arg_str)

    def run_call(self, arg_str):
        mconf = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf')
        arg_str = '--config-dir {0} {1}'.format(mconf, arg_str)
        return self.run_script('salt-call', arg_str)


class ShellCaseCommonTestsMixIn(object):

    def test_deprecated_config(self):
        """
        test for the --config deprecation warning

        Once --config is fully deprecated, this test can be removed

        """

        if getattr(self, '_call_binary_', None) is None:
            self.skipTest("'_call_binary_' not defined.")

        cfgfile = os.path.join(INTEGRATION_TEST_DIR, 'files', 'conf', 'master')
        out, err = self.run_script(
            self._call_binary_,
            '--config {0}'.format(cfgfile),
            catch_stderr=True
        )
        self.assertIn('Usage: {0}'.format(self._call_binary_), '\n'.join(err))
        self.assertIn('deprecated', '\n'.join(err))

    def test_version_includes_binary_name(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest("'_call_binary_' not defined.")

        out = '\n'.join(self.run_script(self._call_binary_, "--version"))
        self.assertIn(self._call_binary_, out)
        self.assertIn(salt.__version__, out)


class SaltReturnAssertsMixIn(object):

    def __assertReturn(self, ret, which_case):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                '{0} is not dict. Salt returned: {1}'.format(
                    type(ret), ret
                )
            )

        try:
            self.assertNotEqual(ret, {})
        except AssertionError:
            raise AssertionError(
                '{} is equal to {}. Salt returned an empty dictionary.'
            )

        for part in ret.itervalues():
            try:
                self.assertTrue(isinstance(part, dict))
            except AssertionError:
                raise AssertionError(
                    '{0} is not dict. Salt returned: {1}'.format(
                        type(part), part
                    )
                )
            try:
                if which_case is True:
                    self.assertTrue(part['result'])
                elif which_case is False:
                    self.assertFalse(part['result'])
                elif which_case is None:
                    self.assertIsNone(part['result'])
            except AssertionError:
                raise AssertionError(
                    '{result} is not {0}. Salt Comment:\n{comment}'.format(
                        which_case, **part
                    )
                )

    def assertSaltTrueReturn(self, ret):
        self.__assertReturn(ret, True)

    def assertSaltFalseReturn(self, ret):
        self.__assertReturn(ret, False)

    def assertSaltNoneReturn(self, ret):
        self.__assertReturn(ret, None)
