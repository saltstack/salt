# -*- coding: utf-8 -*-
'''
    tests.support.parser
    ~~~~~~~~~~~~~~~~~~~~

    Salt Tests CLI access classes

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013-2017 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''
# pylint: disable=repr-flag-used-in-string

from __future__ import absolute_import, print_function
import os
import sys
import time
import signal
import shutil
import logging
import platform
import optparse
import tempfile
import traceback
import subprocess
import warnings
from functools import partial
from contextlib import closing
from collections import namedtuple

from tests.support import helpers
from tests.support.unit import TestLoader, TextTestRunner
from tests.support.xmlunit import HAS_XMLRUNNER, XMLTestRunner

# Import 3rd-party libs
import salt.ext.six as six
try:
    from tests.support.ext import console
    WIDTH, HEIGHT = console.getTerminalSize()
    PNUM = WIDTH
except Exception:  # pylint: disable=broad-except
    PNUM = 70

log = logging.getLogger(__name__)

# This is a completely random and meaningful number intended to identify our
# own signal triggering.
WEIRD_SIGNAL_NUM = -45654


# Let's setup a global exception hook handler which will log all exceptions
# Store a reference to the original handler
__GLOBAL_EXCEPTION_HANDLER = sys.excepthook


def __global_logging_exception_handler(exc_type, exc_value, exc_traceback):
    '''
    This function will log all python exceptions.
    '''
    # Log the exception
    logging.getLogger(__name__).error(
        'An un-handled exception was caught by salt-testing\'s global '
        'exception handler:\n{0}: {1}\n{2}'.format(
            exc_type.__name__,
            exc_value,
            ''.join(traceback.format_exception(
                exc_type, exc_value, exc_traceback
            )).strip()
        )
    )
    # Call the original sys.excepthook
    __GLOBAL_EXCEPTION_HANDLER(exc_type, exc_value, exc_traceback)


# Set our own exception handler as the one to use
sys.excepthook = __global_logging_exception_handler

TestsuiteResult = namedtuple('TestsuiteResult', ['header', 'errors', 'skipped', 'failures', 'passed'])
TestResult = namedtuple('TestResult', ['id', 'reason'])


def print_header(header, sep='~', top=True, bottom=True, inline=False,
                 centered=False, width=PNUM):
    '''
    Allows some pretty printing of headers on the console, either with a
    "ruler" on bottom and/or top, inline, centered, etc.
    '''
    if top and not inline:
        print(sep * width)

    if centered and not inline:
        fmt = u'{0:^{width}}'
    elif inline and not centered:
        fmt = u'{0:{sep}<{width}}'
    elif inline and centered:
        fmt = u'{0:{sep}^{width}}'
    else:
        fmt = u'{0}'
    print(fmt.format(header, sep=sep, width=width))

    if bottom and not inline:
        print(sep * width)


class SaltTestingParser(optparse.OptionParser):
    support_docker_execution = False
    support_destructive_tests_selection = False
    support_expensive_tests_selection = False
    source_code_basedir = None

    _known_interpreters = {
        'salttest/arch': 'python2',
        'salttest/centos-5': 'python2.6',
        'salttest/centos-6': 'python2.6',
        'salttest/debian-7': 'python2.7',
        'salttest/opensuse-12.3': 'python2.7',
        'salttest/ubuntu-12.04': 'python2.7',
        'salttest/ubuntu-12.10': 'python2.7',
        'salttest/ubuntu-13.04': 'python2.7',
        'salttest/ubuntu-13.10': 'python2.7',
        'salttest/py3': 'python3'
    }

    def __init__(self, testsuite_directory, *args, **kwargs):
        if kwargs.pop('html_output_from_env', None) is not None or \
                kwargs.pop('html_output_dir', None) is not None:
            warnings.warn(
                'The unit tests HTML support was removed from {0}. Please '
                'stop passing \'html_output_dir\' or \'html_output_from_env\' '
                'as arguments to {0}'.format(self.__class__.__name__),
                category=DeprecationWarning,
                stacklevel=2
            )

        # Get XML output settings
        xml_output_dir_env_var = kwargs.pop(
            'xml_output_from_env',
            'XML_TESTS_OUTPUT_DIR'
        )
        xml_output_dir = kwargs.pop('xml_output_dir', None)

        if xml_output_dir_env_var in os.environ:
            xml_output_dir = os.environ.get(xml_output_dir_env_var)
        if not xml_output_dir:
            xml_output_dir = os.path.join(
                tempfile.gettempdir() if platform.system() != 'Darwin' else '/tmp',
                'xml-tests-output'
            )
        self.xml_output_dir = xml_output_dir

        # Get the desired logfile to use while running tests
        self.tests_logfile = kwargs.pop('tests_logfile', None)

        optparse.OptionParser.__init__(self, *args, **kwargs)
        self.testsuite_directory = testsuite_directory
        self.testsuite_results = []

        self.test_selection_group = optparse.OptionGroup(
            self,
            'Tests Selection Options',
            'Select which tests are to be executed'
        )
        if self.support_destructive_tests_selection is True:
            self.test_selection_group.add_option(
                '--run-destructive',
                action='store_true',
                default=False,
                help=('Run destructive tests. These tests can include adding '
                      'or removing users from your system for example. '
                      'Default: %default')
            )
        if self.support_expensive_tests_selection is True:
            self.test_selection_group.add_option(
                '--run-expensive',
                action='store_true',
                default=False,
                help=('Run expensive tests. Expensive tests are any tests that, '
                      'once configured, cost money to run, such as creating or '
                      'destroying cloud instances on a cloud provider.')
            )

        self.test_selection_group.add_option(
            '-n',
            '--name',
            dest='name',
            action='append',
            default=None,
            help=('Specific test name to run. A named test is the module path '
                  'relative to the tests directory')
        )
        self.test_selection_group.add_option(
            '--names-file',
            dest='names_file',
            default=None,
            help=('The location of a newline delimited file of test names to '
                  'run')
        )
        self.add_option_group(self.test_selection_group)

        if self.support_docker_execution is True:
            self.docked_selection_group = optparse.OptionGroup(
                self,
                'Docked Tests Execution',
                'Run the tests suite under a Docker container. This allows, '
                'for example, to run destructive tests on your machine '
                'without actually breaking it in any way.'
            )
            self.docked_selection_group.add_option(
                '--docked',
                default=None,
                metavar='CONTAINER',
                help='Run the tests suite in the chosen Docker container'
            )
            self.docked_selection_group.add_option(
                '--docked-interpreter',
                default=None,
                metavar='PYTHON_INTERPRETER',
                help='The python binary name to use when calling the tests '
                     'suite.'
            )
            self.docked_selection_group.add_option(
                '--docked-skip-delete',
                default=False,
                action='store_true',
                help='Skip docker container deletion on exit. Default: False'
            )
            self.docked_selection_group.add_option(
                '--docked-skip-delete-on-errors',
                default=False,
                action='store_true',
                help='Skip docker container deletion on exit if errors '
                     'occurred. Default: False'
            )
            self.docked_selection_group.add_option(
                '--docker-binary',
                help='The docker binary on the host system. Default: %default',
                default='/usr/bin/docker',
            )
            self.add_option_group(self.docked_selection_group)

        self.output_options_group = optparse.OptionGroup(
            self, 'Output Options'
        )
        self.output_options_group.add_option(
            '-v',
            '--verbose',
            dest='verbosity',
            default=1,
            action='count',
            help='Verbose test runner output'
        )
        self.output_options_group.add_option(
            '--output-columns',
            default=PNUM,
            type=int,
            help='Number of maximum columns to use on the output'
        )
        self.output_options_group.add_option(
            '--tests-logfile',
            default=self.tests_logfile,
            help='The path to the tests suite logging logfile'
        )
        if self.xml_output_dir is not None:
            self.output_options_group.add_option(
                '-x',
                '--xml',
                '--xml-out',
                dest='xml_out',
                default=False,
                help='XML test runner output(Output directory: {0})'.format(
                    self.xml_output_dir
                )
            )
        self.output_options_group.add_option(
            '--no-report',
            default=False,
            action='store_true',
            help='Do NOT show the overall tests result'
        )
        self.add_option_group(self.output_options_group)

        self.fs_cleanup_options_group = optparse.OptionGroup(
            self, 'File system cleanup Options'
        )
        self.fs_cleanup_options_group.add_option(
            '--clean',
            dest='clean',
            default=True,
            action='store_true',
            help=('Clean up test environment before and after running the '
                  'tests suite (default behaviour)')
        )
        self.fs_cleanup_options_group.add_option(
            '--no-clean',
            dest='clean',
            action='store_false',
            help=('Don\'t clean up test environment before and after the '
                  'tests suite execution (speed up test process)')
        )
        self.add_option_group(self.fs_cleanup_options_group)
        self.setup_additional_options()

    def parse_args(self, args=None, values=None):
        self.options, self.args = optparse.OptionParser.parse_args(self, args, values)
        if self.options.names_file:
            with open(self.options.names_file, 'rb') as fp_:
                lines = []
                for line in fp_.readlines():
                    if six.PY2:
                        lines.append(line.strip())
                    else:
                        lines.append(
                            line.decode(__salt_system_encoding__).split())
            if self.options.name:
                self.options.name.extend(lines)
            else:
                self.options.name = lines
        if self.args:
            if not self.options.name:
                self.options.name = []
            for fpath in self.args:
                if os.path.isfile(fpath) and \
                        fpath.endswith('.py') and \
                        os.path.basename(fpath).startswith('test_'):
                    self.options.name.append(fpath)
                    continue
                self.exit(status=1, msg='\'{}\' is not a valid test module'.format(fpath))

        print_header(u'', inline=True, width=self.options.output_columns)
        self.pre_execution_cleanup()

        if self.support_docker_execution and self.options.docked is not None:
            if self.source_code_basedir is None:
                raise RuntimeError(
                    'You need to define the \'source_code_basedir\' attribute '
                    'in {0!r}.'.format(self.__class__.__name__)
                )

            if '/' not in self.options.docked:
                self.options.docked = 'salttest/{0}'.format(
                    self.options.docked
                )

            if self.options.docked_interpreter is None:
                self.options.docked_interpreter = self._known_interpreters.get(
                    self.options.docked, 'python'
                )

            # No more processing should be done. We'll exit with the return
            # code we get from the docker container execution
            self.exit(self.run_suite_in_docker())

        # Validate options after checking that we're not goint to execute the
        # tests suite under a docker container
        self._validate_options()

        print(' * Current Directory: {0}'.format(os.getcwd()))
        print(' * Test suite is running under PID {0}'.format(os.getpid()))

        self._setup_logging()
        try:
            return (self.options, self.args)
        finally:
            print_header(u'', inline=True, width=self.options.output_columns)

    def setup_additional_options(self):
        '''
        Subclasses should add additional options in this overridden method
        '''

    def _validate_options(self):
        '''
        Validate the default available options
        '''
        if self.xml_output_dir is not None and self.options.xml_out and HAS_XMLRUNNER is False:
            self.error(
                '\'--xml\' is not available. The xmlrunner library is not '
                'installed.'
            )

        if self.options.xml_out:
            # Override any environment setting with the passed value
            self.xml_output_dir = self.options.xml_out

        if self.xml_output_dir is not None and self.options.xml_out:
            if not os.path.isdir(self.xml_output_dir):
                os.makedirs(self.xml_output_dir)
            print(
                ' * Generated unit test XML reports will be stored '
                'at {0!r}'.format(self.xml_output_dir)
            )

        self.validate_options()

        if self.support_destructive_tests_selection:
            # Set the required environment variable in order to know if
            # destructive tests should be executed or not.
            os.environ['DESTRUCTIVE_TESTS'] = str(self.options.run_destructive)

        if self.support_expensive_tests_selection:
            # Set the required environment variable in order to know if
            # expensive tests should be executed or not.
            os.environ['EXPENSIVE_TESTS'] = str(self.options.run_expensive)

    def validate_options(self):
        '''
        Validate the provided options. Override this method to run your own
        validation procedures.
        '''

    def _setup_logging(self):
        '''
        Setup python's logging system to work with/for the tests suite
        '''
        # Setup tests logging
        formatter = logging.Formatter(
            '%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d]'
            '[%(levelname)-8s] %(message)s',
            datefmt='%H:%M:%S'
        )
        if not hasattr(logging, 'TRACE'):
            logging.TRACE = 5
            logging.addLevelName(logging.TRACE, 'TRACE')
        if not hasattr(logging, 'GARBAGE'):
            logging.GARBAGE = 1
            logging.addLevelName(logging.GARBAGE, 'GARBAGE')

        # Default logging level: ERROR
        logging.root.setLevel(logging.NOTSET)

        if self.options.tests_logfile:
            filehandler = logging.FileHandler(
                mode='w',           # Not preserved between re-runs
                filename=self.options.tests_logfile
            )
            # The logs of the file are the most verbose possible
            filehandler.setLevel(logging.DEBUG)
            filehandler.setFormatter(formatter)
            logging.root.addHandler(filehandler)

            print(' * Logging tests on {0}'.format(self.options.tests_logfile))

        # With greater verbosity we can also log to the console
        if self.options.verbosity >= 2:
            consolehandler = logging.StreamHandler(sys.stderr)
            consolehandler.setFormatter(formatter)
            if self.options.verbosity >= 6:     # -vvvvv
                logging_level = logging.GARBAGE
            elif self.options.verbosity == 5:   # -vvvv
                logging_level = logging.TRACE
            elif self.options.verbosity == 4:   # -vvv
                logging_level = logging.DEBUG
                print('DEBUG')
            elif self.options.verbosity == 3:   # -vv
                print('INFO')
                logging_level = logging.INFO
            else:
                logging_level = logging.ERROR
            consolehandler.setLevel(logging_level)
            logging.root.addHandler(consolehandler)
            log.info('Runtests logging has been setup')

    def pre_execution_cleanup(self):
        '''
        Run any initial clean up operations. If sub-classed, don't forget to
        call SaltTestingParser.pre_execution_cleanup(self) from the overridden
        method.
        '''
        if self.options.clean is True:
            for path in (self.xml_output_dir,):
                if path is None:
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path)

    def run_suite(self, path, display_name, suffix='test_*.py',
                  load_from_name=False, additional_test_dirs=None):
        '''
        Execute a unit test suite
        '''
        loaded_custom = False
        loader = TestLoader()
        try:
            if load_from_name:
                tests = loader.loadTestsFromName(display_name)
            else:
                if additional_test_dirs is None or self.testsuite_directory.startswith(path):
                    tests = loader.discover(path, suffix, self.testsuite_directory)
                else:
                    tests = loader.discover(path, suffix)
                    loaded_custom = True
        except (AttributeError, ImportError):
            print('Could not locate test \'{0}\'. Exiting.'.format(display_name))
            sys.exit(1)

        if additional_test_dirs and not loaded_custom:
            for test_dir in additional_test_dirs:
                additional_tests = loader.discover(test_dir, suffix, test_dir)
                tests.addTests(additional_tests)

        header = '{0} Tests'.format(display_name)
        print_header('Starting {0}'.format(header),
                     width=self.options.output_columns)

        if self.options.xml_out:
            runner = XMLTestRunner(
                stream=sys.stdout,
                output=self.xml_output_dir,
                verbosity=self.options.verbosity
            ).run(tests)
        else:
            runner = TextTestRunner(
                stream=sys.stdout,
                verbosity=self.options.verbosity).run(tests)

        errors = []
        skipped = []
        failures = []
        for testcase, reason in runner.errors:
            errors.append(TestResult(testcase.id(), reason))
        for testcase, reason in runner.skipped:
            skipped.append(TestResult(testcase.id(), reason))
        for testcase, reason in runner.failures:
            failures.append(TestResult(testcase.id(), reason))
        self.testsuite_results.append(
            TestsuiteResult(header,
                            errors,
                            skipped,
                            failures,
                            runner.testsRun - len(errors + skipped + failures))
        )
        success = runner.wasSuccessful()
        del loader
        del runner
        return success

    def print_overall_testsuite_report(self):
        '''
        Print a nicely formatted report about the test suite results
        '''
        print()
        print_header(
            u'  Overall Tests Report  ', sep=u'=', centered=True, inline=True,
            width=self.options.output_columns
        )

        failures = errors = skipped = passed = 0
        no_problems_found = True
        for results in self.testsuite_results:
            failures += len(results.failures)
            errors += len(results.errors)
            skipped += len(results.skipped)
            passed += results.passed

            if not results.failures and not results.errors and not results.skipped:
                continue

            no_problems_found = False

            print_header(
                u'*** {0}  '.format(results.header), sep=u'*', inline=True,
                width=self.options.output_columns
            )
            if results.skipped:
                print_header(
                    u' --------  Skipped Tests  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                maxlen = len(
                    max([testcase.id for testcase in results.skipped], key=len)
                )
                fmt = u'   -> {0: <{maxlen}}  ->  {1}'
                for testcase in results.skipped:
                    print(fmt.format(testcase.id, testcase.reason, maxlen=maxlen))
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

            if results.errors:
                print_header(
                    u' --------  Tests with Errors  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                for testcase in results.errors:
                    print_header(
                        u'   -> {0}  '.format(testcase.id),
                        sep=u'.', inline=True,
                        width=self.options.output_columns
                    )
                    for line in testcase.reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True,
                                 width=self.options.output_columns)
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

            if results.failures:
                print_header(
                    u' --------  Failed Tests  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                for testcase in results.failures:
                    print_header(
                        u'   -> {0}  '.format(testcase.id),
                        sep=u'.', inline=True,
                        width=self.options.output_columns
                    )
                    for line in testcase.reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True,
                                 width=self.options.output_columns)
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

        if no_problems_found:
            print_header(
                u'***  No Problems Found While Running Tests  ',
                sep=u'*', inline=True, width=self.options.output_columns
            )

        print_header(u'', sep=u'=', inline=True,
                     width=self.options.output_columns)
        total = sum([passed, skipped, errors, failures])
        print(
            '{0} (total={1}, skipped={2}, passed={3}, failures={4}, '
            'errors={5}) '.format(
                (errors or failures) and 'FAILED' or 'OK',
                total, skipped, passed, failures, errors
            )
        )
        print_header(
            '  Overall Tests Report  ', sep='=', centered=True, inline=True,
            width=self.options.output_columns
        )

    def post_execution_cleanup(self):
        '''
        Run any final clean-up operations.  If sub-classed, don't forget to
        call SaltTestingParser.post_execution_cleanup(self) from the overridden
        method.
        '''

    def finalize(self, exit_code=0):
        '''
        Run the finalization procedures. Show report, clean-up file-system, etc
        '''
        # Collect any child processes still laying around
        children = helpers.collect_child_processes(os.getpid())
        if self.options.no_report is False:
            self.print_overall_testsuite_report()
        self.post_execution_cleanup()
        # Brute force approach to terminate this process and its children
        if children:
            log.info('Terminating test suite child processes: %s', children)
            helpers.terminate_process(children=children, kill_children=True)
            children = helpers.collect_child_processes(os.getpid())
            if children:
                log.info('Second run at terminating test suite child processes: %s', children)
                helpers.terminate_process(children=children, kill_children=True)
        log.info(
            'Test suite execution finalized with exit code: {0}'.format(
                exit_code
            )
        )
        self.exit(exit_code)

    def run_suite_in_docker(self):
        '''
        Run the tests suite in a Docker container
        '''
        def stop_running_docked_container(cid, signum=None, frame=None):
            # Allow some time for the container to stop if it's going to be
            # stopped by docker or any signals docker might have received
            time.sleep(0.5)

            print_header('', inline=True, width=self.options.output_columns)

            # Let's check if, in fact, the container is stopped
            scode_call = subprocess.Popen(
                [self.options.docker_binary, 'inspect', '--format={{.State.Running}}', cid],
                env=os.environ.copy(),
                close_fds=True,
                stdout=subprocess.PIPE
            )
            scode_call.wait()
            parsed_scode = scode_call.stdout.read().strip()
            if six.PY3:
                parsed_scode = parsed_scode.decode(__salt_system_encoding__)
            if parsed_scode != 'false':
                # If the container is still running, let's make sure it
                # properly stops
                sys.stdout.write(' * Making sure the container is stopped. CID: ')
                sys.stdout.flush()

                stop_call = subprocess.Popen(
                    [self.options.docker_binary, 'stop', '--time=15', cid],
                    env=os.environ.copy(),
                    close_fds=True,
                    stdout=subprocess.PIPE
                )
                stop_call.wait()
                output = stop_call.stdout.read().strip()
                if six.PY3:
                    output = output.decode(__salt_system_encoding__)
                print(output)
                sys.stdout.flush()
                time.sleep(0.5)

            # Let's get the container's exit code. We can't trust on Popen's
            # returncode because it's not reporting the proper one? Still
            # haven't narrowed it down why.
            sys.stdout.write(' * Container exit code: ')
            sys.stdout.flush()
            rcode_call = subprocess.Popen(
                [self.options.docker_binary, 'inspect', '--format={{.State.ExitCode}}', cid],
                env=os.environ.copy(),
                close_fds=True,
                stdout=subprocess.PIPE
            )
            rcode_call.wait()
            parsed_rcode = rcode_call.stdout.read().strip()
            if six.PY3:
                parsed_rcode = parsed_rcode.decode(__salt_system_encoding__)
            try:
                returncode = int(parsed_rcode)
            except ValueError:
                returncode = -1
            print(parsed_rcode)
            sys.stdout.flush()

            if self.options.docked_skip_delete is False and \
                    (self.options.docked_skip_delete_on_errors is False or
                     (self.options.docked_skip_delete_on_error and returncode == 0)):
                sys.stdout.write(' * Cleaning Up Temporary Docker Container. CID: ')
                sys.stdout.flush()
                cleanup_call = subprocess.Popen(
                    [self.options.docker_binary, 'rm', cid],
                    env=os.environ.copy(),
                    close_fds=True,
                    stdout=subprocess.PIPE
                )
                cleanup_call.wait()
                output = cleanup_call.stdout.read().strip()
                if six.PY3:
                    output = output.decode(__salt_system_encoding__)
                print(output)

            if 'DOCKER_CIDFILE' not in os.environ:
                # The CID file was not created "from the outside", so delete it
                os.unlink(cidfile)

            print_header('', inline=True, width=self.options.output_columns)
            # Finally, EXIT!
            sys.exit(returncode)

        # Let's start the Docker container and run the tests suite there
        if '/' not in self.options.docked:
            container = 'salttest/{0}'.format(self.options.docked)
        else:
            container = self.options.docked

        calling_args = [self.options.docked_interpreter,
                        '/salt-source/tests/runtests.py']
        for option in self._get_all_options():
            if option.dest is None:
                # For example --version
                continue

            if option.dest and (option.dest in ('verbosity',) or
                                option.dest.startswith('docked')):
                # We don't need to pass any docker related arguments inside the
                # container, and verbose will be handled bellow
                continue

            default = self.defaults.get(option.dest)
            value = getattr(self.options, option.dest, default)

            if default == value:
                # This is the default value, no need to pass the option to the
                # parser
                continue

            if option.action.startswith('store_'):
                calling_args.append(option.get_opt_string())

            elif option.action == 'append':
                for val in value is not None and value or default:
                    calling_args.extend([option.get_opt_string(), str(val)])
            elif option.action == 'count':
                calling_args.extend([option.get_opt_string()] * value)
            else:
                calling_args.extend(
                    [option.get_opt_string(),
                     str(value is not None and value or default)]
                )

        if not self.options.run_destructive:
            calling_args.append('--run-destructive')

        if self.options.verbosity > 1:
            calling_args.append(
                '-{0}'.format('v' * (self.options.verbosity - 1))
            )

        sys.stdout.write(' * Docker command: {0}\n'.format(' '.join(calling_args)))
        sys.stdout.write(' * Running the tests suite under the {0!r} docker '
                         'container. CID: '.format(container))
        sys.stdout.flush()

        cidfile = os.environ.get(
            'DOCKER_CIDFILE',
            tempfile.mktemp(prefix='docked-testsuite-', suffix='.cid')
        )
        call = subprocess.Popen(
            [self.options.docker_binary,
             'run',
             # '--rm=true', Do not remove the container automatically, we need
             #              to get information back, even for stopped containers
             '--tty',
             '--interactive',
             '-v',
             '{0}:/salt-source'.format(self.source_code_basedir),
             '-w',
             '/salt-source',
             '-e',
             'SHELL=/bin/sh',
             '-e',
             'COLUMNS={0}'.format(WIDTH),
             '-e',
             'LINES={0}'.format(HEIGHT),
             '--cidfile={0}'.format(cidfile),
             container,
             # We need to pass the runtests.py arguments as a single string so
             # that the start-me-up.sh script can handle them properly
             ' '.join(calling_args),
             ],
            env=os.environ.copy(),
            close_fds=True,
        )

        cid = None
        cid_printed = terminating = exiting = False
        signal_handler_installed = signalled = False

        time.sleep(0.25)

        while True:
            try:
                time.sleep(0.15)
                if cid_printed is False:
                    with closing(open(cidfile)) as cidfile_fd:
                        cid = cidfile_fd.read()
                        if cid:
                            print(cid)
                            sys.stdout.flush()
                            cid_printed = True
                            # Install our signal handler to properly shutdown
                            # the docker container
                            for sig in (signal.SIGTERM, signal.SIGINT,
                                        signal.SIGHUP, signal.SIGQUIT):
                                signal.signal(
                                    sig,
                                    partial(stop_running_docked_container, cid)
                                )
                            signal_handler_installed = True

                if exiting:
                    break
                elif terminating and not exiting:
                    exiting = True
                    call.kill()
                    break
                elif signalled and not terminating:
                    terminating = True
                    call.terminate()
                else:
                    call.poll()
                    if call.returncode is not None:
                        # Finished
                        break
            except KeyboardInterrupt:
                print('Caught CTRL-C, exiting...')
                signalled = True
                call.send_signal(signal.SIGINT)

        call.wait()
        time.sleep(0.25)

        # Finish up
        if signal_handler_installed:
            stop_running_docked_container(
                cid,
                signum=(signal.SIGINT if signalled else WEIRD_SIGNAL_NUM)
            )
        else:
            sys.exit(call.returncode)


class SaltTestcaseParser(SaltTestingParser):
    '''
    Option parser to run one or more ``unittest.case.TestCase``, ie, no
    discovery involved.
    '''
    def __init__(self, *args, **kwargs):
        SaltTestingParser.__init__(self, None, *args, **kwargs)
        self.usage = '%prog [options]'
        self.option_groups.remove(self.test_selection_group)
        if self.has_option('--xml-out'):
            self.remove_option('--xml-out')

    def get_prog_name(self):
        return '{0} {1}'.format(sys.executable.split(os.sep)[-1], sys.argv[0])

    def run_testcase(self, testcase):
        '''
        Run one or more ``unittest.case.TestCase``
        '''
        header = ''
        loader = TestLoader()
        if isinstance(testcase, list):
            for case in testcase:
                tests = loader.loadTestsFromTestCase(case)
        else:
            tests = loader.loadTestsFromTestCase(testcase)

        if not isinstance(testcase, list):
            header = '{0} Tests'.format(testcase.__name__)
            print_header('Starting {0}'.format(header),
                         width=self.options.output_columns)

        runner = TextTestRunner(
            verbosity=self.options.verbosity).run(tests)
        self.testsuite_results.append((header, runner))
        return runner.wasSuccessful()
