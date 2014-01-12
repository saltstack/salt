include:
  - requisites.fullsls_test
A:
  cmd.run:
    - name: echo A
    - prereq:
      - sls: requisites.fullsls_test
