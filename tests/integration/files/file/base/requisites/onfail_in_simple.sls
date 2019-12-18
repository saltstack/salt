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
