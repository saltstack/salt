required_state: test.succeed_without_changes

requiring_state:
  test.succeed_without_changes:
    - require:
      - test: required_state
