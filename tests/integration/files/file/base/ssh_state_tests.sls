{% set jinja = pillar.get('test_file_name', 'test') %}
ssh-file-test:
  file.managed:
    - name: /tmp/{{ jinja }}
    - contents: 'test'

second_id:
  cmd.run:
    - name: echo test
