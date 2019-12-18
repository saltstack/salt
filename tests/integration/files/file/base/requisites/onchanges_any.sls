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

# Should succeed since at least one will have changes
test_one_changing_states:
  cmd.run:
    - name: echo "Success!"
    - onchanges_any:
      - cmd: changing_state
      - cmd: another_changing_state
      - pip: non_changing_state
      - pip: another_non_changing_state

test_two_non_changing_states:
  cmd.run:
    - name: echo "Should not run"
    - onchanges_any:
      - pip: non_changing_state
      - pip: another_non_changing_state
