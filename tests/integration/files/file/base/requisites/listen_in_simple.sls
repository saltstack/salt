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
