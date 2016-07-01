# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    tests.conftest
    ~~~~~~~~~~~~~~

    Prepare py.test for our test suite
'''

# Import python libs
from __future__ import absolute_import
import os
import socket

# Import 3rd-party libs
import pytest
import salt.ext.six as six

# Import salt libs
import salt.utils


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    '''
    register argparse-style options and ini-style config values.
    '''
    test_selection_group = parser.getgroup('Tests Selection')
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
# <---- CLI Options Setup --------------------------------------------------------------------------------------------

# ----- Register Markers -------------------------------------------------------------------------------------------->
def pytest_configure(config):
    '''
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    '''
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
        'skip_if_binaries_missing(*binaries, check_all=False): Skip if any of the '
        'passed binaries are not found in path. If \'check_all\' is \'True\', then '
        'all binaries must be found.'
    )
    config.addinivalue_line(
        'markers',
        'requires_network(only_local_network=False): Skip if no networking is set up. '
        'If \'only_local_network\' is \'True\', only the local network is checked.'
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

    expensive_tests_marker = item.get_marker('expensive_test')
    if expensive_tests_marker is not None:
        if item.config.getoption('--run-expensive') is False:
            pytest.skip('Expensive tests are disabled')

    skip_if_not_root_marker = item.get_marker('skip_if_not_root')
    if skip_if_not_root_marker is not None:
        if os.getuid() != 0:
            pytest.skip('You must be logged in as root to run this test')

    skip_if_binaries_missing_marker = item.get_marker('skip_if_binaries_missing')
    if skip_if_binaries_missing_marker is not None:
        binaries = skip_if_binaries_missing_marker.args
        if len(binaries) == 1:
            if isinstance(binaries[0], (list, tuple, set, frozenset)):
                binaries = binaries[0]
        check_all = skip_if_binaries_missing_marker.kwargs.get('check_all', False)
        message = skip_if_binaries_missing_marker.kwargs.get('message', None)
        if check_all:
            for binary in binaries:
                if salt.utils.which(binary) is None:
                    pytest.skip(
                        '{0}The {1!r} binary was not found'.format(
                            message and '{0}. '.format(message) or '',
                            binary
                        )
                    )
        elif salt.utils.which_bin(binaries) is None:
            pytest.skip(
                '{0}None of the following binaries was found: {1}'.format(
                    message and '{0}. '.format(message) or '',
                    ', '.join(binaries)
                )
            )

    requires_network_marker = item.get_marker('requires_network')
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

        def _readlines_side_effect(*args, **kwargs):
            if handle.readlines.return_value is not None:
                return handle.readlines.return_value
            return list(_data)

        def _read_side_effect(*args, **kwargs):
            if handle.read.return_value is not None:
                return handle.read.return_value
            return ''.join(_data)

        def _readline_side_effect():
            if handle.readline.return_value is not None:
                while True:
                    yield handle.readline.return_value
            for line in _data:
                yield line


        global file_spec
        if file_spec is None:
            file_spec = file

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
