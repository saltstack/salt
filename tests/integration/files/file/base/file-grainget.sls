grain_create_file:
  file.managed:
    - name: /tmp/file-grain-test
    - source: salt://file-grainget.tmpl
    - template: jinja

