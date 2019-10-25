#!issue55124|jinja -s|yaml

Display current time:
  cmd.run:
    - name: echo {{ salt.cmd.run('date') }}
