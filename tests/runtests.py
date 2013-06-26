#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import sys
import os
import re
import logging
import optparse
import resource
import tempfile

# Import salt libs
import saltunittest
from integration import print_header, PNUM, TestDaemon, TMP

try:
    import xmlrunner
except ImportError:
    xmlrunner = None

TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
SALT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
XML_OUTPUT_DIR = os.environ.get(
    'SALT_XML_TEST_REPORTS_DIR',
    os.path.join(TMP, 'xml-test-reports')
)


try:
    if SALT_ROOT:
        os.chdir(SALT_ROOT)
except OSError as err:
    print 'Failed to change directory to salt\'s source: {0}'.format(err)

try:
    import coverage
    # Cover any subprocess
    coverage.process_startup()
    # Setup coverage
    code_coverage = coverage.coverage(
        branch=True,
        source=[os.path.join(os.getcwd(), 'salt')],
    )
except ImportError:
    code_coverage = None


REQUIRED_OPEN_FILES = 3072

TEST_RESULTS = []


def run_suite(opts, path, display_name, suffix='[!_]*.py'):
    '''
    Execute a unit test suite
    '''
    loader = saltunittest.TestLoader()
    if opts.name:
        tests = loader.loadTestsFromName(display_name)
    else:
        tests = loader.discover(path, suffix, TEST_DIR)

    header = '{0} Tests'.format(display_name)
    print_header('Starting {0}'.format(header))

    if opts.xmlout:
        runner = xmlrunner.XMLTestRunner(output=XML_OUTPUT_DIR).run(tests)
    else:
        if not os.path.isdir(XML_OUTPUT_DIR):
            os.makedirs(XML_OUTPUT_DIR)
        runner = saltunittest.TextTestRunner(
            verbosity=opts.verbosity
        ).run(tests)
        TEST_RESULTS.append((header, runner))

    return runner.wasSuccessful()


def run_integration_suite(opts, suite_folder, display_name):
    '''
    Run an integration test suite
    '''
    path = os.path.join(TEST_DIR, 'integration', suite_folder)
    return run_suite(opts, path, display_name)


def run_integration_tests(opts):
    '''
    Execute the integration tests suite
    '''
    if opts.unit and not (opts.runner or opts.state or opts.module or opts.client):
        return [True]
    smax_open_files, hmax_open_files = resource.getrlimit(resource.RLIMIT_NOFILE)
    if smax_open_files < REQUIRED_OPEN_FILES:
        print('~' * PNUM)
        print('Max open files setting is too low({0}) for running the tests'.format(smax_open_files))
        print('Trying to raise the limit to {0}'.format(REQUIRED_OPEN_FILES))
        if hmax_open_files < 4096:
            hmax_open_files = 4096  # Decent default?
        try:
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (REQUIRED_OPEN_FILES, hmax_open_files)
            )
        except Exception as err:
            print('ERROR: Failed to raise the max open files setting -> {0}'.format(err))
            print('Please issue the following command on your console:')
            print('  ulimit -n {0}'.format(REQUIRED_OPEN_FILES))
            sys.exit(1)
        finally:
            print('~' * PNUM)

    print_header('Setting up Salt daemons to execute tests', top=False)
    status = []
    if not any([opts.client, opts.module, opts.runner,
                opts.shell, opts.state, opts.name]):
        return status
    with TestDaemon(opts=opts):
        if opts.name:
            for name in opts.name:
                results = run_suite(opts, '', name)
                status.append(results)
        if opts.runner:
            status.append(run_integration_suite(opts, 'runners', 'Runner'))
        if opts.module:
            status.append(run_integration_suite(opts, 'modules', 'Module'))
        if opts.state:
            status.append(run_integration_suite(opts, 'states', 'State'))
        if opts.client:
            status.append(run_integration_suite(opts, 'client', 'Client'))
        if opts.shell:
            status.append(run_integration_suite(opts, 'shell', 'Shell'))
    return status


def run_unit_tests(opts):
    '''
    Execute the unit tests
    '''
    if not opts.unit:
        return [True]
    status = []
    if opts.name:
        for name in opts.name:
            results = run_suite(opts, os.path.join(TEST_DIR, 'unit'), name)
            status.append(results)
    else:
        results = run_suite(
            opts, os.path.join(TEST_DIR, 'unit'), 'Unit', '*_test.py')
        status.append(results)
    return status


def parse_opts():
    '''
    Parse command line options for running specific tests
    '''
    parser = optparse.OptionParser()

    parser.add_option(
        '--sysinfo',
        default=False,
        action='store_true',
        help='Print some system information.'
    )

    tests_select_group = optparse.OptionGroup(
        parser,
        "Tests Selection Options",
        "Select which tests are to be executed"
    )
    tests_select_group.add_option(
        '-m',
        '--module',
        '--module-tests',
        dest='module',
        default=False,
        action='store_true',
        help='Run tests for modules'
    )
    tests_select_group.add_option(
        '-S',
        '--state',
        '--state-tests',
        dest='state',
        default=False,
        action='store_true',
        help='Run tests for states'
    )
    tests_select_group.add_option(
        '-c',
        '--client',
        '--client-tests',
        dest='client',
        default=False,
        action='store_true',
        help='Run tests for client'
    )
    tests_select_group.add_option(
        '-s',
        '--shell',
        dest='shell',
        default=False,
        action='store_true',
        help='Run shell tests'
    )
    tests_select_group.add_option(
        '-r',
        '--runner',
        dest='runner',
        default=False,
        action='store_true',
        help='Run runner tests'
    )
    tests_select_group.add_option(
        '-u',
        '--unit',
        '--unit-tests',
        dest='unit',
        default=False,
        action='store_true',
        help='Run unit tests'
    )
    tests_select_group.add_option(
        '-n',
        '--name',
        dest='name',
        action='append',
        default=[],
        help=('Specific test name to run. A named test is the module path '
              'relative to the tests directory, to execute the config module '
              'integration tests for instance call:\n'
              'runtests.py -n integration.modules.config')
    )
    tests_select_group.add_option(
        '--run-destructive',
        action='store_true',
        default=False,
        help='Run destructive tests. These tests can include adding or '
             'removing users from your system for example. Default: %default'
    )
    parser.add_option_group(tests_select_group)

    fs_cleanup_options_group = optparse.OptionGroup(
        parser, "File system cleanup Options"
    )
    fs_cleanup_options_group.add_option(
        '--clean',
        dest='clean',
        default=True,
        action='store_true',
        help='Clean up test environment before and after integration '
             'testing (default behaviour)'
    )
    fs_cleanup_options_group.add_option(
        '--no-clean',
        dest='clean',
        action='store_false',
        help='Don\'t clean up test environment before and after integration '
             'testing (speed up test process)'
    )
    parser.add_option_group(fs_cleanup_options_group)

    output_options_group = optparse.OptionGroup(parser, "Output Options")
    output_options_group.add_option(
        '-v',
        '--verbose',
        dest='verbosity',
        default=1,
        action='count',
        help='Verbose test runner output'
    )
    output_options_group.add_option(
        '-x',
        '--xml',
        dest='xmlout',
        default=False,
        action='store_true',
        help='XML test runner output(Output directory: {0})'.format(
            XML_OUTPUT_DIR
        )
    )
    output_options_group.add_option(
        '--no-report',
        default=False,
        action='store_true',
        help='Do NOT show the overall tests result'
    )
    output_options_group.add_option(
        '--coverage',
        default=False,
        action='store_true',
        help='Run tests and report code coverage'
    )
    output_options_group.add_option(
        '--no-coverage-report',
        default=False,
        action='store_true',
        help='Don\'t build the coverage HTML report'
    )
    output_options_group.add_option(
        '--no-colors',
        '--no-colours',
        default=False,
        action='store_true',
        help='Disable colour printing.'
    )
    parser.add_option_group(output_options_group)

    options, _ = parser.parse_args()

    if options.xmlout and xmlrunner is None:
        parser.error(
            '\'--xml\' is not available. The xmlrunner library is not '
            'installed.'
        )

    if options.coverage and code_coverage is None:
        parser.error(
            'Cannot run tests with coverage report. '
            'Please install coverage>=3.5.3'
        )
    elif options.coverage:
        coverage_version = tuple(
            [int(part) for part in
             re.search(r'([0-9.]+)', coverage.__version__).group(0).split('.')]
        )
        if coverage_version < (3, 5, 3):
            # Should we just print the error instead of exiting?
            parser.error(
                'Versions lower than 3.5.3 of the coverage library are know '
                'to produce incorrect results. Please consider upgrading...'
            )

        if any((options.module, options.client, options.shell, options.unit,
                options.state, options.runner, options.name,
                os.geteuid() != 0, not options.run_destructive)):
            parser.error(
                'No sense in generating the tests coverage report when not '
                'running the full test suite, including the destructive '
                'tests, as \'root\'. It would only produce incorrect '
                'results.'
            )

        # Update environ so that any subprocess started on test are also
        # included in the report
        os.environ['COVERAGE_PROCESS_START'] = '1'

    # Setup logging
    formatter = logging.Formatter(
        '%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d]'
        '[%(levelname)-8s] %(message)s',
        datefmt='%H:%M:%S'
    )
    logfile = os.path.join(tempfile.gettempdir(), 'salt-runtests.log')
    filehandler = logging.FileHandler(
        mode='w',           # Not preserved between re-runs
        filename=logfile
    )
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    logging.root.addHandler(filehandler)
    logging.root.setLevel(logging.DEBUG)

    print_header('Logging tests on {0}'.format(logfile), bottom=False)
    print('Current Directory: {0}'.format(os.getcwd()))
    print_header(
        'Test suite is running under PID {0}'.format(os.getpid()), bottom=False
    )

    # With greater verbosity we can also log to the console
    if options.verbosity > 2:
        consolehandler = logging.StreamHandler(sys.stderr)
        consolehandler.setLevel(logging.INFO)       # -vv
        consolehandler.setFormatter(formatter)
        handled_levels = {
            3: logging.DEBUG,   # -vvv
            4: logging.TRACE,   # -vvvv
            5: logging.GARBAGE  # -vvvvv
        }
        if options.verbosity > 3:
            consolehandler.setLevel(
                handled_levels.get(
                    options.verbosity,
                    options.verbosity > 5 and 5 or 3
                )
            )

        logging.root.addHandler(consolehandler)

    os.environ['DESTRUCTIVE_TESTS'] = str(options.run_destructive)

    if not any((options.module, options.client,
                options.shell, options.unit,
                options.state, options.runner,
                options.name)):
        options.module = True
        options.client = True
        options.shell = True
        options.unit = True
        options.runner = True
        options.state = True
    return options


if __name__ == '__main__':
    opts = parse_opts()
    if opts.coverage:
        code_coverage.start()

    overall_status = []
    status = run_integration_tests(opts)
    overall_status.extend(status)
    status = run_unit_tests(opts)
    overall_status.extend(status)
    false_count = overall_status.count(False)

    if opts.no_report:
        if opts.coverage:
            code_coverage.stop()
            code_coverage.save()

        if false_count > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    print_header(u'  Overall Tests Report  ', sep=u'=', centered=True, inline=True)

    no_problems_found = True
    for (name, results) in TEST_RESULTS:
        if not results.failures and not results.errors and not results.skipped:
            continue

        no_problems_found = False

        print_header(u'*** {0}  '.format(name), sep=u'*', inline=True)
        if results.skipped:
            print_header(u' --------  Skipped Tests  ', sep='-', inline=True)
            maxlen = len(max([tc.id() for (tc, reason) in results.skipped], key=len))
            fmt = u'   -> {0: <{maxlen}}  ->  {1}'
            for tc, reason in results.skipped:
                print(fmt.format(tc.id(), reason, maxlen=maxlen))
            print_header(u' ', sep='-', inline=True)

        if results.errors:
            print_header(u' --------  Tests with Errors  ', sep='-', inline=True)
            for tc, reason in results.errors:
                print_header(u'   -> {0}  '.format(tc.id()), sep=u'.', inline=True)
                for line in reason.rstrip().splitlines():
                    print('       {0}'.format(line.rstrip()))
                print_header(u'   ', sep=u'.', inline=True)
            print_header(u' ', sep='-', inline=True)

        if results.failures:
            print_header(u' --------  Failed Tests  ', sep='-', inline=True)
            for tc, reason in results.failures:
                print_header(u'   -> {0}  '.format(tc.id()), sep=u'.', inline=True)
                for line in reason.rstrip().splitlines():
                    print('       {0}'.format(line.rstrip()))
                print_header(u'   ', sep=u'.', inline=True)
            print_header(u' ', sep='-', inline=True)

        print_header(u'', sep=u'*', inline=True)

    if no_problems_found:
        print_header(
            u'***  No Problems Found While Running Tests  ',
            sep=u'*', inline=True
        )

    print_header('  Overall Tests Report  ', sep='=', centered=True, inline=True)

    if opts.coverage:
        print('Stopping and saving coverage info')
        code_coverage.stop()
        code_coverage.save()
        print('Current Directory: {0}'.format(os.getcwd()))
        print('Coverage data file exists? {0}'.format(os.path.isfile('.coverage')))

        if opts.no_coverage_report is False:
            report_dir = os.path.join(os.path.dirname(__file__), 'coverage-report')
            print(
                '\nGenerating Coverage HTML Report Under {0!r} ...'.format(
                    report_dir
                )
            ),
            sys.stdout.flush()

            if os.path.isdir(report_dir):
                import shutil
                shutil.rmtree(report_dir)
            code_coverage.html_report(directory=report_dir)
            print('Done.\n')

    if false_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
