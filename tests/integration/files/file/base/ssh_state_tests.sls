{% set jinja = 'test' %}
ssh-file-test:
  file.managed:
    - name: /tmp/{{ jinja }}
    - contents: 'test'

second_id:
  cmd.run:
    - name: echo test
