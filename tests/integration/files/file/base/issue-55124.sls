#!issue55124|jinja -s|yaml

'Who am I?':
  cmd.run:
    - name: echo {{ salt.cmd.run('whoami') }}
