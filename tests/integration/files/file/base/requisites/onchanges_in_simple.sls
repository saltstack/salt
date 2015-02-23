changing_state:
  cmd.run:
    - name: echo "Changed!"
    - onchanges_in:
      - cmd: test_changes_expected

# mock is installed with salttesting, so it should already be
# present on the system, resulting in no changes
non_changing_state:
  pip.installed:
    - name: mock
    - onchanges_in:
      - cmd: test_changes_not_expected

test_changes_expected:
  cmd.run:
    - name: echo "Success!"

test_changes_not_expected:
  cmd.run:
    - name: echo "Should not run"
