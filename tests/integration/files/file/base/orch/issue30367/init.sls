deploy_check:
  salt.function:
    - name: test.false
    - tgt: minion
