{% set file = salt['pillar.get']('info', '') %}
create_file:
  file.managed:
    - name: C:\\Windows\\Temp\\filepillar-{{ file }}
