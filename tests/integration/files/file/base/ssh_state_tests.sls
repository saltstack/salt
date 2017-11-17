ssh-file-test:
  file.managed:
    - name: /tmp/test
    - contents: 'test'
