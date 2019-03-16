include:
  - requisites.fullsls_require_import2
A:
  test.succeed_without_changes:
    - name: A
    - require:
      - sls: requisites.fullsls_require_import2
