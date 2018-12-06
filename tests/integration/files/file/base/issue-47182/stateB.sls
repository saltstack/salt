include:
  - issue-47182.slsfile1
  - issue-47182.slsfile2

some-state:
  test.nop:
    - require:
      - sls: issue-47182.slsfile1
    - require_in:
      - sls: issue-47182.slsfile2
