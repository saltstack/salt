core:
  salt.state:
    - tgt: 'minion*'
    - sls:
      - core

test-state:
  salt.state:
    - tgt: '*'
    - sls:
      - include-test

cmd.run:
  salt.function:
    - tgt: '*'
    - arg:
      - echo test
