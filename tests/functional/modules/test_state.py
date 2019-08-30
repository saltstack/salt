# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
import textwrap

# Import salt libs
import salt.utils.files

# Import 3rd-party libs
import pytest
import salt.ext.six as six

log = logging.getLogger(__name__)


def test_show_highstate(modules):
    '''
    state.show_highstate
    '''
    with pytest.helpers.temp_file('test-file') as testfile_path:
        top_sls_contents = '''
        base:
          '*':
            - core
        '''
        core_sls_contents = '''
        {}:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
        '''.format(testfile_path)
        with pytest.helpers.temp_state_file('top.sls', top_sls_contents):
            with pytest.helpers.temp_state_file('core.sls', core_sls_contents):
                high = modules.state.show_highstate()
                assert isinstance(high, dict)
                assert testfile_path in high
                assert high[testfile_path]['__env__'] == 'base'


def test_show_lowstate(modules):
    '''
    state.show_lowstate
    '''
    with pytest.helpers.temp_file('test-file') as testfile_path:
        top_sls_contents = '''
        base:
          '*':
            - core
        '''
        core_sls_contents = '''
        {}:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
        '''.format(testfile_path)
        with pytest.helpers.temp_state_file('top.sls', top_sls_contents):
            with pytest.helpers.temp_state_file('core.sls', core_sls_contents):
                low = modules.state.show_lowstate()
                assert isinstance(low, list)
                assert isinstance(low[0], dict)


def test_show_states(modules):
    '''
    state.show_states
    '''
    with pytest.helpers.temp_file('test-file') as testfile_path:
        top_sls_contents = '''
        base:
          '*':
            - core
        '''
        core_sls_contents = '''
        {}:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
        '''.format(testfile_path)
        with pytest.helpers.temp_state_file('top.sls', top_sls_contents):
            with pytest.helpers.temp_state_file('core.sls', core_sls_contents):
                states = modules.state.show_states()
                assert isinstance(states, list)
                assert isinstance(states[0], six.string_types)

                states = modules.state.show_states(sorted=False)
                assert isinstance(states, list)
                assert isinstance(states[0], six.string_types)


def test_catch_recurse(modules):
    '''
    state.show_sls used to catch a recursive ref
    '''
    recurse_fail_sls_contents = '''
    mysql:
      service:
        - running
        - require:
          - file: /etc/mysql/my.cnf

    /etc/mysql/my.cnf:
      file:
        - managed
        - source: salt://master.cnf
        - require:
          - service: mysql
    '''
    with pytest.helpers.temp_state_file('recurse_fail.sls', recurse_fail_sls_contents):
        ret = modules.state.sls('recurse_fail')
        assert 'A recursive requisite was found' in ret


def test_no_recurse(modules):
    '''
    verify that a sls structure is NOT a recursive ref
    '''
    recurse_ok_sls_contents = '''
    snmpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: snmpd
        - watch:
          - file: /etc/snmp/snmpd.conf

    /etc/snmp/snmpd.conf:
      file:
        - managed
        - source: salt://snmpd/snmpd.conf.jinja
        - template: jinja
        - user: root
        - group: root
        - mode: "0600"
        - require:
          - pkg: snmpd
    '''
    with pytest.helpers.temp_state_file('recurse_ok.sls', recurse_ok_sls_contents):
        ret = modules.state.show_sls('recurse_ok')
        assert 'snmpd' in ret


def test_no_recurse_two(modules):
    '''
    verify that a sls structure is NOT a recursive ref
    '''
    recurse_ok_two_sls_contents = '''
    nagios-nrpe-server:
      pkg:
        - installed
      service:
        - running
        - watch:
          - file: /etc/nagios/nrpe.cfg

    /etc/nagios/nrpe.cfg:
      file:
        - managed
        - source: salt://baseserver/nrpe.cfg
        - require:
          - pkg: nagios-nrpe-server
    '''
    with pytest.helpers.temp_state_file('recurse_ok_two.sls', recurse_ok_two_sls_contents):
        ret = modules.state.show_sls('recurse_ok_two')
        assert '/etc/nagios/nrpe.cfg' in ret

    # Now including another state file
    recurse_ok_sls_contents = '''
    snmpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: snmpd
        - watch:
          - file: /etc/snmp/snmpd.conf

    /etc/snmp/snmpd.conf:
      file:
        - managed
        - source: salt://snmpd/snmpd.conf.jinja
        - template: jinja
        - user: root
        - group: root
        - mode: "0600"
        - require:
          - pkg: snmpd
    '''
    recurse_ok_two_sls_contents = '''
    include:
      - recurse_ok

    {}
    '''.format(recurse_ok_two_sls_contents)
    with pytest.helpers.temp_state_file('recurse_ok.sls', recurse_ok_sls_contents):
        with pytest.helpers.temp_state_file('recurse_ok_two.sls', recurse_ok_two_sls_contents):
            ret = modules.state.show_sls('recurse_ok_two')
            assert '/etc/nagios/nrpe.cfg' in ret
            assert 'snmpd' in ret


def test_running_dictionary_consistency(modules):
    '''
    Test the structure of the running dictionary so we don't change it
    without deprecating/documenting the change
    '''
    running_dict_fields = [
        '__id__',
        '__run_num__',
        '__sls__',
        'changes',
        'comment',
        'duration',
        'name',
        'result',
        'start_time',
    ]

    sls = modules.state.single(name='gndn', fun='test.succeed_with_changes')
    for ret in sls.values():
        for field in running_dict_fields:
            assert field in ret


def test_running_dictionary_key_sls(modules):
    '''
    Ensure the __sls__ key is either null or a string
    '''

    sls = modules.state.single(name='gndn', fun='test.succeed_with_changes')
    for ret in sls.values():
        assert ret['__sls__'] is None

    gndn_sls_contents = '''
    # Goes nowhere, does nothing.
    gndn:
      test.succeed_with_changes
    '''
    with pytest.helpers.temp_state_file('gndn.sls', gndn_sls_contents):
        sls = modules.state.sls('gndn')

        for ret in sls.values():
            assert isinstance(ret['__sls__'], six.string_types)


@pytest.fixture
def request_cache_file_deleted(sminion):
    '''
    remove minion state request file
    '''
    cache_file = os.path.join(sminion.opts['cachedir'], 'req_state.p')
    if os.path.exists(cache_file):
        os.remove(cache_file)
    # Run tests
    yield
    if os.path.exists(cache_file):
        os.remove(cache_file)


@pytest.mark.usefixtures('request_cache_file_deleted')
def test_request(modules):
    '''
    verify sending a state request to the minion(s)
    '''
    requested_sls_id = 'count_root_dir_contents'
    requested_sls_name = 'ls -a / | wc -l'
    requested_sls_contents = '''
    {}:
      cmd.run:
        - name: '{}'
    '''.format(requested_sls_id, requested_sls_name)
    state_id = 'cmd_|-{}_|-{}_|-run'.format(requested_sls_id, requested_sls_name)
    with pytest.helpers.temp_state_file('requested.sls', requested_sls_contents):
        ret = modules.state.request('requested')
        assert ret[state_id]['result'] is None


@pytest.mark.usefixtures('request_cache_file_deleted')
def test_check_request(modules):
    '''
    verify checking a state request sent to the minion(s)
    '''
    requested_sls_id = 'count_root_dir_contents'
    requested_sls_name = 'ls -a / | wc -l'
    requested_sls_contents = '''
    {}:
      cmd.run:
        - name: '{}'
    '''.format(requested_sls_id, requested_sls_name)
    state_id = 'cmd_|-{}_|-{}_|-run'.format(requested_sls_id, requested_sls_name)
    with pytest.helpers.temp_state_file('requested.sls', requested_sls_contents):
        ret = modules.state.request('requested')
        assert ret[state_id]['result'] is None

        ret = modules.state.check_request()
        assert ret['default']['test_run'][state_id]['result'] is None


@pytest.mark.usefixtures('request_cache_file_deleted')
def test_clear_request(modules):
    '''
    verify clearing a state request sent to the minion(s)
    '''
    requested_sls_id = 'count_root_dir_contents'
    requested_sls_name = 'ls -a / | wc -l'
    requested_sls_contents = '''
    {}:
      cmd.run:
        - name: '{}'
    '''.format(requested_sls_id, requested_sls_name)
    state_id = 'cmd_|-{}_|-{}_|-run'.format(requested_sls_id, requested_sls_name)
    with pytest.helpers.temp_state_file('requested.sls', requested_sls_contents):
        ret = modules.state.request('requested')
        assert ret[state_id]['result'] is None

        assert modules.state.clear_request() is True


@pytest.mark.usefixtures('request_cache_file_deleted')
def test_run_request_succeeded(modules, grains):
    '''
    verify running a state request sent to the minion(s)
    '''
    requested_sls_id = 'count_root_dir_contents'
    if grains.get('os_family', '') == 'Windows':
        requested_sls_name = 'Get-ChildItem C:\\ | Measure-Object | %{$_.Count}'
    else:
        requested_sls_name = 'ls -a / | wc -l'
    requested_sls_contents = '''
    {}:
      cmd.run:
        - name: '{}'
    '''.format(requested_sls_id, requested_sls_name)
    state_id = 'cmd_|-{}_|-{}_|-run'.format(requested_sls_id, requested_sls_name)
    with pytest.helpers.temp_state_file('requested.sls', requested_sls_contents):
        ret = modules.state.request('requested')
        assert ret[state_id]['result'] is None

        req = modules.state.run_request()
        assert req[state_id]['result'] is True


@pytest.mark.usefixtures('request_cache_file_deleted')
def test_run_request_failed_no_request_staged(modules):
    '''
    verify not running a state request sent to the minion(s)
    '''
    requested_sls_id = 'count_root_dir_contents'
    requested_sls_name = 'ls -a / | wc -l'
    requested_sls_contents = '''
    {}:
      cmd.run:
        - name: '{}'
    '''.format(requested_sls_id, requested_sls_name)
    state_id = 'cmd_|-{}_|-{}_|-run'.format(requested_sls_id, requested_sls_name)
    with pytest.helpers.temp_state_file('requested.sls', requested_sls_contents):
        ret = modules.state.request('requested')
        assert ret[state_id]['result'] is None

        assert modules.state.clear_request() is True

        req = modules.state.run_request()
        assert req == {}


def test_issue_1879_too_simple_contains_check(modules, grains):
    with pytest.helpers.temp_file('issue-1879') as testfile:
        step_1_contents = '''
        {}:
          file.append:
            - text: |
                # set variable identifying the chroot you work in (used in the prompt below)
                if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
                    debian_chroot=$(cat /etc/debian_chroot)
                fi
        '''.format(testfile)
        step_2_contents = '''
        {}:
          file.append:
            - text: |
                # enable bash completion in interactive shells
                if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
                    . /etc/bash_completion
                fi
        '''.format(testfile)

        expected = textwrap.dedent('''\
            # set variable identifying the chroot you work in (used in the prompt below)
            if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
                debian_chroot=$(cat /etc/debian_chroot)
            fi
            # enable bash completion in interactive shells
            if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
                . /etc/bash_completion
            fi
            ''')

        if grains.get('os_family', '') == 'Windows':
            expected = os.linesep.join(expected.splitlines())

        with pytest.helpers.temp_state_file('step-1.sls', step_1_contents), \
                pytest.helpers.temp_state_file('step-2.sls', step_2_contents):

            # The first append
            ret = modules.state.sls('step-1')
            assert ret.result is True

            # The second append
            ret = modules.state.sls('step-2')
            assert ret.result is True

            # Does it match?
            with salt.utils.files.fopen(testfile, 'r') as fp_:
                contents = salt.utils.stringutils.to_unicode(fp_.read())

                assert contents == expected

            # Make sure we don't re-append existing text
            # The first append
            ret = modules.state.sls('step-1')
            assert ret.result is True

            # The second append
            ret = modules.state.sls('step-2')
            assert ret.result is True

            with salt.utils.files.fopen(testfile, 'r') as fp_:
                contents = salt.utils.stringutils.to_unicode(fp_.read())

                assert contents == expected


def test_issue_1876_syntax_error(modules):
    '''
    verify that we catch the following syntax error:

        /tmp/salttest/issue-1876:

          file:
            - managed
            - source: salt://testfile

          file.append:
            - text: foo

    '''
    with pytest.helpers.temp_file('issue-1876') as testfile:
        sls_contents = '''
        {}:
          file:
            - managed
            - source: salt://testfile

          file.append:
            - text: foo
        '''.format(testfile)

        with pytest.helpers.temp_state_file('issue-1876.sls', sls_contents):
            ret = modules.state.sls('issue-1876')
            error_msg = (
                'ID \'{}\' in SLS \'issue-1876\' contains multiple state declarations of '
                'the same type'.format(testfile)
            )
            assert error_msg in ret


def test_include(modules):
    with pytest.helpers.temp_directory() as tempdir:
        include_test_path = os.path.join(tempdir, 'include-test')
        include_test_sls_contents = '''
        include:
          - to-include-test

        {}:
          file.managed:
            - source: salt://testfile
        '''.format(include_test_path)

        to_include_test_path = os.path.join(tempdir, 'to-include-test')
        to_include_test_sls_contents = '''
        {}:
          file.managed:
            - source: salt://testfile
        '''.format(to_include_test_path)

        exclude_test_path = os.path.join(tempdir, 'exclude-test')
        exclude_test_sls_contents = '''
        exclude:
          - to-include-test

        include:
          - include-test

        {}:
          file.managed:
            - source: salt://testfile
        '''.format(exclude_test_path)

        with pytest.helpers.temp_state_file('include-test.sls', include_test_sls_contents), \
                pytest.helpers.temp_state_file('to-include-test.sls', to_include_test_sls_contents), \
                pytest.helpers.temp_state_file('exclude-test.sls', exclude_test_sls_contents):
            ret = modules.state.sls('include-test')
            assert ret.result is True
            assert os.path.isfile(include_test_path)
            assert os.path.isfile(to_include_test_path)
            assert os.path.isfile(exclude_test_path) is False


def test_exclude(modules):
    with pytest.helpers.temp_directory() as tempdir:
        include_test_path = os.path.join(tempdir, 'include-test')
        include_test_sls_contents = '''
        include:
          - to-include-test

        {}:
          file.managed:
            - source: salt://testfile
        '''.format(include_test_path)

        to_include_test_path = os.path.join(tempdir, 'to-include-test')
        to_include_test_sls_contents = '''
        {}:
          file.managed:
            - source: salt://testfile
        '''.format(to_include_test_path)

        exclude_test_path = os.path.join(tempdir, 'exclude-test')
        exclude_test_sls_contents = '''
        exclude:
          - to-include-test

        include:
          - include-test

        {}:
          file.managed:
            - source: salt://testfile
        '''.format(exclude_test_path)

        with pytest.helpers.temp_state_file('include-test.sls', include_test_sls_contents), \
                pytest.helpers.temp_state_file('to-include-test.sls', to_include_test_sls_contents), \
                pytest.helpers.temp_state_file('exclude-test.sls', exclude_test_sls_contents):
            ret = modules.state.sls('exclude-test')
            assert ret.result is True
            assert os.path.isfile(include_test_path)
            assert os.path.isfile(exclude_test_path)
            assert os.path.isfile(to_include_test_path) is False


def test_issue_2068_template_str(modules):
    sls_contents = '''
    required_state:
      test:
        - succeed_without_changes

    requiring_state:
      test:
        - succeed_without_changes
        - require:
          - test: required_state
    '''
    with pytest.helpers.temp_state_file('issue-2068.sls', sls_contents) as template_path:
        ret = modules.state.sls('issue-2068')
        assert ret.result is True

        # If running this state with state.sls works, so should using state.template_str
        ret = modules.state.template_str(sls_contents)
        assert ret.result is True

        # Now using state.template
        ret = modules.state.template(template_path)
        assert ret.result is True

    sls_contents = '''
    required_state: test.succeed_without_changes

    requiring_state:
      test.succeed_without_changes:
        - require:
          - test: required_state
    '''
    with pytest.helpers.temp_state_file('issue-2068.sls', sls_contents) as template_path:
        ret = modules.state.sls('issue-2068')
        assert ret.result is True

        # If running this state with state.sls works, so should using state.template_str
        ret = modules.state.template_str(sls_contents)
        assert ret.result is True

        # Now using state.template
        ret = modules.state.template(template_path)
        assert ret.result is True


def test_template_invalid_items(modules):
    sls_contents = textwrap.dedent('''
        {}:
          - issue-2068-template-str

        /tmp/test-template-invalid-items:
          file:
            - managed
            - source: salt://testfile
        ''')
    for item in ('include', 'exclude', 'extends'):
        ret = modules.state.template_str(sls_contents.format(item))
        error_msg = (
            'The \'{}\' declaration found on \'<template-str>\' is invalid when '
            'rendering single templates'.format(item)
        )
        assert isinstance(ret, list)
        assert error_msg in ret


def test_pydsl(modules):
    '''
    Test the basics of the pydsl
    '''
    with pytest.helpers.temp_file('pydsl.test') as testfile:
        sls_contents = '''
        #!pydsl

        #__pydsl__.set(ordered=True)

        state('{}').file('touch')
        '''.format(testfile)
        with pytest.helpers.temp_state_file('pydsl-1.sls', sls_contents):
            ret = modules.state.sls('pydsl-1')
            assert ret.result is True


def test_issues_7905_and_8174_sls_syntax_error(modules):
    '''
    Call sls file with yaml syntax error.

    Ensure theses errors are detected and presented to the user without
    stack traces.
    '''
    sls_name = 'syntax-badlist'
    sls_contents = '''
    # Missing " " between "-" and "foo" or "name"
    A:
      cmd.run:
        -name: echo foo
        -foo:
          - bar
    '''
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == ['State \'A\' in SLS \'{}\' is not formed as a list'.format(sls_name)]

    sls_contents = '''
    # C should fail with bad list error message
    B:
      # ok
      file.exist:
        - name: /foo/bar/foobar
    # ok
    /foo/bar/foobar:
      file.exist

    # nok
    C:
      /foo/bar/foobar:
        file.exist
    '''
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == ['State \'C\' in SLS \'{}\' is not formed as a list'.format(sls_name)]


def test_requisites_mixed_require_prereq_use(modules):
    '''
    Call sls file containing several requisites.
    '''
    sls_name = 'mixed-simple'
    sls_contents = '''
    # Simple mix between prereq and require
    # C (1) <--+ <------+
    #          |        |
    # B (2) -p-+ <-+    |
    #              |    |
    # A (3) --r----+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B
        - require_in:
          - cmd: A

    # infinite recursion.....?
    C:
      cmd.run:
        - name: echo C
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
            - cmd: B
    '''
    expected_simple_result = {
        'cmd_|-A_|-echo A_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo A" run',
            'result': True,
            'changes': {'retcode': 0}
        },
        'cmd_|-B_|-echo B_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo B" run',
            'result': True,
            'changes': {'retcode': 0}
        },
        'cmd_|-C_|-echo C_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo C" run',
            'result': True,
            'changes': {'retcode': 0}
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_simple_result

    # test Traceback recursion prereq+require #8785
    # TODO: this is actually failing badly
    sls_name = 'prereq_require_recursion_error2'
    sls_contents = '''
    # issue #8785
    # B <--+ ----r-+
    #      |       |
    # A -p-+ <-----+-- ERROR: cannot respect both require and prereq

    A:
      cmd.run:
        - name: echo A
        - require_in:
          - cmd: B

    # infinite recursion.....?
    B:
      cmd.run:
        - name: echo B
        # will test A and be applied only if A changes,
        # and then will run before A
        - prereq:
            - cmd: A
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "prereq_require_recursion_error2" ID "B" ID "A"'

    # test Infinite recursion prereq+require #8785 v2
    # TODO: this is actually failing badly
    sls_name = 'prereq_require_recursion_error3'
    sls_contents = '''
    # issue #8785 RuntimeError: maximum recursion depth exceeded
    # C <--+ <------+ -r-+
    #      |        |    |
    # B -p-+ <-+    | <--+-- ERROR: cannot respect both require and prereq
    #          |    |
    # A --r----+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B
        - require_in:
          - cmd: A
          # this should raise the error
          - cmd: C

    # infinite recursion.....?
    C:
      cmd.run:
        - name: echo C
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
            - cmd: B
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "prereq_require_recursion_error3" ID "B" ID "A"'

    # test Infinite recursion prereq+require #8785 v3
    # TODO: this is actually failing badly, and expected result is maybe not a recursion
    sls_name = 'prereq_require_recursion_error4'
    sls_contents = '''
    # issue #8785
    #
    # Here it's more complex. Order SHOULD be ok.
    # When B changes something the require is verified.
    # What should happen if B does not chane anything?
    # It should also run because of the require.
    # Currently we have:
    # RuntimeError: maximum recursion depth exceeded

    # B (1) <---+ <--+
    #           |    |
    # A (2) -r--+ -p-+

    A:
      cmd.run:
        - name: echo A
        # is running in test mode before B
        # B gets executed first if this states modify something
        # key of bug
        - prereq_in:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        # B should run before A
        - require_in:
          - cmd: A
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "prereq_require_recursion_error4" ID "B" ID "A"'

    sls_name = 'mixed_complex1'
    sls_contents = '''
    # Complex require/require_in/prereq/preqreq_in graph
    #
    #
    # D (1) <--------r-----+
    #                      |
    # C (2) <--+ <-----p-------+
    #          |           |   |
    # B (3) -p-+ <-+ <-+ --+   |
    #              |   |       |
    # E (4) ---r---|---+ <-+   |
    #              |       |   |
    # A (5) --r----+ ---r--+ --+
    #

    A:
      cmd.run:
        - name: echo A fifth
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    B:
      cmd.run:
        - name: echo B third
        - require_in:
          - cmd: A

    # infinite recursion.....
    C:
      cmd.run:
        - name: echo C second
        # will test B and be applied only if B changes,
        # and then will run before B
        - prereq:
          - cmd: B

    D:
      cmd.run:
        - name: echo D first
        # issue #8773
        # this will generate a warning but will still be done
        - require_in:
          cmd.foo: B

    E:
      cmd.run:
        - name: echo E fourth
        - require:
          - cmd: B
        - require_in:
          - cmd: A
    '''

    expected_return = {
        'cmd_|-A_|-echo A fifth_|-run': {
            '__run_num__': 4,
            'comment': 'Command "echo A fifth" run',
            'result': True,
            'changes': {'retcode': 0}},
        'cmd_|-B_|-echo B third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo B third" run',
            'result': True,
            'changes': {'retcode': 0}},
        'cmd_|-C_|-echo C second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C second" run',
            'result': True,
            'changes': {'retcode': 0}},
        'cmd_|-D_|-echo D first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo D first" run',
            'result': True,
            'changes': {'retcode': 0}},
        'cmd_|-E_|-echo E fourth_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo E fourth" run',
            'result': True,
            'changes': {'retcode': 0}}
    }
    # undetected infinite loopS prevents this test from running...
    # TODO: this is actually failing badly
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == expected_return


def test_watch_in(modules):
    '''
    test watch_in requisite when there is a success
    '''
    sls_name = 'watch_in'
    sls_contents = '''
    return_changes:
      test.succeed_with_changes:
        - watch_in:
          - test: watch_states

    watch_states:
      test.succeed_without_changes
    '''
    expected_output = {
        'RE:.*return_changes.*': {
            '__run_num__': 0,
            'changes': {
                'testing': {
                    'new': 'Something pretended to change',
                    'old': 'Unchanged'
                }
            }
        },
        'RE:.*watch_states.*': {
            '__run_num__': 2,
            'result': True,
            'comment': 'Watch statement fired.'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_output


def test_watch_in_failure(modules):
    '''
    test watch_in requisite when there is a failure
    '''
    sls_name = 'watch_in_failure'
    sls_contents = '''
    return_changes:
      test.fail_with_changes:
        - watch_in:
          - test: watch_states

    watch_states:
      test.succeed_without_changes
    '''
    expected_return = {
        'RE:.*return_changes.*': {
            '__run_num__': 0,
            'result': False
        },
        'RE:.*watch_states.*': {
            '__run_num__': 1,
            'result': False,
            'comment': 'One or more requisite failed: watch_in_failure.return_changes'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_require_ordering_and_errors(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'require'
    sls_contents = '''
    # Complex require/require_in graph
    #
    # Relative order of C>E is given by the definition order
    #
    # D (1) <--+
    #          |
    # B (2) ---+ <-+ <-+ <-+
    #              |   |   |
    # C (3) <--+ --|---|---+
    #          |   |   |
    # E (4) ---|---|---+ <-+
    #          |   |       |
    # A (5) ---+ --+ ------+
    #

    A:
      cmd.run:
        - name: echo A fifth
        - require:
          - cmd: C
    B:
      cmd.run:
        - name: echo B second
        - require_in:
          - cmd: A
          - cmd: C

    C:
      cmd.run:
        - name: echo C third

    D:
      cmd.run:
        - name: echo D first
        - require_in:
          - cmd: B

    E:
      cmd.run:
        - name: echo E fourth
        - require:
          - cmd: B
        - require_in:
          - cmd: A

    # will fail with "The following requisites were not found"
    F:
      cmd.run:
        - name: echo F
        - require:
          - foobar: A
    # will fail with "The following requisites were not found"
    G:
      cmd.run:
        - name: echo G
        - require:
          - cmd: Z
    # will fail with "The following requisites were not found"
    H:
      cmd.run:
        - name: echo H
        - require:
          - cmd: Z
    '''
    expected_return = {
        'cmd_|-A_|-echo A fifth_|-run': {
            '__run_num__': 4,
            'comment': 'Command "echo A fifth" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-B_|-echo B second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo B second" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-C_|-echo C third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo C third" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-D_|-echo D first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo D first" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-E_|-echo E fourth_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo E fourth" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-F_|-echo F_|-run': {
            '__run_num__': 5,
            'comment': 'The following requisites were not found:\n'
                       + '                   require:\n'
                       + '                       foobar: A\n',
            'result': False,
            'changes': {},
        },
        'cmd_|-G_|-echo G_|-run': {
            '__run_num__': 6,
            'comment': 'The following requisites were not found:\n'
                       + '                   require:\n'
                       + '                       cmd: Z\n',
            'result': False,
            'changes': {},
        },
        'cmd_|-H_|-echo H_|-run': {
            '__run_num__': 7,
            'comment': 'The following requisites were not found:\n'
                       + '                   require:\n'
                       + '                       cmd: Z\n',
            'result': False,
            'changes': {},
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return

    sls_name = 'require_error1'
    sls_contents = '''
    # will fail with "Data failed to compile:"
    A:
      cmd.run:
        - name: echo A
        - require_in:
          - foobar: W
    '''
    expected_error = (
        "Cannot extend ID 'W' in 'base:require_error1'. It is not part of the high state.\n"
        "This is likely due to a missing include statement or an incorrectly typed ID.\n"
        "Ensure that a state with an ID of 'W' is available\n"
        "in environment 'base' and to SLS 'require_error1'"
    )
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_error

    # issue #8235
    # FIXME: Why is require enforcing list syntax while require_in does not?
    # And why preventing it?
    # Currently this state fails, should return C/B/A
    sls_name = 'require_simple_nolist'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo A
    B:
      cmd.run:
        - name: echo B
        # here used without "-"
        - require:
            cmd: A
    C:
      cmd.run:
        - name: echo C
        # here used without "-"
        - require_in:
            cmd: A
    '''
    expected_error = (
        "The require statement in state 'B' in SLS "
        "'require_simple_nolist' needs to be formed as a list"
    )
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_error

    sls_name = 'require_recursion_error1'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo A
        - require:
          - cmd: B

    B:
      cmd.run:
        - name: echo B
        - require:
          - cmd: A
    '''
    expected_error = (
        'A recursive requisite was found, SLS "require_recursion_error1" ID "B" ID "A"'
    )
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_error

    # commented until a fix is made for issue #8772
    # TODO: this test actually fails
    sls_name = 'require_error2'
    sls_contents = '''
    # issue #8772
    # should fail with "Data failed to compile:"
    B:
      cmd.run:
        - name: echo B last
        - require_in:
          # state foobar does not exists in A
          - foobar: A

    A:
      cmd.run:
        - name: echo A first
    '''
    expected_error = (
        'Cannot extend state foobar for ID A in "base:require_error2".'
        ' It is not part of the high state.'
    )
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert isinstance(ret, list)
    #    assert ret == expected_error


def test_requisites_require_any(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'require_any'
    sls_contents = '''
    # Complex require/require_in graph
    #
    # Relative order of C>E is given by the definition order
    #
    # D (1) <--+
    #          |
    # B (2) ---+ <-+ <-+ <-+
    #              |   |   |
    # C (3) <--+ --|---|---+
    #          |   |   |
    # E (4) ---|---|---+ <-+
    #          |   |       |
    # A (5) ---+ --+ ------+
    #

    # A should success since B succeeds even though C fails.
    A:
      cmd.run:
        - name: echo A
        - require_any:
          - cmd: B
          - cmd: C
          - cmd: D
    B:
      cmd.run:
        - name: echo B

    C:
      cmd.run:
        - name: "$(which false)"

    D:
      cmd.run:
        - name: echo D
    '''
    expected_return = {
        'cmd_|-A_|-echo A_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo A" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-B_|-echo B_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B" run',
            'result': True,
            'changes': {'retcode': 0},
        },
        'cmd_|-C_|-$(which false)_|-run': {
            '__run_num__': 1,
            'comment': 'Command "$(which false)" run',
            'result': False,
            # Not including changes since the retcode depends on the shell
            #'changes': {'retcode': 123},
        },
        'cmd_|-D_|-echo D_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo D" run',
            'result': True,
            'changes': {'retcode': 0},
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_require_any_fail(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'require_any_fail'
    sls_contents = '''
    # D should fail since both E & F fail
    E:
      cmd.run:
        - name: 'false'

    F:
      cmd.run:
        - name: 'false'

    D:
      cmd.run:
        - name: echo D
        - require_any:
          - cmd: E
          - cmd: F
    '''
    expected_return = {
        'RE:.*E.*': {'result': False, '__run_num__': 0},
        'RE:.*F.*': {'result': False, '__run_num__': 1},
        'RE:.*D.*': {'result': False, '__run_num__': 2, 'comment': 'One or more requisite failed'}
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_watch_any(modules, grains):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    if grains.get('os_family', '') == 'Windows':
        cmd_true = 'exit'
        cmd_false = 'exit /B 1'
    else:
        cmd_true = 'true'
        cmd_false = 'false'

    sls_name = 'watch_any'
    sls_contents = '''
    A:
      cmd.wait:
        - name: '{cmd_true}'
        - watch_any:
          - cmd: B
          - cmd: C
          - cmd: D

    B:
      cmd.run:
        - name: '{cmd_true}'

    C:
      cmd.run:
        - name: '{cmd_false}'

    D:
      cmd.run:
        - name: '{cmd_true}'

    E:
      cmd.wait:
        - name: '{cmd_true}'
        - watch_any:
          - cmd: F
          - cmd: G
          - cmd: H

    F:
      cmd.run:
        - name: '{cmd_true}'

    G:
      cmd.run:
        - name: '{cmd_false}'

    H:
      cmd.run:
        - name: '{cmd_false}'
    '''.format(cmd_true=cmd_true, cmd_false=cmd_false)

    expected_return = {
        'cmd_|-A_|-{}_|-wait'.format(cmd_true): {
            '__run_num__': 4,
            'comment': 'Command "{}" run'.format(cmd_true),
            'result': True,
        },
        'cmd_|-B_|-{}_|-run'.format(cmd_true): {
            '__run_num__': 0,
            'comment': 'Command "{}" run'.format(cmd_true),
            'result': True,
        },
        'cmd_|-C_|-{}_|-run'.format(cmd_false): {
            '__run_num__': 1,
            'comment': 'Command "{}" run'.format(cmd_false),
            'result': False,
        },
        'cmd_|-D_|-{}_|-run'.format(cmd_true): {
            '__run_num__': 2,
            'comment': 'Command "{}" run'.format(cmd_true),
            'result': True,
        },
        'cmd_|-E_|-{}_|-wait'.format(cmd_true): {
            '__run_num__': 9,
            'comment': 'Command "{}" run'.format(cmd_true),
            'result': True,
        },
        'cmd_|-F_|-{}_|-run'.format(cmd_true): {
            '__run_num__': 5,
            'comment': 'Command "{}" run'.format(cmd_true),
            'result': True,
        },
        'cmd_|-G_|-{}_|-run'.format(cmd_false): {
            '__run_num__': 6,
            'comment': 'Command "{}" run'.format(cmd_false),
            'result': False,
        },
        'cmd_|-H_|-{}_|-run'.format(cmd_false): {
            '__run_num__': 7,
            'comment': 'Command "{}" run'.format(cmd_false),
            'result': False,
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_watch_any_fail(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'watch_any_fail'
    sls_contents = '''
    A:
      cmd.wait:
        - name: 'true'
        - watch_any:
          - cmd: B
          - cmd: C

    B:
      cmd.run:
        - name: 'false'

    C:
      cmd.run:
        - name: 'false'
    '''
    expected_return = {
        'RE:.*B.*': {'result': False, '__run_num__': 0},
        'RE:.*C.*': {'result': False, '__run_num__': 1},
        'RE:.*A.*': {'result': False, '__run_num__': 2, 'comment': 'One or more requisite failed'}
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_onchanges_any(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'onchanges_any'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    another_changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes

    another_non_changing_state:
      test.succeed_without_changes

    # Should succeed since at least one will have changes
    test_one_changing_states:
      cmd.run:
        - name: echo "Success!"
        - onchanges_any:
          - cmd: changing_state
          - cmd: another_changing_state
          - test: non_changing_state
          - test: another_non_changing_state

    test_two_non_changing_states:
      cmd.run:
        - name: echo "Should not run"
        - onchanges_any:
          - test: non_changing_state
          - test: another_non_changing_state
    '''
    expected_return = {
        'cmd_|-another_changing_state_|-echo "Changed!"_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo "Changed!"" run',
            'result': True
        },
        'cmd_|-changing_state_|-echo "Changed!"_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo "Changed!"" run',
            'result': True
        },
        'cmd_|-test_one_changing_states_|-echo "Success!"_|-run': {
            '__run_num__': 4,
            'comment': 'Command "echo "Success!"" run',
            'result': True
        },
        'cmd_|-test_two_non_changing_states_|-echo "Should not run"_|-run': {
            '__run_num__': 5,
            'comment': 'State was not run because none of the onchanges reqs changed',
            'result': True
        },
        'test_|-another_non_changing_state_|-another_non_changing_state_|-succeed_without_changes': {
            '__run_num__': 3,
            'comment': 'Success!',
            'result': True
        },
        'test_|-non_changing_state_|-non_changing_state_|-succeed_without_changes': {
            '__run_num__': 2,
            'comment': 'Success!',
            'result': True
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_onfail_any(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'onfail_any'
    sls_contents = '''
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 1

    c:
      cmd.run:
        - name: exit 0

    d:
      cmd.run:
        - name: echo itworked
        - onfail_any:
          - cmd: a
          - cmd: b
          - cmd: c

    e:
      cmd.run:
        - name: exit 0

    f:
      cmd.run:
        - name: exit 0

    g:
      cmd.run:
        - name: exit 0

    h:
      cmd.run:
        - name: echo itworked
        - onfail_any:
          - cmd: e
          - cmd: f
          - cmd: g
    '''
    expected_return = {
        'cmd_|-a_|-exit 0_|-run': {
            '__run_num__': 0,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-b_|-exit 1_|-run': {
            '__run_num__': 1,
            'changes': {'retcode': 1},
            'comment': 'Command "exit 1" run',
            'result': False
        },
        'cmd_|-c_|-exit 0_|-run': {
            '__run_num__': 2,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-d_|-echo itworked_|-run': {
            '__run_num__': 3,
            'changes': {'retcode': 0},
            'comment': 'Command "echo itworked" run',
            'result': True},
        'cmd_|-e_|-exit 0_|-run': {
            '__run_num__': 4,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-f_|-exit 0_|-run': {
            '__run_num__': 5,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-g_|-exit 0_|-run': {
            '__run_num__': 6,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-h_|-echo itworked_|-run': {
            '__run_num__': 7,
            'changes': {},
            'comment': 'State was not run because onfail req did not change',
            'result': True
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_onfail_all(modules):
    '''
    Call sls file containing several onfail-all

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'onfail_all'
    sls_contents = '''
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 0

    c:
      cmd.run:
        - name: exit 0

    d:
      cmd.run:
        - name: exit 1

    e:
      cmd.run:
        - name: exit 1

    f:
      cmd.run:
        - name: exit 1

    reqs not met:
      cmd.run:
        - name: echo itdidntonfail
        - onfail_all:
          - cmd: a
          - cmd: e

    reqs also not met:
      cmd.run:
        - name: echo italsodidnonfail
        - onfail_all:
          - cmd: a
          - cmd: b
          - cmd: c

    reqs met:
      cmd.run:
        - name: echo itonfailed
        - onfail_all:
          - cmd: d
          - cmd: e
          - cmd: f

    reqs also met:
      cmd.run:
        - name: echo itonfailed
        - onfail_all:
          - cmd: d
        - require:
          - cmd: a
    '''
    expected_return = {
        'cmd_|-a_|-exit 0_|-run': {
            '__run_num__': 0,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-b_|-exit 0_|-run': {
            '__run_num__': 1,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-c_|-exit 0_|-run': {
            '__run_num__': 2,
            'changes': {'retcode': 0},
            'comment': 'Command "exit 0" run',
            'result': True
        },
        'cmd_|-d_|-exit 1_|-run': {
            '__run_num__': 3,
            'changes': {'retcode': 1},
            'comment': 'Command "exit 1" run',
            'result': False
        },
        'cmd_|-e_|-exit 1_|-run': {
            '__run_num__': 4,
            'changes': {'retcode': 1},
            'comment': 'Command "exit 1" run',
            'result': False
        },
        'cmd_|-f_|-exit 1_|-run': {
            '__run_num__': 5,
            'changes': {'retcode': 1},
            'comment': 'Command "exit 1" run',
            'result': False
        },
        'cmd_|-reqs also met_|-echo itonfailed_|-run': {
            '__run_num__': 9,
            'changes': {'retcode': 0},
            'comment': 'Command "echo itonfailed" run',
            'result': True
        },
        'cmd_|-reqs also not met_|-echo italsodidnonfail_|-run': {
            '__run_num__': 7,
            'changes': {},
            'comment':
            'State was not run because onfail req did not change',
            'result': True
        },
        'cmd_|-reqs met_|-echo itonfailed_|-run': {
            '__run_num__': 8,
            'changes': {'retcode': 0},
            'comment': 'Command "echo itonfailed" run',
            'result': True
        },
        'cmd_|-reqs not met_|-echo itdidntonfail_|-run': {
            '__run_num__': 6,
            'changes': {},
            'comment':
            'State was not run because onfail req did not change',
            'result': True
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_full_sls(modules):
    '''
    Teste the sls special command in requisites
    '''
    sls_name = 'fullsls_require'
    sls_contents = '''
    include:
      - fullsls_test
    A:
      cmd.run:
        - name: echo A
        - require:
          - sls: fullsls_test
    '''
    fullsls_test_contents = '''
    B:
      cmd.run:
        - name: echo B
    C:
      cmd.run:
        - name: echo C
    '''
    expected_return = {
        'cmd_|-A_|-echo A_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo A" run',
            'result': True,
            'changes': {'retcode': 0}
        },
        'cmd_|-B_|-echo B_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B" run',
            'result': True,
            'changes': {'retcode': 0}
        },
        'cmd_|-C_|-echo C_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C" run',
            'result': True,
            'changes': {'retcode': 0}
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        with pytest.helpers.temp_state_file('fullsls_test.sls', fullsls_test_contents):
            ret = modules.state.sls(sls_name)
            assert ret == expected_return

    sls_name = 'fullsls_prereq'
    sls_contents = '''
    include:
      - fullsls_test
    A:
      cmd.run:
        - name: echo A
        - prereq:
          - sls: fullsls_test
    '''
    # issue #8233: traceback on prereq sls
    # TODO: not done
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    with pytest.helpers.temp_state_file('fullsls_test.sls', fullsls_test_contents):
    #        ret = modules.state.sls(sls_name)
    #        assert ret == 'sls command can only be used with require requisite'


def test_requisites_require_no_state_module(modules):
    '''
    Call sls file containing several require_in and require.

    Ensure that some of them are failing and that the order is right.
    '''
    sls_name = 'require_no_state_module'
    sls_contents = '''
    # Complex require/require_in graph
    #
    # Relative order of C>E is given by the definition order
    #
    # D (1) <--+
    #          |
    # B (2) ---+ <-+ <-+ <-+
    #              |   |   |
    # C (3) <--+ --|---|---+
    #          |   |   |
    # E (4) ---|---|---+ <-+
    #          |   |       |
    # A (5) ---+ --+ ------+
    #

    A:
      cmd.run:
        - name: echo A fifth
        - require:
          - C
    B:
      cmd.run:
        - name: echo B second
        - require_in:
          - A
          - C

    C:
      cmd.run:
        - name: echo C third

    D:
      cmd.run:
        - name: echo D first
        - require_in:
          - B

    E:
      cmd.run:
        - name: echo E fourth
        - require:
          - B
        - require_in:
          - A

    # will fail with "The following requisites were not found"
    G:
      cmd.run:
        - name: echo G
        - require:
          - Z
    # will fail with "The following requisites were not found"
    H:
      cmd.run:
        - name: echo H
        - require:
          - Z
    '''
    expected_return = {
        'cmd_|-A_|-echo A fifth_|-run': {
            '__run_num__': 4,
            'comment': 'Command "echo A fifth" run',
            'result': True,
        },
        'cmd_|-B_|-echo B second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo B second" run',
            'result': True,
        },
        'cmd_|-C_|-echo C third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo C third" run',
            'result': True,
        },
        'cmd_|-D_|-echo D first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo D first" run',
            'result': True,
        },
        'cmd_|-E_|-echo E fourth_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo E fourth" run',
            'result': True,
        },
        'cmd_|-G_|-echo G_|-run': {
            '__run_num__': 5,
            'comment': 'The following requisites were not found:\n'
                       + '                   require:\n'
                       + '                       id: Z\n',
            'result': False,
        },
        'cmd_|-H_|-echo H_|-run': {
            '__run_num__': 6,
            'comment': 'The following requisites were not found:\n'
                       + '                   require:\n'
                       + '                       id: Z\n',
            'result': False,
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_return


def test_requisites_prereq_simple_ordering_and_errors(modules):
    '''
    Call sls file containing several prereq_in and prereq.

    Ensure that some of them are failing and that the order is right.
    '''
    # XXX: Use pytest-subtests once we go py3 only
    sls_name = 'prereq_simple'
    sls_contents = '''
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C
    C:
      cmd.run:
        - name: echo C second

    # will fail with "The following requisites were not found"
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - cmd: Z
    J:
      cmd.run:
        - name: echo J
        - prereq:
          - foobar: A
    '''
    expected_result_simple = {
        'cmd_|-A_|-echo A third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo A third" run',
            'result': True,
        },
        'cmd_|-B_|-echo B first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B first" run',
            'result': True,
        },
        'cmd_|-C_|-echo C second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C second" run',
            'result': True,
        },
        'cmd_|-I_|-echo I_|-run': {
            '__run_num__': 3,
            'comment': 'The following requisites were not found:\n'
                       + '                   prereq:\n'
                       + '                       cmd: Z\n',
            'result': False,
        },
        'cmd_|-J_|-echo J_|-run': {
            '__run_num__': 4,
            'comment': 'The following requisites were not found:\n'
                       + '                   prereq:\n'
                       + '                       foobar: A\n',
            'result': False,
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_simple

    sls_name = 'prereq_simple_nolist'
    sls_contents = '''
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
           cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
            cmd: C
    C:
      cmd.run:
        - name: echo C second
    '''
    expected_result_simple_nolist = {
        'cmd_|-A_|-echo A third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo A third" run',
            'result': True,
        },
        'cmd_|-B_|-echo B first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B first" run',
            'result': True,
        },
        'cmd_|-C_|-echo C second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C second" run',
            'result': True,
        },
    }
    # same test, but not using lists in yaml syntax
    # TODO: issue #8235, prereq ignored when not used in list syntax
    # Currently fails badly with :
    # TypeError encountered executing state.sls: string indices must be integers, not str.
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == expected_result_simple_nolist

    sls_name = 'prereq_simple2'
    sls_contents = '''
    #
    # Theory:
    #
    # C <--+ <--+ <-+ <-+
    #      |    |   |   |
    # A ---+    |   |   |
    #           |   |   |
    # B --------+   |   |
    #               |   |
    # D-------------+   |
    #                   |
    # E-----------------+

    # runs after C
    A:
      cmd.run:
        - name: echo A
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    B:
      cmd.run:
        - name: echo B

    # runs before D and B
    C:
      cmd.run:
        - name: echo C
        # will test D and be applied only if D changes,
        # and then will run before D. Same for B
        - prereq:
          - cmd: B
          - cmd: D

    D:
      cmd.run:
        - name: echo D

    E:
      cmd.run:
        - name: echo E
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C
    '''
    expected_result_simple2 = {
        'cmd_|-A_|-echo A_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo A" run',
            'result': True,
        },
        'cmd_|-B_|-echo B_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo B" run',
            'result': True,
        },
        'cmd_|-C_|-echo C_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo C" run',
            'result': True,
        },
        'cmd_|-D_|-echo D_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo D" run',
            'result': True,
        },
        'cmd_|-E_|-echo E_|-run': {
            '__run_num__': 4,
            'comment': 'Command "echo E" run',
            'result': True,
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_simple2

    sls_name = 'prereq_simple3'
    sls_contents = '''
    # A --+
    #     |
    # B <-+ ----+
    #           |
    # C <-------+

    # runs before A and/or B
    A:
      cmd.run:
        - name: echo A first
        # is running in test mode before B/C
        - prereq:
          - cmd: B
          - cmd: C

    # always has to run
    B:
      cmd.run:
        - name: echo B second

    # never has to run
    C:
      cmd.wait:
        - name: echo C third
    '''
    expected_result_simple3 = {
        'cmd_|-A_|-echo A first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo A first" run',
            'result': True,
        },
        'cmd_|-B_|-echo B second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo B second" run',
            'result': True,
        },
        'cmd_|-C_|-echo C third_|-wait': {
            '__run_num__': 2,
            'comment': '',
            'result': True,
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_simple3

    sls_name = 'prereq_error_nolist'
    sls_contents = '''
    # will fail with 'Cannot extend ID Z (...) not part of the high state.'
    # and not "The following requisites were not found" like in yaml list syntax
    I:
      cmd.run:
        - name: echo I
        - prereq:
            cmd: Z
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == (
    #        'Cannot extend ID Z in "base:prereq_error_nolist".'
    #        ' It is not part of the high state.'
    #    )

    sls_name = 'prereq_compile_error1'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: A
    '''
    expected_result_compile_error1 = {
        'RE:.*A.*': {'result': True, '__run_num__': 0},
        'RE:.*B.*': {
            'result': False,
            '__run_num__': 1,
            'comment': 'The following requisites were not found:\n'
                       '                   prereq:\n'
                       '                       foobar: A\n'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_compile_error1

    sls_name = 'prereq_compile_error2'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo A

    B:
      cmd.run:
        - name: echo B
        - prereq:
          - foobar: C
    '''
    expected_result_compile_error2 = {
        'RE:.*A.*': {'result': True, '__run_num__': 0},
        'RE:.*B.*': {
            'result': False,
            '__run_num__': 1,
            'comment': 'The following requisites were not found:\n'
                       '                   prereq:\n'
                       '                       foobar: C\n'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_compile_error2

    sls_name = 'prereq_complex'
    sls_contents = '''
    # issue #8211
    #             expected rank
    # B --+             1
    #     |
    # C <-+ ----+       2/3
    #           |
    # D ---+    |       3/2
    #      |    |
    # A <--+ <--+       4
    #
    #             resulting rank
    # D --+
    #     |
    # A <-+ <==+
    #          |
    # B --+    +--> unrespected A prereq_in C (FAILURE)
    #     |    |
    # C <-+ ===+

    # runs after C
    A:
      cmd.run:
        - name: echo A fourth
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - cmd: C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - cmd: C

    C:
      cmd.run:
        - name: echo C second
        # replacing A prereq_in C by theses lines
        # changes nothing actually
        #- prereq:
        #  - cmd: A

    # Removing D, A gets executed after C
    # as described in (A prereq_in C)
    # runs before A
    D:
      cmd.run:
        - name: echo D third
        # will test A and be applied only if A changes,
        # and then will run before A
        - prereq:
          - cmd: A
    '''
    expected_result_complex = {
        'cmd_|-A_|-echo A fourth_|-run': {
            '__run_num__': 3,
            'comment': 'Command "echo A fourth" run',
            'result': True,
        },
        'cmd_|-B_|-echo B first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B first" run',
            'result': True,
        },
        'cmd_|-C_|-echo C second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C second" run',
            'result': True,
        },
        'cmd_|-D_|-echo D third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo D third" run',
            'result': True,
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_complex

    sls_name = 'prereq_recursion_error'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo A
        - prereq_in:
          - cmd: B
    B:
      cmd.run:
        - name: echo B
        - prereq_in:
          - cmd: A
    '''
    # issue #8210 : prereq recursion undetected
    # TODO: this test fails
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "prereq_recursion_error" ID "B" ID "A"'

    sls_name = 'prereq_simple_no_state_module'
    sls_contents = '''
    # B --+
    #     |
    # C <-+ ----+
    #           |
    # A <-------+

    # runs after C
    A:
      cmd.run:
        - name: echo A third
        # is running in test mode before C
        # C gets executed first if this states modify something
        - prereq_in:
          - C

    # runs before C
    B:
      cmd.run:
        - name: echo B first
        # will test C and be applied only if C changes,
        # and then will run before C
        - prereq:
          - C
    C:
      cmd.run:
        - name: echo C second

    # will fail with "The following requisites were not found"
    I:
      cmd.run:
        - name: echo I
        - prereq:
          - Z
    '''
    expected_result_simple_no_state_module = {
        'cmd_|-A_|-echo A third_|-run': {
            '__run_num__': 2,
            'comment': 'Command "echo A third" run',
            'result': True,
        },
        'cmd_|-B_|-echo B first_|-run': {
            '__run_num__': 0,
            'comment': 'Command "echo B first" run',
            'result': True,
        },
        'cmd_|-C_|-echo C second_|-run': {
            '__run_num__': 1,
            'comment': 'Command "echo C second" run',
            'result': True,
        },
        'cmd_|-I_|-echo I_|-run': {
            '__run_num__': 3,
            'comment': 'The following requisites were not found:\n'
                       + '                   prereq:\n'
                       + '                       id: Z\n',
            'result': False,
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result_simple_no_state_module


def test_infinite_recursion_sls_prereq(modules):
    include_sls_name = 'prereq_sls_infinite_recursion_2'
    include_sls_contents = '''
    B:
      test.succeed_without_changes:
        - name: B
    '''
    sls_name = 'prereq_sls_infinite_recursion'
    sls_contents = '''
    include:
      - {0}
    A:
      test.succeed_without_changes:
        - name: A
        - prereq:
          - sls: {0}
    '''.format(include_sls_name)
    with pytest.helpers.temp_state_file(include_sls_name +'.sls', include_sls_contents):
        with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
            ret = modules.state.sls(sls_name)
            assert ret.result is True


def test_requisites_use(modules):
    '''
    Call sls file containing several use_in and use.

    '''
    # TODO issue #8235 & #8774 some examples are still commented in the test file
    sls_name = 'use'
    sls_contents = '''
    # None of theses states should run
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: 'false'

    # issue #8235
    #B:
    #  cmd.run:
    #    - name: echo "B"
    #  # here used without "-"
    #    - use:
    #        cmd: A

    C:
      cmd.run:
        - name: echo "C"
        - use:
            - cmd: A

    D:
      cmd.run:
        - name: echo "D"
        - onlyif: 'false'
        - use_in:
            - cmd: E

    E:
      cmd.run:
        - name: echo "E"

    # issue 8235
    #F:
    #  cmd.run:
    #    - name: echo "F"
    #    - onlyif: return 0
    #    - use_in:
    #        cmd: G
    #
    #G:
    #  cmd.run:
    #    - name: echo "G"

    # issue xxxx
    #H:
    #  cmd.run:
    #    - name: echo "H"
    #    - use:
    #        - cmd: C
    #I:
    #  cmd.run:
    #    - name: echo "I"
    #    - use:
    #        - cmd: E
    '''
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        for state_entry in ret.values():
            assert state_entry['comment'] == 'onlyif condition is false'

    # TODO: issue #8802 : use recursions undetected
    # issue is closed as use does not actually inherit requisites
    # if chain-use is added after #8774 resolution theses tests would maybe become useful
    sls_name = 'use_recursion'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: return False
        - use:
            cmd: B

    B:
      cmd.run:
        - name: echo "B"
        - unless: return False
        - use:
            cmd: A
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "use_recursion" ID "B" ID "A"'

    sls_name = 'use_recursion2'
    sls_contents = '''
    #
    # A <--+ ---u--+
    #      |       |
    # B -u-+ <-+   |
    #          |   |
    # C -u-----+ <-+

    A:
      cmd.run:
        - name: echo "A"
        - use:
            cmd: C

    B:
      cmd.run:
        - name: echo "B"
        - use:
            cmd: C

    C:
      cmd.run:
        - name: echo "B"
        - use:
            cmd: A
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "use_recursion2" ID "C" ID "A"'

    sls_name = 'use_auto_recursion'
    sls_contents = '''
    A:
      cmd.run:
        - name: echo "A"
        - use:
            cmd: A
    '''
    #with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
    #    ret = modules.state.sls(sls_name)
    #    assert ret == 'A recursive requisite was found, SLS "use_auto_recursion" ID "A" ID "A"'


def test_requisites_use_no_state_module(modules):
    '''
    Call sls file containing several use_in and use.

    '''
    sls_name = 'use_no_state_module'
    sls_contents = '''
    # None of theses states should run
    A:
      cmd.run:
        - name: echo "A"
        - onlyif: 'false'

    # issue #8235
    #B:
    #  cmd.run:
    #    - name: echo "B"
    #  # here used without "-"
    #    - use:
    #        cmd: A

    C:
      cmd.run:
        - name: echo "C"
        - use:
            - A

    D:
      cmd.run:
        - name: echo "D"
        - onlyif: 'false'
        - use_in:
            - E

    E:
      cmd.run:
        - name: echo "E"

    # issue 8235
    #F:
    #  cmd.run:
    #    - name: echo "F"
    #    - onlyif: return 0
    #    - use_in:
    #        cmd: G
    #
    #G:
    #  cmd.run:
    #    - name: echo "G"

    # issue xxxx
    #H:
    #  cmd.run:
    #    - name: echo "H"
    #    - use:
    #        - cmd: C
    #I:
    #  cmd.run:
    #    - name: echo "I"
    #    - use:
    #        - cmd: E
    '''
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        for state_entry in ret.values():
            assert state_entry['comment'] == 'onlyif condition is false'


def test_onlyif_req(modules):
    expected_result = {
        'RE:.*onlyif test.*': {'result': True, 'comment': 'Success!'}
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='onlyif test', onlyif=[{}])
    assert ret == expected_result

    expected_result = {
        'RE:.*onlyif test.*': {'result': True, 'comment': 'onlyif condition is false', 'changes': {}}
    }
    ret = modules.state.single(fun='test.fail_with_changes', name='onlyif test', onlyif=[{'fun': 'test.false'}])
    assert ret == expected_result

    expected_result = {
        'RE:.*onlyif test.*': {
            'result': False,
            'comment': 'Failure!',
            'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}
        }
    }
    ret = modules.state.single(fun='test.fail_with_changes', name='onlyif test', onlyif=[{'fun': 'test.true'}])
    assert ret == expected_result

    expected_result = {
        'RE:.*onlyif test.*': {'result': True, 'comment': 'Success!', 'changes': {}}
    }
    ret = modules.state.single(fun='test.succeed_without_changes', name='onlyif test', onlyif=[{'fun': 'test.true'}])
    assert ret == expected_result


def test_onlyif_req_retcode(modules):
    expected_result = {
        'RE:.*onlyif test.*': {'result': True, 'comment': 'onlyif condition is false', 'changes': {}}
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='onlyif test', onlyif=[{'fun': 'test.retcode'}])
    assert ret == expected_result
    expected_result = {
        'RE:.*onlyif test.*': {
            'result': True,
            'comment': 'Success!',
            'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}
        }
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='onlyif test', onlyif=[{'fun': 'test.retcode', 'code': 0}])
    assert ret == expected_result


def test_unless_req(modules):
    expected_result = {
        'RE:.*unless test.*': {
            'result': True,
            'comment': 'Success!',
        }
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='unless test', unless=[{}])
    assert ret == expected_result

    expected_result = {
        'RE:.*unless test.*': {
            'result': True,
            'comment': 'unless condition is true',
            'changes': {}
        }
    }
    ret = modules.state.single(fun='test.fail_with_changes', name='unless test', unless=[{'fun': 'test.true'}])
    assert ret == expected_result

    expected_result = {
        'RE:.*unless test.*': {
            'result': False,
            'comment': 'Failure!',
            'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}
        }
    }
    ret = modules.state.single(fun='test.fail_with_changes', name='unless test', unless=[{'fun': 'test.false'}])
    assert ret == expected_result

    expected_result = {
        'RE:.*unless test.*': {
            'result': True,
            'comment': 'Success!',
            'changes': {}
        }
    }
    ret = modules.state.single(fun='test.succeed_without_changes', name='unless test', unless=[{'fun': 'test.false'}])
    assert ret == expected_result


def test_unless_req_retcode(modules):
    expected_result = {
        'RE:.*unless test.*': {
            'result': True,
            'comment': 'Success!',
            'changes': {'testing': {'new': 'Something pretended to change', 'old': 'Unchanged'}}
        }
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='unless test', unless=[{'fun': 'test.retcode'}])
    assert ret == expected_result

    expected_result = {
        'RE:.*unless test.*': {
            'result': True,
            'comment': 'unless condition is true',
            'changes': {}
        }
    }
    ret = modules.state.single(fun='test.succeed_with_changes', name='unless test', unless=[{'fun': 'test.retcode', 'code': 0}])
    assert ret == expected_result


def test_get_file_from_env_in_top_match(modules):
    with pytest.helpers.temp_file('testfile') as testfile_tgt:
        with pytest.helpers.temp_file('prod-cheese-file') as cheese_tgt:
            base_top_sls_contents = '''
            base:
              '*':
                - core
            '''

            prod_top_sls_contents = '''
            prod:
              'G@role:functional-testing':
                - match: compound
                - issue-8196
            '''

            core_sls_contents = '''
            {}:
              file:
                - managed
                - source: salt://testfile
                - makedirs: true
            '''.format(testfile_tgt)

            issue_8196_sls_contents = '''
            {}:
              file.managed:
                - source: salt://cheese
            '''.format(cheese_tgt)

            prod_cheese_file_contents = '''
            I could just fancy some cheese, Gromit. What do you say? Cheddar? Comte?
            '''
            with pytest.helpers.temp_state_file('top.sls', base_top_sls_contents), \
                    pytest.helpers.temp_state_file('core.sls', core_sls_contents), \
                    pytest.helpers.temp_state_file('top.sls', prod_top_sls_contents, saltenv='prod'), \
                    pytest.helpers.temp_state_file('issue-8196.sls', issue_8196_sls_contents, saltenv='prod'), \
                    pytest.helpers.temp_state_file('cheese', prod_cheese_file_contents, saltenv='prod'):
                ret = modules.state.highstate()
                assert ret.result is True
                assert os.path.isfile(testfile_tgt)
                assert os.path.isfile(cheese_tgt)
                with salt.utils.files.fopen(cheese_tgt, 'r') as cheese:
                    data = salt.utils.stringutils.to_unicode(cheese.read())
                assert 'Gromit' in data
                assert 'Comte' in data


# onchanges tests


def test_onchanges_requisite(modules):
    '''
    Tests a simple state using the onchanges requisite
    '''
    sls_name = 'onchanges_simple'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
        test.succeed_without_changes

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
    '''
    expected_result = {
        'RE:.*changing_state.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*non_changing_state': {
            'result': True,
            '__run_num__': 1,
            'changes': {}
        },
        'RE:.*test_changing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_changing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because none of the onchanges reqs changed'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onchanges_requisite_multiple(modules):
    '''
    Tests a simple state using the onchanges requisite
    '''
    sls_name = 'onchanges_multiple'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    another_changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes

    another_non_changing_state:
      test.succeed_without_changes

    test_two_changing_states:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state
          - cmd: another_changing_state

    test_two_non_changing_states:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
          - test: another_non_changing_state

    test_one_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state
          - test: non_changing_state
    '''
    expected_result = {
        'RE:.*-changing_state.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*another_changing_state.*': {
            'result': True,
            '__run_num__': 1
        },
        'RE:.*-non_changing_state': {
            'result': True,
            '__run_num__': 2,
            'changes': {}
        },
        'RE:.*another_non_changing_state': {
            'result': True,
            '__run_num__': 3,
            'changes': {}
        },
        'RE:.*test_two_changing_states.*': {
            'result': True,
            '__run_num__': 4,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_two_non_changing_states.*': {
            'result': True,
            '__run_num__': 5,
            'comment': 'State was not run because none of the onchanges reqs changed'
        },
        'RE:.*test_one_changing_state.*': {
            'result': True,
            '__run_num__': 6,
            'comment': 'Command "echo "Success!"" run'
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onchanges_in_requisite(modules):
    '''
    Tests a simple state using the onchanges_in requisite
    '''
    sls_name = 'onchanges_in_simple'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"
        - onchanges_in:
          - cmd: test_changes_expected

    non_changing_state:
      test.succeed_without_changes:
        - onchanges_in:
          - cmd: test_changes_not_expected

    test_changes_expected:
      cmd.run:
        - name: echo "Success!"

    test_changes_not_expected:
      cmd.run:
        - name: echo "Should not run"
    '''
    expected_result = {
        'RE:.*-changing_state.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*non_changing_state.*': {
            'result': True,
            '__run_num__': 1,
        },
        'RE:.*test_changes_expected.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_changes_not_expected.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because none of the onchanges reqs changed'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onchanges_requisite_no_state_module(modules):
    '''
    Tests a simple state using the onchanges requisite without state modules
    '''
    sls_name = 'onchanges_simple_no_state_module'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
      test.succeed_without_changes

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - non_changing_state
    '''
    expected_result = {
        'RE:.*changing_state.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*non_changing_state': {
            'result': True,
            '__run_num__': 1,
            'changes': {}
        },
        'RE:.*test_changing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_changing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because none of the onchanges reqs changed'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onchanges_requisite_with_duration(modules):
    '''
    Tests a simple state using the onchanges requisite
    the state will not run but results will include duration
    '''
    sls_name = 'onchanges_simple'
    sls_contents = '''
    changing_state:
      cmd.run:
        - name: echo "Changed!"

    non_changing_state:
        test.succeed_without_changes

    test_changing_state:
      cmd.run:
        - name: echo "Success!"
        - onchanges:
          - cmd: changing_state

    test_non_changing_state:
      cmd.run:
        - name: echo "Should not run"
        - onchanges:
          - test: non_changing_state
    '''
    expected_result = {
        'RE:.*changing_state.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*non_changing_state': {
            'result': True,
            '__run_num__': 1,
            'changes': {}
        },
        'RE:.*test_changing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_changing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because none of the onchanges reqs changed',
            'duration': '0.*'
        }
    }
    # Then, test the result of the state run when changes are not expected to happen
    # and ensure duration is included in the results
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onfail_requisite(modules):
    '''
    Tests a simple state using the onfail requisite
    '''
    sls_name = 'onfail_simple'
    sls_contents = '''
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - cmd: failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - cmd: non_failing_state
    '''
    expected_result = {
        'RE:.*failing_state.*': {
            'result': False,
            '__run_num__': 0
        },
        'RE:.*non_failing_state': {
            'result': True,
            '__run_num__': 1,
        },
        'RE:.*test_failing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_failing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because onfail req did not change',
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_multiple_onfail_requisite(modules):
    '''
    test to ensure state is run even if only one
    of the onfails fails. This is a test for the issue:
    https://github.com/saltstack/salt/issues/22370
    '''
    sls_name = 'onfail_multiple'
    sls_contents = '''
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: exit 1

    c:
      cmd.run:
        - name: echo itworked
        - onfail:
          - cmd: a
          - cmd: b
    '''
    expected_result = {
        'RE:.*a.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*b.*': {
            'result': False,
            '__run_num__': 1
        },
        'RE:.*c.*': {
            'result': True,
            '__run_num__': 2,
            'changes': {'retcode': 0, 'stdout': 'itworked', 'stderr': ''}
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onfail_in_requisite(modules):
    '''
    Tests a simple state using the onfail_in requisite
    '''
    sls_name = 'onfail_in_simple'
    sls_contents = '''
    failing_state:
      cmd.run:
        - name: asdf
        - onfail_in:
          - cmd: test_failing_state

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"
        - onfail_in:
          - cmd: test_non_failing_state

    test_failing_state:
      cmd.run:
        - name: echo "Success!"

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
    '''
    expected_result = {
        'RE:.*failing_state.*': {
            'result': False,
            '__run_num__': 0
        },
        'RE:.*non_failing_state': {
            'result': True,
            '__run_num__': 1,
        },
        'RE:.*test_failing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_failing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because onfail req did not change',
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onfail_requisite_no_state_module(modules):
    '''
    Tests a simple state using the onfail requisite
    '''
    sls_name = 'onfail_simple_no_state_module'
    sls_contents = '''
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - non_failing_state
    '''
    expected_result = {
        'RE:.*failing_state.*': {
            'result': False,
            '__run_num__': 0
        },
        'RE:.*non_failing_state': {
            'result': True,
            '__run_num__': 1,
        },
        'RE:.*test_failing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_failing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because onfail req did not change',
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_onfail_requisite_with_duration(modules):
    '''
    Tests a simple state using the onfail requisite
    '''
    sls_name = 'onfail_simple'
    sls_contents = '''
    failing_state:
      cmd.run:
        - name: asdf

    non_failing_state:
      cmd.run:
        - name: echo "Non-failing state"

    test_failing_state:
      cmd.run:
        - name: echo "Success!"
        - onfail:
          - cmd: failing_state

    test_non_failing_state:
      cmd.run:
        - name: echo "Should not run"
        - onfail:
          - cmd: non_failing_state
    '''
    expected_result = {
        'RE:.*failing_state.*': {
            'result': False,
            '__run_num__': 0
        },
        'RE:.*non_failing_state': {
            'result': True,
            '__run_num__': 1,
        },
        'RE:.*test_failing_state.*': {
            'result': True,
            '__run_num__': 2,
            'comment': 'Command "echo "Success!"" run'
        },
        'RE:.*test_non_failing_state.*': {
            'result': True,
            '__run_num__': 3,
            'comment': 'State was not run because onfail req did not change',
            'duration': '0.*'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_multiple_onfail_requisite_with_required(modules):
    '''
    test to ensure multiple states are run
    when specified as onfails for a single state.
    This is a test for the issue:
    https://github.com/saltstack/salt/issues/46552
    '''
    sls_name = 'onfail_multiple_required'
    sls_contents = '''
    a:
      cmd.run:
        - name: exit 1

    pass:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: echo b
        - onfail:
          - cmd: a

    c:
      cmd.run:
        - name: echo c
        - onfail:
          - cmd: a
        - require:
          - cmd: b

    d:
      cmd.run:
        - name: echo d
        - onfail:
          - cmd: a
        - require:
          - cmd: c

    e:
      cmd.run:
        - name: echo e
        - onfail:
          - cmd: pass
        - require:
          - cmd: c

    f:
      cmd.run:
        - name: echo f
        - onfail:
          - cmd: pass
        - onchanges:
          - cmd: b
    '''
    expected_result = {
        'RE:.*a.*': {
            'result': False,
            '__run_num__': 0
        },
        'RE:.*pass.*': {
            'result': True,
            '__run_num__': 1
        },
        'RE:.*b.*': {
            'result': True,
            '__run_num__': 2,
            'changes': {'retcode': 0, 'stdout': 'b'}
        },
        'RE:.*c.*': {
            'result': True,
            '__run_num__': 3,
            'changes': {'retcode': 0, 'stdout': 'c'}
        },
        'RE:.*d.*': {
            'result': True,
            '__run_num__': 4,
            'changes': {'retcode': 0, 'stdout': 'd'}
        },
        'RE:.*e.*': {
            'result': True,
            '__run_num__': 5,
            'changes': {},
            'comment': 'State was not run because onfail req did not change'
        },
        'RE:.*f.*': {
            'result': True,
            '__run_num__': 6,
            'changes': {'retcode': 0, 'stdout': 'f'}
        },
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_multiple_onfail_requisite_with_required_no_run(modules):
    '''
    test to ensure multiple states are not run
    when specified as onfails for a single state
    which fails.
    This is a test for the issue:
    https://github.com/saltstack/salt/issues/46552
    '''
    sls_name = 'onfail_multiple_required_no_run'
    sls_contents = '''
    a:
      cmd.run:
        - name: exit 0

    b:
      cmd.run:
        - name: echo b
        - onfail:
          - cmd: a

    c:
      cmd.run:
        - name: echo c
        - onfail:
          - cmd: a
        - require:
          - cmd: b

    d:
      cmd.run:
        - name: echo d
        - onfail:
          - cmd: a
        - require:
          - cmd: c
    '''
    expected_result = {
        'RE:.*a.*': {
            'result': True,
            '__run_num__': 0
        },
        'RE:.*b.*': {
            'result': True,
            '__run_num__': 2,
            'changes': {},
            'comment': 'State was not run because onfail req did not change'
        },
        'RE:.*c.*': {
            'result': True,
            '__run_num__': 3,
            'changes': {},
            'comment': 'State was not run because onfail req did not change'
        },
        'RE:.*d.*': {
            'result': True,
            '__run_num__': 4,
            'changes': {},
            'comment': 'State was not run because onfail req did not change'
        }
    }
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        assert ret == expected_result


def test_listen_requisite(modules):
    '''
    Tests a simple state using the listen requisite
    '''
    sls_name = 'listen_simple'
    sls_contents = '''
    successful_changing_state:
      cmd.run:
        - name: echo "Successful Change"

    non_changing_state:
      test.succeed_without_changes

    test_listening_change_state:
      cmd.run:
        - name: echo "Listening State"
        - listen:
          - cmd: successful_changing_state

    # This state should actually not run, it should not be part of the states ran
    test_listening_non_changing_state:
      cmd.run:
        - name: echo "Only run once"
        - listen:
          - test: non_changing_state

    # test that requisite resolution for listen uses ID declaration.
    # test_listening_resolution_one and test_listening_resolution_two
    # should both run.
    test_listening_resolution_one:
      cmd.run:
        - name: echo "Successful listen resolution"
        - listen:
          - cmd: successful_changing_state

    test_listening_resolution_two:
      cmd.run:
        - name: echo "Successful listen resolution"
        - listen:
          - cmd: successful_changing_state
    '''
    expected_return = {
        'cmd_|-successful_changing_state_|-echo "Successful Change"_|-run': {
            '__id__': 'successful_changing_state',
            '__run_num__': 0,
            '__saltfunc__': 'cmd.run',
            'changes': {'retcode': 0,
                        'stderr': '',
                        'stdout': 'Successful Change'},
            'comment': 'Command "echo "Successful Change"" run',
            'name': 'echo "Successful Change"',
            'result': True,
        },
        'test_|-non_changing_state_|-non_changing_state_|-succeed_without_changes': {
            '__id__': 'non_changing_state',
            '__run_num__': 1,
            '__saltfunc__': 'test.succeed_without_changes',
            '__sls__': 'listen_simple',
            'changes': {},
            'comment': 'Success!',
            'name': 'non_changing_state',
            'result': True,
        },
        'cmd_|-test_listening_change_state_|-echo "Listening State"_|-run': {
            '__id__': 'test_listening_change_state',
            '__run_num__': 2,
            '__saltfunc__': 'cmd.run',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Listening State'},
            'comment': 'Command "echo "Listening State"" run',
            'name': 'echo "Listening State"',
            'result': True,
        },
        'cmd_|-test_listening_non_changing_state_|-echo "Only run once"_|-run': {
            '__id__': 'test_listening_non_changing_state',
            '__run_num__': 3,
            '__saltfunc__': 'cmd.run',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Only run once'},
            'comment': 'Command "echo "Only run once"" run',
            'name': 'echo "Only run once"',
            'result': True,
        },
        'cmd_|-test_listening_resolution_one_|-echo "Successful listen resolution"_|-run': {
            '__id__': 'test_listening_resolution_one',
            '__run_num__': 4,
            '__saltfunc__': 'cmd.run',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Successful listen resolution'},
            'comment': 'Command "echo "Successful listen resolution"" run',
            'name': 'echo "Successful listen resolution"',
            'result': True,
        },
        'cmd_|-test_listening_resolution_two_|-echo "Successful listen resolution"_|-run': {
            '__id__': 'test_listening_resolution_two',
            '__run_num__': 5,
            '__saltfunc__': 'cmd.run',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Successful listen resolution'},
            'comment': 'Command "echo "Successful listen resolution"" run',
            'name': 'echo "Successful listen resolution"',
            'result': True,
        },
        'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch': {
            '__id__': 'listener_test_listening_change_state',
            '__run_num__': 6,
            '__saltfunc__': 'cmd.mod_watch',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Listening State'},
            'comment': 'Command "echo "Listening State"" run',
            'name': 'echo "Listening State"',
            'result': True,
        },
        'cmd_|-listener_test_listening_resolution_one_|-echo "Successful listen resolution"_|-mod_watch': {
            '__id__': 'listener_test_listening_resolution_one',
            '__run_num__': 7,
            '__saltfunc__': 'cmd.mod_watch',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Successful listen resolution'},
            'comment': 'Command "echo "Successful listen resolution"" run',
            'name': 'echo "Successful listen resolution"',
            'result': True,
        },
        'cmd_|-listener_test_listening_resolution_two_|-echo "Successful listen resolution"_|-mod_watch': {
            '__id__': 'listener_test_listening_resolution_two',
            '__run_num__': 8,
            '__saltfunc__': 'cmd.mod_watch',
            '__sls__': 'listen_simple',
            'changes': {'retcode': 0, 'stderr': '', 'stdout': 'Successful listen resolution'},
            'comment': 'Command "echo "Successful listen resolution"" run',
            'name': 'echo "Successful listen resolution"',
            'result': True,
        },
    }

    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        # Let's assert against the full expected return
        assert ret == expected_return
        # However, the short testing of this scenario is:
        #  - test the result of the state run when a listener is expected to trigger
        state_keys = ret.keys()
        assert 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch' in state_keys
        #  - test the result of the state run when a listener should not trigger
        assert 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch' not in state_keys


def test_listen_in_requisite(modules):
    '''
    Tests a simple state using the listen_in requisite
    '''
    sls_name = 'listen_in_simple'
    sls_contents = '''
    successful_changing_state:
      cmd.run:
        - name: echo "Successful Change"
        - listen_in:
          - cmd: test_listening_change_state

    non_changing_state:
      test.succeed_without_changes:
        - listen_in:
          - cmd: test_listening_non_changing_state

    test_listening_change_state:
      cmd.run:
        - name: echo "Listening State"

    test_listening_non_changing_state:
      cmd.run:
        - name: echo "Only run once"

    # test that requisite resolution for listen_in uses ID declaration.
    # test_listen_in_resolution should run.
    test_listen_in_resolution:
      cmd.wait:
        - name: echo "Successful listen_in resolution"

    successful_changing_state_name_foo:
      test.succeed_with_changes:
        - name: foo
        - listen_in:
          - cmd: test_listen_in_resolution

    successful_non_changing_state_name_foo:
      test.succeed_without_changes:
        - name: foo
        - listen_in:
          - cmd: test_listen_in_resolution
    '''
    with pytest.helpers.temp_state_file(sls_name +'.sls', sls_contents):
        ret = modules.state.sls(sls_name)
        state_keys = ret.keys()
        #  - test the result of the state run when a listener is expected to trigger
        state_keys = ret.keys()
        assert 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch' in state_keys
        #  - test the result of the state run when a listener should not trigger
        assert 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch' not in state_keys
