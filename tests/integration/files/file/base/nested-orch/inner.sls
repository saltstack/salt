cmd.run:
  salt.function:
    - tgt: minion
    - arg:
      - /bin/false
    - failhard: True
