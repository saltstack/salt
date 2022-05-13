include:
  - validate-saltcheck.directory
  - validate-saltcheck.directory.level1

saltcheck-test-pass:
  test.succeed_without_changes:
    - name: testing-saltcheck
