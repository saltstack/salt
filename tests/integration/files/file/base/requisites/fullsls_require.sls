include:
  - requisites.fullsls_test
A:
  cmd.run:
    - name: echo A
    - require:
      - sls: requisites.fullsls_test
