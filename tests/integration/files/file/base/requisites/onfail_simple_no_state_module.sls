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
