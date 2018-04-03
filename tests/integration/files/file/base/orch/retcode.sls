test_runner_success:
  salt.runner:
    - name: runtests_helpers.success

test_runner_failure:
  salt.runner:
    - name: runtests_helpers.failure

test_wheel_success:
  salt.wheel:
    - name: runtests_helpers.success

test_wheel_failure:
  salt.wheel:
    - name: runtests_helpers.failure
