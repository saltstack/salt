grain_create_file:
  file.managed:
    - name: {{ pillar['grain_path'] }}
    - source: salt://file-grainget.tmpl
    - template: jinja

