include:
  - stuff

ls -l:
  cmd.run:
    - require_in:
      - sls: stuff
