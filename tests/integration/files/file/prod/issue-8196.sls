{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('prod-cheese-file') }}:
  file.managed:
    - source: salt://cheese
