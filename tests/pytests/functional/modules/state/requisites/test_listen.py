import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_listen_requisite(state, state_tree):
    """
    Tests a simple state using the listen requisite
    """
    sls_contents = """
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
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        listener_state = (
            'cmd_|-listener_test_listening_change_state_|-echo "Listening'
            ' State"_|-mod_watch'
        )
        assert listener_state in ret

        absent_state = (
            'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run'
            ' once"_|-mod_watch'
        )
        assert absent_state not in ret


def test_listen_in_requisite(state, state_tree):
    """
    Tests a simple state using the listen_in requisite
    """
    sls_contents = """
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
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")

        listener_state = (
            'cmd_|-listener_test_listening_change_state_|-echo "Listening'
            ' State"_|-mod_watch'
        )
        assert listener_state in ret
        absent_state = (
            'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run'
            ' once"_|-mod_watch'
        )
        assert absent_state not in ret


def test_listen_in_requisite_resolution(state, state_tree):
    """
    Verify listen_in requisite lookups use ID declaration to check for changes
    """
    sls_contents = """
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
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        listener_state = (
            'cmd_|-listener_test_listen_in_resolution_|-echo "Successful listen_in'
            ' resolution"_|-mod_watch'
        )
        assert listener_state in ret


def test_listen_requisite_resolution(state, state_tree):
    """
    Verify listen requisite lookups use ID declaration to check for changes
    """
    sls_contents = """
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
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        listener_state = (
            'cmd_|-listener_test_listening_resolution_one_|-echo "Successful listen'
            ' resolution"_|-mod_watch'
        )
        assert listener_state in ret


def test_listen_requisite_no_state_module(state, state_tree):
    """
    Tests a simple state using the listen requisite
    """
    sls_contents = """
    successful_changing_state:
      cmd.run:
        - name: echo "Successful Change"

    non_changing_state:
      test.succeed_without_changes

    test_listening_change_state:
      cmd.run:
        - name: echo "Listening State"
        - listen:
          - successful_changing_state

    test_listening_non_changing_state:
      cmd.run:
        - name: echo "Only run once"
        - listen:
          - non_changing_state

    # test that requisite resolution for listen uses ID declaration.
    # test_listening_resolution_one and test_listening_resolution_two
    # should both run.
    test_listening_resolution_one:
      cmd.run:
        - name: echo "Successful listen resolution"
        - listen:
          - successful_changing_state

    test_listening_resolution_two:
      cmd.run:
        - name: echo "Successful listen resolution"
        - listen:
          - successful_changing_state
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        listener_state = (
            'cmd_|-listener_test_listening_change_state_|-echo "Listening'
            ' State"_|-mod_watch'
        )
        assert listener_state in ret

        absent_state = (
            'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run'
            ' once"_|-mod_watch'
        )
        assert absent_state not in ret


def test_listen_in_requisite_resolution_names(state, state_tree):
    """
    Verify listen_in requisite lookups use ID declaration to check for changes
    and resolves magic names state variable
    """
    sls_contents = """
    test:
      test.succeed_with_changes:
        - name: test
        - listen_in:
          - test: service

    service:
      test.succeed_without_changes:
        - names:
          - nginx
          - crond
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert "test_|-listener_service_|-nginx_|-mod_watch" in ret
        assert "test_|-listener_service_|-crond_|-mod_watch" in ret


def test_listen_requisite_resolution_names(state, state_tree):
    """
    Verify listen requisite lookups use ID declaration to check for changes
    and resolves magic names state variable
    """
    sls_contents = """
    test:
      test.succeed_with_changes:
        - name: test

    service:
      test.succeed_without_changes:
        - names:
          - nginx
          - crond
        - listen:
          - test: test
    """
    with pytest.helpers.temp_file("requisite.sls", sls_contents, state_tree):
        ret = state.sls("requisite")
        assert "test_|-listener_service_|-nginx_|-mod_watch" in ret
        assert "test_|-listener_service_|-crond_|-mod_watch" in ret


def test_onlyif_req(state, subtests):
    onlyif = [{}]
    with subtests.test(onlyif=onlyif):
        ret = state.single(
            name="onlyif test", fun="test.succeed_with_changes", onlyif=onlyif
        )
        assert ret.result is True
        assert ret.comment == "Success!"

    onlyif = [{"fun": "test.true"}]
    with subtests.test(onlyif=onlyif):
        ret = state.single(
            name="onlyif test", fun="test.succeed_without_changes", onlyif=onlyif
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Success!"

    onlyif = [{"fun": "test.false"}]
    with subtests.test(onlyif=onlyif):
        ret = state.single(
            name="onlyif test", fun="test.fail_with_changes", onlyif=onlyif
        )
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "onlyif condition is false"

    onlyif = [{"fun": "test.true"}]
    with subtests.test(onlyif=onlyif):
        ret = state.single(
            name="onlyif test", fun="test.fail_with_changes", onlyif=onlyif
        )
        assert ret.result is False
        assert ret.changes
        assert ret.comment == "Failure!"
