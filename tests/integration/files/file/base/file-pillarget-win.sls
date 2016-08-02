{% set file = salt['pillar.get']('monty', '') %}
create_file:
  file.managed:
    - name: C:\\Windows\\Temp\\filepillar-{{ file }}
