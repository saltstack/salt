grain_create_file:
  file.managed:
    - name: C:\\Windows\\Temp\\file-grain-test
    - source: salt://file-grainget.tmpl
    - template: jinja

