changing_state:
  cmd.run:
    - name: echo "Changed!"

another_changing_state:
  cmd.run:
    - name: echo "Changed!"

# mock is installed with salttesting, so it should already be
# present on the system, resulting in no changes
non_changing_state:
  pip.installed:
    - name: mock

another_non_changing_state:
  pip.installed:
    - name: mock

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
      - pip: non_changing_state
      - pip: another_non_changing_state

test_one_changing_state:
  cmd.run:
    - name: echo "Success!"
    - onchanges:
      - cmd: changing_state
      - pip: non_changing_state
