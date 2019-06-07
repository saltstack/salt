{% set file_name = 'test' + pillar.get('test_file_suffix', '') %}
ssh-file-test:
  file.managed:
    - name: /tmp/{{ file_name }}
    - contents: 'test'

second_id:
  cmd.run:
    - name: echo test
