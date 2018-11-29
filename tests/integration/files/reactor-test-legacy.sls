reactor-test:
  runner.event.send:
    - arg:
      - test_reaction
    - kwarg:
        data:
          test_reaction: True
