# -*- coding: utf-8 -*-
'''
    tests.support.parser
    ~~~~~~~~~~~~~~~~~~~~

    Salt Tests CLI access classes

    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :copyright: Copyright 2013-2017 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''
# pylint: disable=repr-flag-used-in-string

from __future__ import absolute_import, print_function
import fnmatch
import os
import sys
import time
import signal
import shutil
import logging
import platform
import optparse
import re
import tempfile
import traceback
import subprocess
import warnings
from functools import partial
from collections import namedtuple

import tests.support.paths
from tests.support import helpers
from tests.support.unit import TestLoader, TextTestRunner
from tests.support.xmlunit import HAS_XMLRUNNER, XMLTestRunner

# Import 3rd-party libs
from salt.ext import six
import salt.utils.data
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.yaml

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


def __global_logging_exception_handler(exc_type, exc_value, exc_traceback,
                                       _logger=logging.getLogger(__name__),
                                       _stderr=sys.__stderr__,
                                       _format_exception=traceback.format_exception):
    '''
    This function will log all python exceptions.
    '''
    if exc_type.__name__ == "KeyboardInterrupt":
        # Call the original sys.excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Log the exception
    try:
        msg = (
            'An un-handled exception was caught by salt\'s testing global exception handler:\n{}: {}\n{}'.format(
                exc_type.__name__,
                exc_value,
                ''.join(_format_exception(exc_type, exc_value, exc_traceback)).strip()
            )
        )
    except Exception:  # pylint: disable=broad-except
        msg = (
            'An un-handled exception was caught by salt-testing\'s global exception handler:\n{}: {}\n'
            '(UNABLE TO FORMAT TRACEBACK)'.format(
                exc_type.__name__,
                exc_value,
            )
        )
    try:
        _logger(__name__).error(msg)
    except Exception:  # pylint: disable=broad-except
        # Python is shutting down and logging has been set to None already
        try:
            _stderr.write(msg + '\n')
        except Exception:  # pylint: disable=broad-except
            # We have also lost reference to sys.__stderr__ ?!
            print(msg)

    # Call the original sys.excepthook
    try:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    except Exception:  # pylint: disable=broad-except
        # Python is shutting down and sys has been set to None already
        pass


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
            default=[],
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
        self.test_selection_group.add_option(
            '--from-filenames',
            dest='from_filenames',
            action='append',
            default=None,
            help=('Pass a comma-separated list of file paths, and any '
                  'unit/integration test module which corresponds to the '
                  'specified file(s) will be run. For example, a path of '
                  'salt/modules/git.py would result in unit.modules.test_git '
                  'and integration.modules.test_git being run. Absolute paths '
                  'are assumed to be files containing relative paths, one per '
                  'line. Providing the paths in a file can help get around '
                  'shell character limits when the list of files is long.')
        )
        self.test_selection_group.add_option(
            '--filename-map',
            dest='filename_map',
            default=None,
            help=('Path to a YAML file mapping paths/path globs to a list '
                  'of test names to run. See tests/filename_map.yml '
                  'for example usage (when --from-filenames is used, this '
                  'map file will be the default one used).')
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
            '-F',
            '--fail-fast',
            dest='failfast',
            default=False,
            action='store_true',
            help='Stop on first failure'
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

    @staticmethod
    def _expand_paths(paths):
        '''
        Expand any comma-separated lists of paths, and return a set of all
        paths to ensure there are no duplicates.
        '''
        ret = set()
        for path in paths:
            for item in [x.strip() for x in path.split(',')]:
                if not item:
                    continue
                elif os.path.isabs(item):
                    try:
                        with salt.utils.files.fopen(item, 'rb') as fp_:
                            for line in fp_:
                                line = salt.utils.stringutils.to_unicode(line.strip())
                                if os.path.isabs(line):
                                    log.warning(
                                        'Invalid absolute path %s in %s, '
                                        'ignoring', line, item
                                    )
                                else:
                                    ret.add(line)
                    except (IOError, OSError) as exc:
                        log.error('Failed to read from %s: %s', item, exc)
                else:
                    ret.add(item)
        return ret

    @property
    def _test_mods(self):
        '''
        Use the test_mods generator to get all of the test module names, and
        then store them in a set so that further references to this attribute
        will not need to re-walk the test dir.
        '''
        try:
            return self.__test_mods
        except AttributeError:
            self.__test_mods = set(tests.support.paths.list_test_mods())
            return self.__test_mods

    def _map_files(self, files):
        '''
        Map the passed paths to test modules, returning a set of the mapped
        module names.
        '''
        ret = set()

        if self.options.filename_map is not None:
            try:
                with salt.utils.files.fopen(self.options.filename_map) as fp_:
                    filename_map = salt.utils.yaml.safe_load(fp_)
            except Exception as exc:
                raise RuntimeError(
                    'Failed to load filename map: {0}'.format(exc)
                )
        else:
            filename_map = {}

        def _add(comps):
            '''
            Helper to add unit and integration tests matching a given mod path
            '''
            mod_relname = '.'.join(comps)
            ret.update(
                x for x in
                ['.'.join(('unit', mod_relname)),
                 '.'.join(('integration', mod_relname)),
                 '.'.join(('multimaster', mod_relname))]
                if x in self._test_mods
            )

        # First, try a path match
        for path in files:
            match = re.match(r'^(salt/|tests/(unit|integration|multimaster)/)(.+\.py)$', path)
            if match:
                comps = match.group(3).split('/')

                # Find matches for a source file
                if match.group(1) == 'salt/':
                    if comps[-1] == '__init__.py':
                        comps.pop(-1)
                        comps[-1] = 'test_' + comps[-1]
                    else:
                        comps[-1] = 'test_{0}'.format(comps[-1][:-3])

                    # Direct name matches
                    _add(comps)

                    # State matches for execution modules of the same name
                    # (e.g. unit.states.test_archive if
                    # unit.modules.test_archive is being run)
                    try:
                        if comps[-2] == 'modules':
                            comps[-2] = 'states'
                            _add(comps)
                    except IndexError:
                        # Not an execution module. This is either directly in
                        # the salt/ directory, or salt/something/__init__.py
                        pass

                # Make sure to run a test module if it's been modified
                elif match.group(1).startswith('tests/'):
                    comps.insert(0, match.group(2))
                    if fnmatch.fnmatch(comps[-1], 'test_*.py'):
                        comps[-1] = comps[-1][:-3]
                        test_name = '.'.join(comps)
                        if test_name in self._test_mods:
                            ret.add(test_name)

        # Next, try the filename_map
        for path_expr in filename_map:
            for filename in files:
                if salt.utils.stringutils.expr_match(filename, path_expr):
                    ret.update(filename_map[path_expr])
                    break

        if any(x.startswith('integration.proxy.') for x in ret):
            # Ensure that the salt-proxy daemon is started for these tests.
            self.options.proxy = True

        if any(x.startswith('integration.ssh.') for x in ret):
            # Ensure that an ssh daemon is started for these tests.
            self.options.ssh = True

        return ret

    def parse_args(self, args=None, values=None):
        self.options, self.args = optparse.OptionParser.parse_args(self, args, values)

        file_names = []
        if self.options.names_file:
            with open(self.options.names_file, 'rb') as fp_:  # pylint: disable=resource-leakage
                for line in fp_.readlines():
                    if six.PY2:
                        file_names.append(line.strip())
                    else:
                        file_names.append(
                            line.decode(__salt_system_encoding__).strip())

        if self.args:
            for fpath in self.args:
                if os.path.isfile(fpath) and \
                        fpath.endswith('.py') and \
                        os.path.basename(fpath).startswith('test_'):
                    if fpath in file_names:
                        self.options.name.append(fpath)
                    continue
                self.exit(status=1, msg='\'{}\' is not a valid test module\n'.format(fpath))

        if self.options.from_filenames is not None:
            self.options.from_filenames = self._expand_paths(self.options.from_filenames)

            # Locate the default map file if one was not passed
            if self.options.filename_map is None:
                self.options.filename_map = salt.utils.path.join(
                    tests.support.paths.TESTS_DIR,
                    'filename_map.yml'
                )

            self.options.name.extend(self._map_files(self.options.from_filenames))

        if self.options.name and file_names:
            self.options.name = list(set(self.options.name).intersection(file_names))
        elif file_names:
            self.options.name = file_names

        print_header(u'', inline=True, width=self.options.output_columns)
        self.pre_execution_cleanup()

        if self.support_docker_execution and self.options.docked is not None:
            if self.source_code_basedir is None:
                raise RuntimeError(
                    'You need to define the \'source_code_basedir\' attribute '
                    'in \'{0}\'.'.format(self.__class__.__name__)
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
            os.environ['TESTS_XML_OUTPUT_DIR'] = self.xml_output_dir
            print(
                ' * Generated unit test XML reports will be stored '
                'at {0!r}'.format(self.xml_output_dir)
            )

        self.validate_options()

        if self.support_destructive_tests_selection and not os.environ.get('DESTRUCTIVE_TESTS', None):
            # Set the required environment variable in order to know if
            # destructive tests should be executed or not.
            os.environ['DESTRUCTIVE_TESTS'] = str(self.options.run_destructive)

        if self.support_expensive_tests_selection and not os.environ.get('EXPENSIVE_TESTS', None):
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

        log_levels_to_evaluate = [
            logging.ERROR,  # Default log level
        ]
        if self.options.tests_logfile:
            filehandler = logging.FileHandler(
                mode='w',           # Not preserved between re-runs
                filename=self.options.tests_logfile,
                encoding='utf-8',
            )
            # The logs of the file are the most verbose possible
            filehandler.setLevel(logging.DEBUG)
            filehandler.setFormatter(formatter)
            logging.root.addHandler(filehandler)
            log_levels_to_evaluate.append(logging.DEBUG)

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
            elif self.options.verbosity == 3:   # -vv
                logging_level = logging.INFO
            else:
                logging_level = logging.ERROR
            log_levels_to_evaluate.append(logging_level)
            os.environ['TESTS_LOG_LEVEL'] = str(self.options.verbosity)  # future lint: disable=blacklisted-function
            consolehandler.setLevel(logging_level)
            logging.root.addHandler(consolehandler)
            log.info('Runtests logging has been setup')

        os.environ['TESTS_MIN_LOG_LEVEL_NAME'] = logging.getLevelName(min(log_levels_to_evaluate))

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
                  load_from_name=False, additional_test_dirs=None, failfast=False):
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
                verbosity=self.options.verbosity,
                failfast=failfast,
            ).run(tests)
        else:
            runner = TextTestRunner(
                stream=sys.stdout,
                verbosity=self.options.verbosity,
                failfast=failfast
            ).run(tests)

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
        exit_msg = 'Test suite execution finalized with exit code: {}'.format(exit_code)
        log.info(exit_msg)
        self.exit(status=exit_code, msg=exit_msg + '\n')

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
                    with open(cidfile) as cidfile_fd:  # pylint: disable=resource-leakage
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
            verbosity=self.options.verbosity,
            failfast=self.options.failfast,
        ).run(tests)
        self.testsuite_results.append((header, runner))
        return runner.wasSuccessful()
