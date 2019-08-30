# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import sys
import errno
import logging
import tempfile

# Import 3rd-party libs
import pytest
import salt.ext.six as six

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


# ----- cmd.run redirect tests -------------------------------------------------------------------------------------->
@pytest.fixture
def run_redirect_test_file():
    # Create the testfile and release the handle
    fd, file_path = tempfile.mkstemp()
    try:
        os.close(fd)
    except OSError as exc:
        if exc.errno != errno.EBADF:
            six.reraise(*sys.exc_info())

    yield file_path

    try:
        os.unlink(file_path)
    except OSError:
        # Already gone
        pass


@pytest.fixture
def run_redirect_test_tmp_path():
    # Create the testfile and release the handle
    fd, file_path = tempfile.mkstemp()
    try:
        os.close(fd)
    except OSError as exc:
        if exc.errno != errno.EBADF:
            six.reraise(*sys.exc_info())

    yield file_path

    try:
        os.unlink(file_path)
    except OSError:
        # Already gone
        pass


@pytest.fixture
def run_redirect_state_name():
    return 'run_redirect'


@pytest.fixture
def run_redirect_state_file(run_redirect_state_name):
    state_filename = run_redirect_state_name + '.sls'
    state_file = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, state_filename)

    yield state_file

    try:
        os.unlink(state_file)
    except OSError:
        # Already gone, not even created
        pass


def test_run_unless(modules,
                    run_redirect_state_name,
                    run_redirect_state_file,
                    run_redirect_test_file,
                    run_redirect_test_tmp_path):
    '''
    test cmd.run unless
    '''
    state_key = 'cmd_|-{0}_|-{0}_|-run'.format(run_redirect_test_tmp_path)
    state_file_contents = '''
    {0}:
      cmd.run:
        - unless: echo cheese > {1}
    '''.format(run_redirect_test_tmp_path, run_redirect_test_file)

    with pytest.helpers.temp_state_file(run_redirect_state_name + '.sls', state_file_contents):
        ret = modules.state.sls(run_redirect_state_name)
    assert ret.result is True
    expected_changes = {}
    assert ret == {state_key: {'changes': expected_changes}}


def test_run_unless_multiple_cmds(modules):
    '''
    test cmd.run using multiple unless options where the first cmd in the
    list will pass, but the second will fail. This tests the fix for issue
    #35384. (The fix is in PR #35545.)
    '''
    state_key = 'cmd_|-cmd_run_unless_multiple_|-echo "hello"_|-run'
    state_name = 'issue-35384'
    state_contents = '''
    cmd_run_unless_multiple:
      cmd.run:
        - name: echo "hello"
        - unless:
          - "$(which true)"
          - "$(which false)"
    '''
    with pytest.helpers.temp_state_file(state_name + '.sls', state_contents) as f:
        log.warning('F\n\n\n: %s', f)
        ret = modules.state.sls(state_name)

    assert ret.result is True
    # We must assert against the comment here to make sure the comment reads that the
    # command "echo "hello"" was run. This ensures that we made it to the last unless
    # command in the state. If the comment reads "unless condition is true", or similar,
    # then the unless state run bailed out after the first unless command succeeded,
    # which is the bug we're regression testing for.
    assert ret == {state_key: {'comment': 'Command "echo "hello"" run'}}


def test_run_creates_exists(modules,
                            run_redirect_state_name,
                            run_redirect_test_file):
    '''
    test cmd.run creates already there
    '''
    state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(run_redirect_test_file)
    state_contents = '''
    echo >> {0}:
      cmd.run:
        - creates: {0}
    '''.format(run_redirect_test_file)
    with pytest.helpers.temp_state_file(run_redirect_state_name + '.sls', state_contents):
        ret = modules.state.sls(run_redirect_state_name)

    assert ret.result is True
    expected_changes = {}
    assert ret == {state_key: {'changes': expected_changes}}


def test_run_creates_new(modules,
                         run_redirect_state_name,
                         run_redirect_test_file):
    '''
    test cmd.run creates not there
    '''
    os.unlink(run_redirect_test_file)
    state_key = 'cmd_|-echo >> {0}_|-echo >> {0}_|-run'.format(run_redirect_test_file)
    state_contents = '''
    echo >> {0}:
      cmd.run:
        - creates: {0}
    '''.format(run_redirect_test_file)
    with pytest.helpers.temp_state_file(run_redirect_state_name + '.sls', state_contents):
        ret = modules.state.sls(run_redirect_state_name)

    assert ret.result is True
    expected_changes = {'retcode': 0, 'stdout': '', 'stderr': ''}
    assert ret == {state_key: {'changes': expected_changes}}


def test_run_redirect(modules,
                      run_redirect_state_name,
                      run_redirect_test_file):
    '''
    test cmd.run with shell redirect
    '''
    state_key = 'cmd_|-echo test > {0}_|-echo test > {0}_|-run'.format(run_redirect_test_file)
    state_contents = '''
    echo test > {0}:
      cmd.run
    '''.format(run_redirect_test_file)
    with pytest.helpers.temp_state_file(run_redirect_state_name + '.sls', state_contents):
        ret = modules.state.sls(run_redirect_state_name)

    assert ret.result is True
    expected_changes = {'retcode': 0, 'stdout': '', 'stderr': ''}
    assert ret == {state_key: {'changes': expected_changes}}
# <---- cmd.run redirect tests ---------------------------------------------------------------------------------------
