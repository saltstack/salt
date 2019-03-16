call_sleep_state:
  salt.state:
    - tgt: '*'
    - sls: simple-ping
