return_changes:
  test.succeed_with_changes:
    - watch_in:
      - test: watch_states

watch_states:
  test.succeed_without_changes
