{% from "validate-saltcheck/map.jinja" import testdata with context %}

saltcheck-prod-test-pass:
  test.succeed_without_changes:
    - name: testing-saltcheck-prodenv
