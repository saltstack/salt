include:
  - requisites.prereq_sls_infinite_recursion_2
A:
  test.succeed_without_changes:
    - name: A
    - prereq:
      - sls: requisites.prereq_sls_infinite_recursion_2
