{% set file = salt['pillar.get']('pillardoesnotexist', 'defaultvalue') %}
create_file:
  file.managed:
    - name: C:\\Windows\\Temp\\filepillar-{{ file }}
