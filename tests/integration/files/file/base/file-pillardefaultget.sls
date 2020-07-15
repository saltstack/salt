{% set file = salt['pillar.get']('pillardoesnotexist', 'defaultvalue') %}

create_file:
  file.managed:
    - name: {{ salt['runtests_helpers.get_salt_temp_dir_for_path']('filepillar-' + file) }}
