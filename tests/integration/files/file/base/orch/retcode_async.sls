test_runner_success:
  salt.runner:
    - name: runtests_helpers.success
    - asynchronous: True

test_wheel_sucess:
  salt.wheel:
    - name: runtests_helpers.success
    - asynchronous: True

test_function_sucess:
  salt.function:
    - tgt: minion
    - name: runtests_helpers.success
    - asynchronous: True

test_state_sucess:
  salt.state:
    - tgt: minion
    - sls: test
    - asynchronous: True
