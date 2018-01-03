# -*- coding: utf-8 -*-
'''
    tests.support.parser.cover
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Code coverage aware testing parser

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: Copyright 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''
# pylint: disable=repr-flag-used-in-string

# Import python libs
from __future__ import absolute_import, print_function
import os
import re
import sys
import shutil
import warnings

# Import Salt libs
import salt.utils.json

# Import salt testing libs
from tests.support.parser import SaltTestingParser

# Import coverage libs
try:
    import coverage
    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False

try:
    import multiprocessing.util
    # Force forked multiprocessing processes to be measured as well

    def multiprocessing_stop(coverage_object):
        '''
        Save the multiprocessing process coverage object
        '''
        coverage_object.stop()
        coverage_object.save()

    def multiprocessing_start(obj):
        coverage_options = salt.utils.json.loads(os.environ.get('COVERAGE_OPTIONS', '{}'))
        if not coverage_options:
            return

        if coverage_options.get('data_suffix', False) is False:
            return

        coverage_object = coverage.coverage(**coverage_options)
        coverage_object.start()

        multiprocessing.util.Finalize(
            None,
            multiprocessing_stop,
            args=(coverage_object,),
            exitpriority=1000
        )

    if COVERAGE_AVAILABLE:
        multiprocessing.util.register_after_fork(
            multiprocessing_start,
            multiprocessing_start
        )
except ImportError:
    pass

if COVERAGE_AVAILABLE:
    # Cover any processes if the environ variables are present
    coverage.process_startup()


class SaltCoverageTestingParser(SaltTestingParser):
    '''
    Code coverage aware testing option parser
    '''
    def __init__(self, *args, **kwargs):
        if kwargs.pop('html_output_from_env', None) is not None or \
                kwargs.pop('html_output_dir', None) is not None:
            warnings.warn(
                'The unit tests HTML support was removed from {0}. Please '
                'stop passing \'html_output_dir\' or \'html_output_from_env\' '
                'as arguments to {0}'.format(self.__class__.__name__),
                category=DeprecationWarning,
                stacklevel=2
            )

        SaltTestingParser.__init__(self, *args, **kwargs)
        self.code_coverage = None

        # Add the coverage related options
        self.output_options_group.add_option(
            '--coverage',
            default=False,
            action='store_true',
            help='Run tests and report code coverage'
        )
        self.output_options_group.add_option(
            '--no-processes-coverage',
            default=False,
            action='store_true',
            help='Do not track subprocess and/or multiprocessing processes'
        )
        self.output_options_group.add_option(
            '--coverage-xml',
            default=None,
            help='If provided, the path to where a XML report of the code '
                 'coverage will be written to'
        )
        self.output_options_group.add_option(
            '--coverage-html',
            default=None,
            help=('The directory where the generated HTML coverage report '
                  'will be saved to. The directory, if existing, will be '
                  'deleted before the report is generated.')
        )

    def _validate_options(self):
        if (self.options.coverage_xml or self.options.coverage_html) and \
                not self.options.coverage:
            self.options.coverage = True

        if self.options.coverage is True and COVERAGE_AVAILABLE is False:
            self.error(
                'Cannot run tests with coverage report. '
                'Please install coverage>=3.5.3'
            )

        if self.options.coverage is True:
            coverage_version = tuple([
                int(part) for part in re.search(
                    r'([0-9.]+)', coverage.__version__).group(0).split('.')
            ])
            if coverage_version < (3, 5, 3):
                # Should we just print the error instead of exiting?
                self.error(
                    'Versions lower than 3.5.3 of the coverage library are '
                    'know to produce incorrect results. Please consider '
                    'upgrading...'
                )
        SaltTestingParser._validate_options(self)

    def pre_execution_cleanup(self):
        if self.options.coverage_html is not None:
            if os.path.isdir(self.options.coverage_html):
                shutil.rmtree(self.options.coverage_html)
        if self.options.coverage_xml is not None:
            if os.path.isfile(self.options.coverage_xml):
                os.unlink(self.options.coverage_xml)
        SaltTestingParser.pre_execution_cleanup(self)

    def start_coverage(self, **coverage_options):
        '''
        Start code coverage.

        You can pass any coverage options as keyword arguments. For the
        available options please see:
            http://nedbatchelder.com/code/coverage/api.html
        '''
        if self.options.coverage is False:
            return

        if coverage_options.pop('track_processes', None) is not None:
            raise RuntimeWarning(
                'Please stop passing \'track_processes\' to '
                '\'start_coverage()\'. It\'s now the default and '
                '\'--no-processes-coverage\' was added to the parser to '
                'disable it.'
            )
        print(' * Starting Coverage')

        if self.options.no_processes_coverage is False:
            # Update environ so that any subprocess started on tests are also
            # included in the report
            coverage_options['data_suffix'] = True
            os.environ['COVERAGE_PROCESS_START'] = '1'
            os.environ['COVERAGE_OPTIONS'] = salt.utils.json.dumps(coverage_options)

        # Setup coverage
        self.code_coverage = coverage.coverage(**coverage_options)
        self.code_coverage.start()

    def stop_coverage(self, save_coverage=True):
        '''
        Stop code coverage.
        '''
        if self.options.coverage is False:
            return

        # Clean up environment
        os.environ.pop('COVERAGE_OPTIONS', None)
        os.environ.pop('COVERAGE_PROCESS_START', None)

        print(' * Stopping coverage')
        self.code_coverage.stop()
        if save_coverage:
            print(' * Saving coverage info')
            self.code_coverage.save()

        if self.options.no_processes_coverage is False:
            # Combine any multiprocessing coverage data files
            sys.stdout.write(' * Combining multiple coverage info files ... ')
            sys.stdout.flush()
            self.code_coverage.combine()
            print('Done.')

        if self.options.coverage_xml is not None:
            sys.stdout.write(
                ' * Generating Coverage XML Report At {0!r} ... '.format(
                    self.options.coverage_xml
                )
            )
            sys.stdout.flush()
            self.code_coverage.xml_report(
                outfile=self.options.coverage_xml
            )
            print('Done.')

        if self.options.coverage_html is not None:
            sys.stdout.write(
                ' * Generating Coverage HTML Report Under {0!r} ... '.format(
                    self.options.coverage_html
                )
            )
            sys.stdout.flush()
            self.code_coverage.html_report(
                directory=self.options.coverage_html
            )
            print('Done.')

    def finalize(self, exit_code=0):
        if self.options.coverage is True:
            self.stop_coverage(save_coverage=True)
        SaltTestingParser.finalize(self, exit_code)
