{% set file = salt['pillar.get']('info', '') %}
create_file:
  file.managed:
    - name: /tmp/filepillar-{{ file }}
