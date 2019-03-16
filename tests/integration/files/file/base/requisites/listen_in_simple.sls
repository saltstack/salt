successful_changing_state:
  cmd.run:
    - name: echo "Successful Change"
    - listen_in:
      - cmd: test_listening_change_state

# mock is installed with salttesting, so it should already be
# present on the system, resulting in no changes
non_changing_state:
  pip.installed:
    - name: mock
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
