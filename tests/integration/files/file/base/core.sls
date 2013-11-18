{{ salt['runtests_helpers.get_sys_temp_dir_for_path']('testfile') }}:
  file:
    - managed
    - source: salt://testfile
