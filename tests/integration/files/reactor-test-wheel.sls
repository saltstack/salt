reactor-test:
  wheel.key.gen_accept:
    - args:
      - id_: foobar

# we just use this to signal the previous state fired
wheel-ran:
  runner.event.send:
    - args:
      - tag: test_reaction
      - data:
          test_reaction: True
