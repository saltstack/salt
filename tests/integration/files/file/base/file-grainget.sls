grain_create_file:
  file.managed:
    - name: {{ grains['grain_path'] }}
    - source: salt://file-grainget.tmpl
    - template: jinja

