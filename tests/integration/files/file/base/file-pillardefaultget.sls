{% set file = salt['pillar.get']('pillardoesnotexist', 'defaultvalue') %}
create_file:
  file.managed:
    - name: /tmp/filepillar-{{ file }}
