cmd.run:
  salt.function:
    - tgt: minion
    - arg:
      - "$(which false)"
    - failhard: True
