call_fail_state:
  salt.state:
    - tgt: '*minion'
    - batch: 1
    - failhard: True
    - sls: fail
