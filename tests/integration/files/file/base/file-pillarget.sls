{% set file = salt['pillar.get']('monty', '') %}
create_file:
  file.managed:
    - name: /tmp/filepillar-{{ file }}
