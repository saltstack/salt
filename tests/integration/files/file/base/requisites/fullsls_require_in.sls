include:
  - requisites.fullsls_test
A:
  cmd.run:
    - name: echo A
    - require_in:
      - sls: requisites.fullsls_test
