Step01:
  salt.state:
    - tgt: 'minion'
    - sls:
      - orch.issue43204.fail_with_changes

Step02:
  salt.function:
    - name: runtests_helpers.nonzero_retcode_return_false
    - tgt: 'minion'
    - fail_function: runtests_helpers.fail_function
