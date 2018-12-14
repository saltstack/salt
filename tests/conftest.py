# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.conftest
    ~~~~~~~~~~~~~~

    Prepare py.test for our test suite
'''
# pylint: disable=ungrouped-imports,wrong-import-position,redefined-outer-name,missing-docstring

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import stat
import pprint
import shutil
import socket
import logging
TESTS_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)
CODE_DIR = os.path.dirname(TESTS_DIR)
os.chdir(CODE_DIR)
try:
    # If we have a system-wide salt module imported, unload it
    import salt
    for module in list(sys.modules):
        if module.startswith(('salt',)):
            try:
                if not sys.modules[module].__file__.startswith(CODE_DIR):
                    sys.modules.pop(module)
            except AttributeError:
                continue
    sys.path.insert(0, CODE_DIR)
except ImportError:
    sys.path.insert(0, CODE_DIR)

# Import test libs
from tests.support import paths  # pylint: disable=unused-import
from tests.support.runtests import RUNTIME_VARS

# Import pytest libs
import pytest
import _pytest.logging

# Import 3rd-party libs
import yaml
import psutil
from salt.ext import six

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.log.setup
import salt.log.mixins
import salt.utils.platform
from salt.utils.odict import OrderedDict
from salt.utils.immutabletypes import freeze

# Define the pytest plugins we rely on
# pylint: disable=invalid-name
pytest_plugins = ['tempdir', 'helpers_namespace', 'salt-from-filenames']

# Define where not to collect tests from
collect_ignore = ['setup.py']
# pylint: enable=invalid-name


# Patch PyTest logging handlers
# pylint: disable=protected-access,too-many-ancestors
class LogCaptureHandler(salt.log.mixins.ExcInfoOnLogLevelFormatMixIn,
                        _pytest.logging.LogCaptureHandler):
    '''
    Subclassing PyTest's LogCaptureHandler in order to add the
    exc_info_on_loglevel functionality.
    '''


_pytest.logging.LogCaptureHandler = LogCaptureHandler


class LiveLoggingStreamHandler(salt.log.mixins.ExcInfoOnLogLevelFormatMixIn,
                               _pytest.logging._LiveLoggingStreamHandler):
    '''
    Subclassing PyTest's LiveLoggingStreamHandler in order to add the
    exc_info_on_loglevel functionality.
    '''


_pytest.logging._LiveLoggingStreamHandler = LiveLoggingStreamHandler
# pylint: enable=protected-access,too-many-ancestors

# Reset logging root handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


log = logging.getLogger('salt.testsuite')


def pytest_tempdir_basename():
    '''
    Return the temporary directory basename for the salt test suite.
    '''
    return 'salt-tests-tmpdir'


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    '''
    register argparse-style options and ini-style config values.
    '''
    parser.addoption(
        '--sysinfo',
        default=False,
        action='store_true',
        help='Print some system information.'
    )
    parser.addoption(
        '--transport',
        default='zeromq',
        choices=('zeromq', 'tcp'),
        help=('Select which transport to run the integration tests with, '
              'zeromq or tcp. Default: %default')
    )
    test_selection_group = parser.getgroup('Tests Selection')
    test_selection_group.addoption(
        '--ssh',
        '--ssh-tests',
        dest='ssh',
        action='store_true',
        default=False,
        help='Run salt-ssh tests. These tests will spin up a temporary '
             'SSH server on your machine. In certain environments, this '
             'may be insecure! Default: False'
    )
    test_selection_group.addoption(
        '--proxy',
        '--proxy-tests',
        dest='proxy',
        action='store_true',
        default=False,
        help='Run proxy tests'
    )
    test_selection_group.addoption(
        '--run-destructive',
        action='store_true',
        default=False,
        help='Run destructive tests. These tests can include adding '
             'or removing users from your system for example. '
             'Default: False'
    )
    test_selection_group.addoption(
        '--run-expensive',
        action='store_true',
        default=False,
        help='Run expensive tests. These tests usually involve costs '
             'like for example bootstrapping a cloud VM. '
             'Default: False'
    )
    output_options_group = parser.getgroup('Output Options')
    output_options_group.addoption(
        '--output-columns',
        default=80,
        type=int,
        help='Number of maximum columns to use on the output'
    )
    output_options_group.addoption(
        '--no-colors',
        '--no-colours',
        default=False,
        action='store_true',
        help='Disable colour printing.'
    )
# <---- CLI Options Setup --------------------------------------------------------------------------------------------


# ----- Register Markers -------------------------------------------------------------------------------------------->
@pytest.mark.trylast
def pytest_configure(config):
    '''
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    '''
    config.addinivalue_line('norecursedirs', os.path.join(CODE_DIR, 'templates'))
    config.addinivalue_line('norecursedirs', os.path.join(CODE_DIR, 'tests/support'))
    config.addinivalue_line(
        'filterwarnings',
        r'once:encoding is deprecated, Use raw=False instead\.:DeprecationWarning'
    )
    config.addinivalue_line(
        'markers',
        'destructive_test: Run destructive tests. These tests can include adding '
        'or removing users from your system for example.'
    )
    config.addinivalue_line(
        'markers',
        'skip_if_not_root: Skip if the current user is not `root`.'
    )
    config.addinivalue_line(
        'markers',
        'skip_if_binaries_missing(*binaries, check_all=False, message=None): Skip if '
        'any of the passed binaries are not found in path. If \'check_all\' is '
        '\'True\', then all binaries must be found.'
    )
    config.addinivalue_line(
        'markers',
        'requires_network(only_local_network=False): Skip if no networking is set up. '
        'If \'only_local_network\' is \'True\', only the local network is checked.'
    )
    # Make sure the test suite "knows" this is a pytest test run
    RUNTIME_VARS.PYTEST_SESSION = True

    # Provide a global timeout for each test(pytest-timeout).
    if config._env_timeout is None:
        # If no timeout is set, set it to the default timeout value
        # Right now, we set it to 5 minutes which is absurd, but let's see how it goes
        config._env_timeout = 5 * 60

    # We always want deferred timeouts. Ie, only take into account the test function time
    # to run, exclude fixture setup/teardown
    config._env_timeout_func_only = True
# <---- Register Markers ---------------------------------------------------------------------------------------------


# ----- Test Setup -------------------------------------------------------------------------------------------------->
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    '''
    Fixtures injection based on markers or test skips based on CLI arguments
    '''
    destructive_tests_marker = item.get_closest_marker('destructive_test')
    if destructive_tests_marker is not None:
        if item.config.getoption('--run-destructive') is False:
            pytest.skip('Destructive tests are disabled')
    os.environ['DESTRUCTIVE_TESTS'] = six.text_type(item.config.getoption('--run-destructive'))

    expensive_tests_marker = item.get_closest_marker('expensive_test')
    if expensive_tests_marker is not None:
        if item.config.getoption('--run-expensive') is False:
            pytest.skip('Expensive tests are disabled')
    os.environ['EXPENSIVE_TESTS'] = six.text_type(item.config.getoption('--run-expensive'))

    skip_if_not_root_marker = item.get_closest_marker('skip_if_not_root')
    if skip_if_not_root_marker is not None:
        if os.getuid() != 0:
            pytest.skip('You must be logged in as root to run this test')

    skip_if_binaries_missing_marker = item.get_closest_marker('skip_if_binaries_missing')
    if skip_if_binaries_missing_marker is not None:
        binaries = skip_if_binaries_missing_marker.args
        if len(binaries) == 1:
            if isinstance(binaries[0], (list, tuple, set, frozenset)):
                binaries = binaries[0]
        check_all = skip_if_binaries_missing_marker.kwargs.get('check_all', False)
        message = skip_if_binaries_missing_marker.kwargs.get('message', None)
        if check_all:
            for binary in binaries:
                if salt.utils.path.which(binary) is None:
                    pytest.skip(
                        '{0}The "{1}" binary was not found'.format(
                            message and '{0}. '.format(message) or '',
                            binary
                        )
                    )
        elif salt.utils.path.which_bin(binaries) is None:
            pytest.skip(
                '{0}None of the following binaries was found: {1}'.format(
                    message and '{0}. '.format(message) or '',
                    ', '.join(binaries)
                )
            )

    requires_network_marker = item.get_closest_marker('requires_network')
    if requires_network_marker is not None:
        only_local_network = requires_network_marker.kwargs.get('only_local_network', False)
        has_local_network = False
        # First lets try if we have a local network. Inspired in verify_socket
        try:
            pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            pubsock.bind(('', 18000))
            pubsock.close()
            retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            retsock.bind(('', 18001))
            retsock.close()
            has_local_network = True
        except socket.error:
            # I wonder if we just have IPV6 support?
            try:
                pubsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                retsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                pubsock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                pubsock.bind(('', 18000))
                pubsock.close()
                retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                retsock.bind(('', 18001))
                retsock.close()
                has_local_network = True
            except socket.error:
                # Let's continue
                pass

        if only_local_network is True:
            if has_local_network is False:
                # Since we're only supposed to check local network, and no
                # local network was detected, skip the test
                pytest.skip('No local network was detected')

        # We are using the google.com DNS records as numerical IPs to avoid
        # DNS lookups which could greatly slow down this check
        for addr in ('173.194.41.198', '173.194.41.199', '173.194.41.200',
                     '173.194.41.201', '173.194.41.206', '173.194.41.192',
                     '173.194.41.193', '173.194.41.194', '173.194.41.195',
                     '173.194.41.196', '173.194.41.197'):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.25)
                sock.connect((addr, 80))
                sock.close()
                # We connected? Stop the loop
                break
            except socket.error:
                # Let's check the next IP
                continue
            else:
                pytest.skip('No internet network connection was detected')
# <---- Test Setup ---------------------------------------------------------------------------------------------------


# ----- Automatic Markers Setup ------------------------------------------------------------------------------------->
def pytest_collection_modifyitems(items):
    '''
    Automatically add markers to tests based on directory layout
    '''
    for item in items:
        fspath = str(item.fspath)
        if '/integration/' in fspath:
            if 'default_session_daemons' not in item.fixturenames:
                item.fixturenames.append('default_session_daemons')
            item.add_marker(pytest.mark.integration)
            for kind in ('cli', 'client', 'cloud', 'fileserver', 'loader', 'minion', 'modules',
                         'netapi', 'output', 'reactor', 'renderers', 'runners', 'sdb', 'shell',
                         'ssh', 'states', 'utils', 'wheel'):
                if '/{0}/'.format(kind) in fspath:
                    item.add_marker(getattr(pytest.mark, kind))
                    break
        if '/unit/' in fspath:
            item.add_marker(pytest.mark.unit)
            for kind in ('acl', 'beacons', 'cli', 'cloud', 'config', 'grains', 'modules', 'netapi',
                         'output', 'pillar', 'renderers', 'runners', 'serializers', 'states',
                         'templates', 'transport', 'utils'):
                if '/{0}/'.format(kind) in fspath:
                    item.add_marker(getattr(pytest.mark, kind))
                    break
# <---- Automatic Markers Setup --------------------------------------------------------------------------------------


# ----- Pytest Helpers ---------------------------------------------------------------------------------------------->
if six.PY2:
    # backport mock_open from the python 3 unittest.mock library so that we can
    # mock read, readline, readlines, and file iteration properly

    file_spec = None

    def _iterate_read_data(read_data):
        # Helper for mock_open:
        # Retrieve lines from read_data via a generator so that separate calls to
        # readline, read, and readlines are properly interleaved
        data_as_list = ['{0}\n'.format(l) for l in read_data.split('\n')]

        if data_as_list[-1] == '\n':
            # If the last line ended in a newline, the list comprehension will have an
            # extra entry that's just a newline.  Remove this.
            data_as_list = data_as_list[:-1]
        else:
            # If there wasn't an extra newline by itself, then the file being
            # emulated doesn't have a newline to end the last line  remove the
            # newline that our naive format() added
            data_as_list[-1] = data_as_list[-1][:-1]

        for line in data_as_list:
            yield line

    @pytest.helpers.mock.register
    def mock_open(mock=None, read_data=''):
        """
        A helper function to create a mock to replace the use of `open`. It works
        for `open` called directly or used as a context manager.

        The `mock` argument is the mock object to configure. If `None` (the
        default) then a `MagicMock` will be created for you, with the API limited
        to methods or attributes available on standard file handles.

        `read_data` is a string for the `read` methoddline`, and `readlines` of the
        file handle to return.  This is an empty string by default.
        """
        _mock = pytest.importorskip('mock', minversion='2.0.0')

        # pylint: disable=unused-argument
        def _readlines_side_effect(*args, **kwargs):
            if handle.readlines.return_value is not None:
                return handle.readlines.return_value
            return list(_data)

        def _read_side_effect(*args, **kwargs):
            if handle.read.return_value is not None:
                return handle.read.return_value
            return ''.join(_data)
        # pylint: enable=unused-argument

        def _readline_side_effect():
            if handle.readline.return_value is not None:
                while True:
                    yield handle.readline.return_value
            for line in _data:
                yield line

        global file_spec  # pylint: disable=global-statement
        if file_spec is None:
            file_spec = file  # pylint: disable=undefined-variable

        if mock is None:
            mock = _mock.MagicMock(name='open', spec=open)

        handle = _mock.MagicMock(spec=file_spec)
        handle.__enter__.return_value = handle

        _data = _iterate_read_data(read_data)

        handle.write.return_value = None
        handle.read.return_value = None
        handle.readline.return_value = None
        handle.readlines.return_value = None

        handle.read.side_effect = _read_side_effect
        handle.readline.side_effect = _readline_side_effect()
        handle.readlines.side_effect = _readlines_side_effect

        mock.return_value = handle
        return mock
else:
    @pytest.helpers.mock.register
    def mock_open(mock=None, read_data=''):
        _mock = pytest.importorskip('mock', minversion='2.0.0')
        return _mock.mock_open(mock=mock, read_data=read_data)
# <---- Pytest Helpers -----------------------------------------------------------------------------------------------


# ----- Fixtures Overrides ------------------------------------------------------------------------------------------>
# ----- Generate CLI Scripts ---------------------------------------------------------------------------------------->
@pytest.fixture(scope='session')
def cli_master_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_master'


@pytest.fixture(scope='session')
def cli_minion_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_minion'


@pytest.fixture(scope='session')
def cli_salt_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt'


@pytest.fixture(scope='session')
def cli_run_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_run'


@pytest.fixture(scope='session')
def cli_key_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_key'


@pytest.fixture(scope='session')
def cli_call_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_call'


@pytest.fixture(scope='session')
def cli_syndic_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_syndic'


@pytest.fixture(scope='session')
def cli_ssh_script_name():
    '''
    Return the CLI script basename
    '''
    return 'cli_salt_ssh'


@pytest.fixture(scope='session')
def cli_bin_dir(tempdir,
                request,
                python_executable_path,
                cli_master_script_name,
                cli_minion_script_name,
                cli_salt_script_name,
                cli_call_script_name,
                cli_key_script_name,
                cli_run_script_name,
                cli_ssh_script_name,
                cli_syndic_script_name):
    '''
    Return the path to the CLI script directory to use
    '''
    tmp_cli_scripts_dir = tempdir.join('cli-scrips-bin')
    tmp_cli_scripts_dir.ensure(dir=True)
    cli_bin_dir_path = tmp_cli_scripts_dir.strpath

    # Now that we have the CLI directory created, lets generate the required CLI scripts to run salt's test suite
    script_templates = {
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
            'if __name__ == \'__main__\':\n',
            '    salt_{0}()'
        ]
    }

    for script_name in (cli_master_script_name,
                        cli_minion_script_name,
                        cli_call_script_name,
                        cli_key_script_name,
                        cli_run_script_name,
                        cli_salt_script_name,
                        cli_ssh_script_name,
                        cli_syndic_script_name):
        original_script_name = script_name.split('cli_')[-1].replace('_', '-')
        script_path = os.path.join(cli_bin_dir_path, script_name)

        if not os.path.isfile(script_path):
            log.info('Generating %s', script_path)

            with salt.utils.files.fopen(script_path, 'w') as sfh:
                script_template = script_templates.get(original_script_name, None)
                if script_template is None:
                    script_template = script_templates.get('common', None)
                if script_template is None:
                    raise RuntimeError(
                        'Salt\'s test suite does not know how to handle the "{0}" script'.format(
                            original_script_name
                        )
                    )
                sfh.write(
                    '#!{0}\n\n'.format(python_executable_path) +
                    'import sys\n' +
                    'CODE_DIR="{0}"\n'.format(request.config.startdir.realpath().strpath) +
                    'if CODE_DIR not in sys.path:\n' +
                    '    sys.path.insert(0, CODE_DIR)\n\n' +
                    '\n'.join(script_template).format(original_script_name.replace('salt-', ''))
                )
            fst = os.stat(script_path)
            os.chmod(script_path, fst.st_mode | stat.S_IEXEC)

    # Return the CLI bin dir value
    return cli_bin_dir_path
# <---- Generate CLI Scripts -----------------------------------------------------------------------------------------


# ----- Salt Configuration ------------------------------------------------------------------------------------------>
@pytest.fixture(scope='session')
def session_master_of_masters_id():
    '''
    Returns the master of masters id
    '''
    return 'syndic_master'


@pytest.fixture(scope='session')
def session_master_id():
    '''
    Returns the session scoped master id
    '''
    return 'master'


@pytest.fixture(scope='session')
def session_minion_id():
    '''
    Returns the session scoped minion id
    '''
    return 'minion'


@pytest.fixture(scope='session')
def session_secondary_minion_id():
    '''
    Returns the session scoped secondary minion id
    '''
    return 'sub_minion'


@pytest.fixture(scope='session')
def session_syndic_id():
    '''
    Returns the session scoped syndic id
    '''
    return 'syndic'


@pytest.fixture(scope='session')
def salt_fail_hard():
    '''
    Return the salt fail hard value
    '''
    return True


@pytest.fixture(scope='session')
def session_master_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'master')) as rfh:
        opts = yaml.load(rfh.read())

        tests_known_hosts_file = session_root_dir.join('salt_ssh_known_hosts').strpath
        with salt.utils.files.fopen(tests_known_hosts_file, 'w') as known_hosts:
            known_hosts.write('')

        opts['known_hosts_file'] = tests_known_hosts_file
        opts['syndic_master'] = 'localhost'
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def session_master_config_overrides(session_root_dir):
    if salt.utils.platform.is_windows():
        ext_pillar = {'cmd_yaml': 'type {0}'.format(os.path.join(RUNTIME_VARS.FILES, 'ext.yaml'))}
    else:
        ext_pillar = {'cmd_yaml': 'cat {0}'.format(os.path.join(RUNTIME_VARS.FILES, 'ext.yaml'))}

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = session_root_dir.join('extension_modules').strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(
                RUNTIME_VARS.FILES, 'extension_modules'
            ),
            extension_modules_path
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = session_root_dir.join('autosign_file').strpath
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, 'autosign_file'),
        autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    os.chmod(autosign_file_path, autosign_file_permissions)

    return {
        'ext_pillar': [ext_pillar],
        'extension_modules': extension_modules_path,
        'file_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'base'),
            ],
            # Alternate root to test __env__ choices
            'prod': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
            ]
        },
        'pillar_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'pillar', 'base'),
            ]
        },
        'reactor': [
            {
                'salt/minion/*/start': [
                    os.path.join(RUNTIME_VARS.FILES, 'reactor-sync-minion.sls')
                ],
            }
        ]
    }


@pytest.fixture(scope='session')
def session_minion_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'minion')) as rfh:
        opts = yaml.load(rfh.read())

        opts['hosts.file'] = session_root_dir.join('hosts').strpath
        opts['aliases.file'] = session_root_dir.join('aliases').strpath
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def session_minion_config_overrides():
    return {
        'file_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'base'),
            ],
            # Alternate root to test __env__ choices
            'prod': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
            ]
        },
        'pillar_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'pillar', 'base'),
            ]
        },
    }


@pytest.fixture(scope='session')
def session_secondary_minion_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'sub_minion')) as rfh:
        opts = yaml.load(rfh.read())

        opts['hosts.file'] = session_root_dir.join('hosts').strpath
        opts['aliases.file'] = session_root_dir.join('aliases').strpath
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def session_master_of_masters_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'syndic_master')) as rfh:
        opts = yaml.load(rfh.read())

        opts['hosts.file'] = session_root_dir.join('hosts').strpath
        opts['aliases.file'] = session_root_dir.join('aliases').strpath
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def session_master_of_masters_config_overrides(session_master_of_masters_root_dir):
    if salt.utils.platform.is_windows():
        ext_pillar = {'cmd_yaml': 'type {0}'.format(os.path.join(RUNTIME_VARS.FILES, 'ext.yaml'))}
    else:
        ext_pillar = {'cmd_yaml': 'cat {0}'.format(os.path.join(RUNTIME_VARS.FILES, 'ext.yaml'))}

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = session_master_of_masters_root_dir.join('extension_modules').strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(
                RUNTIME_VARS.FILES, 'extension_modules'
            ),
            extension_modules_path
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = session_master_of_masters_root_dir.join('autosign_file').strpath
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, 'autosign_file'),
        autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    os.chmod(autosign_file_path, autosign_file_permissions)

    return {
        'ext_pillar': [ext_pillar],
        'extension_modules': extension_modules_path,
        'file_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'base'),
            ],
            # Alternate root to test __env__ choices
            'prod': [
                os.path.join(RUNTIME_VARS.FILES, 'file', 'prod'),
            ]
        },
        'pillar_roots': {
            'base': [
                os.path.join(RUNTIME_VARS.FILES, 'pillar', 'base'),
            ]
        },
    }


@pytest.fixture(scope='session')
def session_syndic_master_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'syndic_master')) as rfh:
        opts = yaml.load(rfh.read())

        opts['hosts.file'] = session_root_dir.join('hosts').strpath
        opts['aliases.file'] = session_root_dir.join('aliases').strpath
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def session_syndic_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, 'syndic')) as rfh:
        opts = yaml.load(rfh.read())

        opts['hosts.file'] = session_root_dir.join('hosts').strpath
        opts['aliases.file'] = session_root_dir.join('aliases').strpath
        opts['transport'] = request.config.getoption('--transport')

        return opts


@pytest.fixture(scope='session')
def reap_stray_processes():
    # Run tests
    yield

    children = psutil.Process(os.getpid()).children(recursive=True)
    if not children:
        log.info('No astray processes found')
        return

    def on_terminate(proc):
        log.debug('Process %s terminated with exit code %s', proc, proc.returncode)

    if children:
        # Reverse the order, sublings first, parents after
        children.reverse()
        log.warning(
            'Test suite left %d astray processes running. Killing those processes:\n%s',
            len(children),
            pprint.pformat(children)
        )

        gone, alive = psutil.wait_procs(children, timeout=3, callback=on_terminate)
        for child in alive:
            child.kill()

        gone, alive = psutil.wait_procs(alive, timeout=3, callback=on_terminate)
        if alive:
            # Give up
            for child in alive:
                log.warning('Process %s survived SIGKILL, giving up:\n%s', child, pprint.pformat(child.as_dict()))


@pytest.fixture(scope='session', autouse=True)
def bridge_pytest_and_runtests(reap_stray_processes,
                               session_root_dir,
                               session_conf_dir,
                               session_secondary_conf_dir,
                               session_syndic_conf_dir,
                               session_master_of_masters_conf_dir,
                               session_base_env_pillar_tree_root_dir,
                               session_base_env_state_tree_root_dir,
                               session_prod_env_state_tree_root_dir,
                               session_master_config,
                               session_minion_config,
                               session_secondary_minion_config,
                               session_master_of_masters_config,
                               session_syndic_config):

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP = RUNTIME_VARS.SYS_TMP_DIR = session_root_dir.realpath().strpath
    RUNTIME_VARS.TMP_CONF_DIR = session_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = session_secondary_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = session_master_of_masters_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = session_syndic_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_PILLAR_TREE = session_base_env_pillar_tree_root_dir.realpath().strpath
    RUNTIME_VARS.TMP_STATE_TREE = session_base_env_state_tree_root_dir.realpath().strpath
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = session_prod_env_state_tree_root_dir.realpath().strpath

    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS['master'] = freeze(session_master_config)
    RUNTIME_VARS.RUNTIME_CONFIGS['minion'] = freeze(session_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS['sub_minion'] = freeze(session_secondary_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS['syndic_master'] = freeze(session_master_of_masters_config)
    RUNTIME_VARS.RUNTIME_CONFIGS['syndic'] = freeze(session_syndic_config)
    RUNTIME_VARS.RUNTIME_CONFIGS['client_config'] = freeze(session_master_config)

    # Copy configuration files and directories which are not automatically generated
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if entry in ('master', 'minion', 'sub_minion', 'syndic', 'syndic_master', 'proxy'):
            # These have runtime computed values and are handled by pytest-salt fixtures
            continue
        entry_path = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        if os.path.isfile(entry_path):
            shutil.copy(
                entry_path,
                os.path.join(RUNTIME_VARS.TMP_CONF_DIR, entry)
            )
        elif os.path.isdir(entry_path):
            shutil.copytree(
                entry_path,
                os.path.join(RUNTIME_VARS.TMP_CONF_DIR, entry)
            )
# <---- Salt Configuration -------------------------------------------------------------------------------------------


# <---- Fixtures Overrides -------------------------------------------------------------------------------------------
# ----- Custom Fixtures Definitions --------------------------------------------------------------------------------->
# pylint: disable=unused-argument
@pytest.fixture(scope='session')
def session_salt_syndic(request, session_salt_master_of_masters, session_salt_syndic):
    request.session.stats_processes.update(OrderedDict((
        ('Salt Syndic Master', psutil.Process(session_salt_master_of_masters.pid)),
        ('       Salt Syndic', psutil.Process(session_salt_syndic.pid)),
    )).items())
    yield session_salt_syndic
    request.session.stats_processes.pop('Salt Syndic Master')
    request.session.stats_processes.pop('       Salt Syndic')


@pytest.fixture(scope='session')
def default_session_daemons(request,
                            log_server,
                            salt_log_port,
                            engines_dir,
                            log_handlers_dir,
                            session_salt_master,
                            session_salt_minion,
                            session_secondary_salt_minion,
                            ):

    request.session.stats_processes.update(OrderedDict((
        ('       Salt Master', psutil.Process(session_salt_master.pid)),
        ('       Salt Minion', psutil.Process(session_salt_minion.pid)),
        ('   Salt Sub Minion', psutil.Process(session_secondary_salt_minion.pid)),
    )).items())
# pylint: enable=unused-argument
# <---- Custom Fixtures Definitions ----------------------------------------------------------------------------------
