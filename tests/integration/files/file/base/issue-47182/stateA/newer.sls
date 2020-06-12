exclude:
  - sls: issue-47182.stateA

somestuff:
  cmd.run:
    - name: echo This supersedes the stuff previously done in issue-47182.stateA
