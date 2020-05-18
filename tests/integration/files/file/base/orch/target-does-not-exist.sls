core:
  salt.state:
    - tgt: 'doesnotexist*'
    - sls:
      - core

test-state:
  salt.state:
    - tgt: '*'
    - sls:
      - orch.target-test

cmd.run:
  salt.function:
    - tgt: '*'
    - arg:
      - echo test
