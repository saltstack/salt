state.orchestrate:
  salt.runner:
    - mods: nested-orch.inner
    - failhard: True

cmd.run:
  salt.function:
    - tgt: minion
    - arg:
      - touch /tmp/ewu-2016-12-13
