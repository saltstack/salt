a: test.fail_without_changes

b:
  test.nop:
    - prereq:
      - c

c:
  test.nop:
  - require:
    - a
