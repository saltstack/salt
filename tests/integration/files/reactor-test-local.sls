reactor-test:
  local.event.fire_master:
    - tgt: 'minion'
    - args:
      - tag: test_reaction
      - data:
          test_reaction: True
