changing_state:
  cmd.run:
    - name: echo "Changed!"

# mock is installed with salttesting, so it should already be
# present on the system, resulting in no changes
non_changing_state:
  pip.installed:
    - name: mock

test_changing_state:
  cmd.run:
    - name: echo "Success!"
    - onchanges:
      - cmd: changing_state

test_non_changing_state:
  cmd.run:
    - name: echo "Should not run"
    - onchanges:
      - pip: non_changing_state
