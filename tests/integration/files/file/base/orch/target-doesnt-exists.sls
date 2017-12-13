core:
  salt.state:
    - tgt: 'doesnotexist*'
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
