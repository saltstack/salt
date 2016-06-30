# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    tests.conftest
    ~~~~~~~~~~~~~~

    Prepare py.test for our test suite
'''

# Import 3rd-party libs
import pytest


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    '''
    register argparse-style options and ini-style config values.
    '''
    parser.addoption(
        '--run-destructive',
        action='store_true',
        default=False,
        help='Run destructive tests. These tests can include adding '
             'or removing users from your system for example. '
             'Default: False'
    )
# <---- CLI Options Setup --------------------------------------------------------------------------------------------

# ----- Register Markers -------------------------------------------------------------------------------------------->
def pytest_configure(config):
    '''
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    '''
    config.addinivalue_line(
        'markers',
        'Run destructive tests. These tests can include adding '
        'or removing users from your system for example.'
    )
# <---- Register Markers ---------------------------------------------------------------------------------------------

# ----- Test Setup -------------------------------------------------------------------------------------------------->
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    '''
    Fixtures injection based on markers or test skips based on CLI arguments
    '''
    destructive_tests_marker = item.get_marker('destructive_test')
    if destructive_tests_marker is not None:
        if item.config.getoption('--run-destructive') is False:
            pytest.skip('Destructive tests are disabled')
# <---- Test Setup ---------------------------------------------------------------------------------------------------
