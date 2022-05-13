{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('prod-cheese-file') }}:
  file.managed:
    - source: salt://cheese
